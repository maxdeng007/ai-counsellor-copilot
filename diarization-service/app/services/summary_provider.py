from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI

from app.schemas.summary_schema import SummarizeMeetingRequest, SummaryOutput
from app.services.entity_extractor import transcript_to_prompt_lines

_log = logging.getLogger("summary-provider")

SUMMARY_PROVIDER = os.getenv("SUMMARY_PROVIDER", "openai").strip().lower() or "openai"
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()


def _output_schema() -> Dict[str, Any]:
    # Keep schema aligned with SummaryPanel contract.
    kv_row = {
        "type": "object",
        "properties": {
            "k": {"type": "string"},
            "v": {"type": "string"},
        },
        "required": ["k", "v"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summaryZh": {"type": "string"},
            "summaryEn": {"type": "string"},
            "profile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "labelZh": {"type": "string"},
                    "labelEn": {"type": "string"},
                    "rowsZh": {"type": "array", "items": kv_row},
                    "rowsEn": {"type": "array", "items": kv_row},
                },
                "required": ["labelZh", "labelEn", "rowsZh", "rowsEn"],
            },
            "assets": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "labelZh": {"type": "string"},
                    "labelEn": {"type": "string"},
                    "rowsZh": {"type": "array", "items": kv_row},
                    "rowsEn": {"type": "array", "items": kv_row},
                },
                "required": ["labelZh", "labelEn", "rowsZh", "rowsEn"],
            },
            "risk": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "labelZh": {"type": "string"},
                    "labelEn": {"type": "string"},
                    "levelZh": {"type": "string"},
                    "levelEn": {"type": "string"},
                    "targetZh": {"type": "string"},
                    "targetEn": {"type": "string"},
                },
                "required": ["labelZh", "labelEn", "levelZh", "levelEn", "targetZh", "targetEn"],
            },
            "topicsZh": {"type": "array", "items": {"type": "string"}},
            "topicsEn": {"type": "array", "items": {"type": "string"}},
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "textZh": {"type": "string"},
                        "textEn": {"type": "string"},
                        "dueZh": {"type": "string"},
                        "dueEn": {"type": "string"},
                    },
                    "required": ["id", "textZh", "textEn", "dueZh", "dueEn"],
                },
            },
            "emailDraftZh": {"type": "string"},
            "emailDraftEn": {"type": "string"},
        },
        "required": [
            "summaryZh",
            "summaryEn",
            "profile",
            "assets",
            "risk",
            "topicsZh",
            "topicsEn",
            "actions",
            "emailDraftZh",
            "emailDraftEn",
        ],
    }


def _fallback_output(req: SummarizeMeetingRequest) -> SummaryOutput:
    locale = req.locale or "zh"
    client_name = req.linkedClient.nameZh if locale == "zh" else req.linkedClient.nameEn
    if not client_name:
      client_name = req.linkedClient.nameZh or req.linkedClient.nameEn or "client"
    summary_zh = f"已完成会谈记录整理。建议围绕客户 {client_name} 的核心诉求进行后续跟进。"
    summary_en = f"Meeting notes compiled. Follow-up should focus on core needs for {client_name}."
    return SummaryOutput(
        summaryZh=summary_zh,
        summaryEn=summary_en,
        profile={"labelZh": "客户画像", "labelEn": "Client Profile", "rowsZh": [], "rowsEn": []},
        assets={"labelZh": "资产盘点", "labelEn": "Asset Snapshot", "rowsZh": [], "rowsEn": []},
        risk={"labelZh": "风险偏好", "labelEn": "Risk Profile", "levelZh": "待评估", "levelEn": "TBD", "targetZh": "", "targetEn": ""},
        topicsZh=[],
        topicsEn=[],
        actions=[],
        emailDraftZh="您好，感谢今天会谈。后续建议我将整理详细建议并与您确认下一步计划。",
        emailDraftEn="Thank you for today's meeting. I will send a structured follow-up with recommended next steps.",
    )


def _build_messages(req: SummarizeMeetingRequest) -> List[Dict[str, str]]:
    lines = transcript_to_prompt_lines(req.transcript)
    transcript_plain = "\n".join([f'{line["speaker"]}: {line["text"]}' for line in lines[:400]])
    locale = req.locale or "zh"
    user_prompt = {
        "locale": locale,
        "linkedClient": req.linkedClient.model_dump(),
        "transcript": transcript_plain,
        "requirements": {
            "mustUseTranscriptFactsOnly": True,
            "noFabrication": True,
            "outputBothZhEnFields": True,
            "maxActions": 5,
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You are a financial counsellor meeting assistant. "
                "Return strict JSON only. No markdown. "
                "Use transcript facts only, do not hallucinate numbers."
            ),
        },
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]


def summarize_with_openai(req: SummarizeMeetingRequest) -> SummaryOutput:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client_kwargs: Dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL
    client = OpenAI(**client_kwargs)

    messages = _build_messages(req)
    schema = _output_schema()
    response = client.chat.completions.create(
        model=SUMMARY_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "meeting_summary_output",
                "schema": schema,
                "strict": True,
            },
        },
        temperature=0.2,
    )
    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise RuntimeError("empty_response_content")
    parsed = json.loads(content)
    return SummaryOutput.model_validate(parsed)


def summarize_meeting(req: SummarizeMeetingRequest) -> Dict[str, Any]:
    if SUMMARY_PROVIDER != "openai":
        _log.warning("Unsupported SUMMARY_PROVIDER=%s, fallback to openai", SUMMARY_PROVIDER)
    try:
        output = summarize_with_openai(req)
        return {
            "ok": True,
            "degraded": False,
            "provider": "openai",
            "aiOutput": output,
        }
    except Exception as error:
        _log.exception("summary generation failed, returning degraded output")
        fallback = _fallback_output(req)
        return {
            "ok": False,
            "degraded": True,
            "provider": "openai",
            "error": f"{type(error).__name__}: {error}",
            "aiOutput": fallback,
        }

