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

# Volcano Ark (豆包) — OpenAI-compatible Chat Completions; use api root …/api/v3 (SDK adds /chat/completions).
VOLC_ARK_BASE_URL_DEFAULT = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_SEED_LITE_EP = "ep-m-20260427181727-ms2s8"
DOUBAO_SEED_MINI_EP = "ep-m-20260506152356-bdvpg"
VOLC_ARK_API_KEY = os.getenv("VOLC_ARK_API_KEY", "").strip()


def _normalize_summary_provider(raw: str) -> str:
    key = (raw or "openai").strip().lower() or "openai"
    if key in ("volc_ark", "volc", "ark", "doubao", "byte_ark"):
        return "volc_ark"
    if key == "openai":
        return "openai"
    _log.warning("Unknown SUMMARY_PROVIDER=%r; falling back to openai", raw)
    return "openai"


def _volc_ark_base_url() -> str:
    raw = (os.getenv("VOLC_ARK_BASE_URL") or "").strip() or VOLC_ARK_BASE_URL_DEFAULT
    base = raw.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base


def _resolved_volc_ark_model() -> str:
    explicit = os.getenv("VOLC_ARK_MODEL", "").strip()
    if explicit:
        return explicit
    tier = os.getenv("VOLC_ARK_MODEL_TIER", "lite").strip().lower()
    if tier in ("mini", "seed-mini", "doubao-seed-2.0-mini"):
        return DOUBAO_SEED_MINI_EP
    return DOUBAO_SEED_LITE_EP


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


def _chat_summary_json_schema(client: OpenAI, model: str, req: SummarizeMeetingRequest) -> SummaryOutput:
    messages = _build_messages(req)
    schema = _output_schema()
    response = client.chat.completions.create(
        model=model,
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


def summarize_with_openai(req: SummarizeMeetingRequest) -> SummaryOutput:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client_kwargs: Dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL.rstrip("/")
    client = OpenAI(**client_kwargs)
    return _chat_summary_json_schema(client, SUMMARY_MODEL, req)


def summarize_with_volc_ark(req: SummarizeMeetingRequest) -> SummaryOutput:
    if not VOLC_ARK_API_KEY:
        raise RuntimeError("VOLC_ARK_API_KEY is missing")
    client = OpenAI(api_key=VOLC_ARK_API_KEY, base_url=_volc_ark_base_url())
    model = _resolved_volc_ark_model()
    return _chat_summary_json_schema(client, model, req)


def summarize_meeting(req: SummarizeMeetingRequest) -> Dict[str, Any]:
    provider = _normalize_summary_provider(SUMMARY_PROVIDER)
    try:
        if provider == "volc_ark":
            output = summarize_with_volc_ark(req)
            return {
                "ok": True,
                "degraded": False,
                "provider": "volc_ark",
                "aiOutput": output,
            }
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
            "provider": provider,
            "error": f"{type(error).__name__}: {error}",
            "aiOutput": fallback,
        }

