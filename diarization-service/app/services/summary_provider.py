from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import httpx
from openai import OpenAI
from pydantic import ValidationError

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

# Xiaomi MiMo — OpenAI-compatible Chat Completions (Token Plan or pay-as-you-go).
MIMO_BASE_URL_DEFAULT = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL_DEFAULT = "mimo-v2.5-pro"
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "").strip()
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "").strip()
MIMO_MODEL = os.getenv("MIMO_MODEL", "").strip()


def _openai_http_client() -> httpx.Client:
    # macOS/VPN often sets a system proxy that breaks LLM/ASR HTTP clients (502 via SDK).
    return httpx.Client(trust_env=False, timeout=120.0)


def _normalize_summary_provider(raw: str) -> str:
    key = (raw or "openai").strip().lower() or "openai"
    if key in ("volc_ark", "volc", "ark", "doubao", "byte_ark"):
        return "volc_ark"
    if key in ("xiaomi_mimo", "mimo", "xiaomi", "token_plan", "mimo_token_plan"):
        return "xiaomi_mimo"
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


def _mimo_base_url() -> str:
    raw = (MIMO_BASE_URL or "").strip() or MIMO_BASE_URL_DEFAULT
    base = raw.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base


def _resolved_mimo_model() -> str:
    explicit = MIMO_MODEL.strip()
    if explicit:
        return explicit
    tier = os.getenv("MIMO_MODEL_TIER", "pro").strip().lower()
    if tier in ("flash", "lite", "mimo-v2.5", "v2.5"):
        return "mimo-v2.5"
    return MIMO_MODEL_DEFAULT


def _mimo_openai_client() -> OpenAI:
    if not MIMO_API_KEY:
        raise RuntimeError("MIMO_API_KEY is missing")
    # Token Plan docs use the api-key header (tp-xxxxx); keep Bearer via api_key for SDK compatibility.
    return OpenAI(
        api_key=MIMO_API_KEY,
        base_url=_mimo_base_url(),
        default_headers={"api-key": MIMO_API_KEY},
        http_client=_openai_http_client(),
    )


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
                "Return strict JSON only. No markdown, no prose, no code fences.\n\n"
                "You MUST return ALL of these fields, even when empty or 'N/A':\n"
                "- summaryZh, summaryEn (string)\n"
                "- profile {labelZh, labelEn, rowsZh[], rowsEn[]} with each row being {k, v}\n"
                "- assets {labelZh, labelEn, rowsZh[], rowsEn[]} with each row being {k, v}\n"
                "- risk {labelZh, labelEn, levelZh, levelEn, targetZh, targetEn}\n"
                "- topicsZh[], topicsEn[]\n"
                "- actions[] where each item is {id, textZh, textEn, dueZh, dueEn}. "
                "Set `id` to act-1, act-2, ... act-5. Use empty string '' for missing due dates.\n"
                "- emailDraftZh, emailDraftEn (string)\n\n"
                "Use only facts from the transcript. Do NOT invent numbers, names, or "
                "dates. If a section has no data, use '' or []. Fill bilingual pairs for "
                "every value where the locale is bilingual (zh + en)."
            ),
        },
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]


def _normalize_action_items(items: Any) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    if not isinstance(items, list):
        return actions
    for i, item in enumerate(items[:5]):
        if not isinstance(item, dict):
            continue
        # Free-tier models (gpt-oss-20b, qwen3-next-80b) sometimes use a
        # title/description shape instead of id/textZh/textEn. Combine them
        # into the single textZh/textEn fields the schema requires.
        title_zh = item.get("titleZh") or item.get("title") or ""
        title_en = item.get("titleEn") or ""
        desc_zh = item.get("descriptionZh") or item.get("description") or ""
        desc_en = item.get("descriptionEn") or ""
        combined_zh = f"{title_zh}：{desc_zh}".strip("： ").strip()
        combined_en = f"{title_en}: {desc_en}".strip(": ").strip()
        actions.append(
            {
                "id": str(item.get("id") or item.get("actionId") or f"act-{i + 1}"),
                "textZh": str(
                    item.get("textZh")
                    or item.get("zh")
                    or item.get("actionZh")
                    or combined_zh
                    or ""
                ),
                "textEn": str(
                    item.get("textEn")
                    or item.get("en")
                    or item.get("actionEn")
                    or combined_en
                    or ""
                ),
                "dueZh": str(item.get("dueZh") or ""),
                "dueEn": str(item.get("dueEn") or ""),
            }
        )
    return actions


def _bilingual_text(block: Any) -> tuple[str, str]:
    if isinstance(block, dict):
        zh = str(block.get("zh") or block.get("summaryZh") or block.get("textZh") or "")
        en = str(block.get("en") or block.get("summaryEn") or block.get("textEn") or "")
        return zh, en
    if isinstance(block, str):
        return block, ""
    return "", ""


def _empty_summary_section(label_zh: str, label_en: str) -> Dict[str, Any]:
    return {"labelZh": label_zh, "labelEn": label_en, "rowsZh": [], "rowsEn": []}


def _empty_risk_section() -> Dict[str, Any]:
    return {
        "labelZh": "风险偏好",
        "labelEn": "Risk Profile",
        "levelZh": "待评估",
        "levelEn": "TBD",
        "targetZh": "",
        "targetEn": "",
    }


def _coerce_summary_section(value: Any, label_zh: str, label_en: str) -> Dict[str, Any]:
    section = _empty_summary_section(label_zh, label_en)
    if value is None:
        return section
    if isinstance(value, dict):
        if value.get("rowsZh") is not None or value.get("rowsEn") is not None:
            section["labelZh"] = str(value.get("labelZh") or label_zh)
            section["labelEn"] = str(value.get("labelEn") or label_en)
            section["rowsZh"] = list(value.get("rowsZh") or [])
            section["rowsEn"] = list(value.get("rowsEn") or [])
            return section
        rows_zh: List[Dict[str, str]] = []
        rows_en: List[Dict[str, str]] = []
        for key, raw in value.items():
            if raw is None or raw == "":
                continue
            label = str(key)
            text = str(raw)
            rows_zh.append({"k": label, "v": text})
            rows_en.append({"k": label, "v": text})
        section["rowsZh"] = rows_zh
        section["rowsEn"] = rows_en
        return section
    if isinstance(value, list):
        rows_zh = []
        rows_en = []
        for item in value:
            if not isinstance(item, dict):
                continue
            k_zh = str(item.get("k") or item.get("typeZh") or item.get("nameZh") or "项目")
            v_zh = str(item.get("v") or item.get("valueZh") or item.get("amountZh") or item.get("amount") or "")
            k_en = str(item.get("kEn") or item.get("typeEn") or item.get("nameEn") or k_zh)
            v_en = str(item.get("vEn") or item.get("valueEn") or item.get("amountEn") or v_zh)
            if v_zh:
                rows_zh.append({"k": k_zh, "v": v_zh})
            if v_en:
                rows_en.append({"k": k_en, "v": v_en})
        section["rowsZh"] = rows_zh
        section["rowsEn"] = rows_en
    return section


def _coerce_risk_section(value: Any) -> Dict[str, Any]:
    risk = _empty_risk_section()
    if not isinstance(value, dict):
        return risk
    if value.get("levelZh") or value.get("labelZh"):
        for key in risk.keys():
            if key in value and value[key] is not None:
                risk[key] = str(value[key])
        return risk
    tolerance = value.get("riskTolerance") or value.get("level") or value.get("tolerance")
    if tolerance:
        risk["levelZh"] = str(tolerance)
        risk["levelEn"] = str(value.get("riskToleranceEn") or value.get("levelEn") or tolerance)
    target = value.get("target") or value.get("targetZh")
    if target:
        risk["targetZh"] = str(target)
        risk["targetEn"] = str(value.get("targetEn") or target)
    return risk


def _coerce_mimo_actions(value: Any) -> List[Dict[str, str]]:
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return [
            {
                "id": f"act-{i + 1}",
                "textZh": text,
                "textEn": "",
                "dueZh": "",
                "dueEn": "",
            }
            for i, text in enumerate(value[:5])
        ]
    return _normalize_action_items(value)


def _coerce_mimo_summary_dict(parsed: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        raise RuntimeError("mimo_summary_not_object")

    out: Dict[str, Any] = {}
    if parsed.get("summaryZh") or parsed.get("summaryEn"):
        out["summaryZh"] = str(parsed.get("summaryZh") or "")
        out["summaryEn"] = str(parsed.get("summaryEn") or "")
    else:
        for key in ("meetingSummary", "transcriptSummary", "summary"):
            if key in parsed:
                zh, en = _bilingual_text(parsed[key])
                if zh or en:
                    out["summaryZh"] = zh
                    out["summaryEn"] = en
                    break

    profile_source = parsed.get("profile")
    if profile_source is None and isinstance(parsed.get("clientProfile"), dict):
        cp = parsed["clientProfile"]
        zh, en = _bilingual_text(cp)
        profile_source = cp if not (zh or en) else {"rowsZh": [{"k": "概况", "v": zh}] if zh else [], "rowsEn": [{"k": "Overview", "v": en}] if en else []}
    out["profile"] = _coerce_summary_section(profile_source, "客户画像", "Client Profile")

    key_facts = parsed.get("keyFacts")
    if isinstance(key_facts, list):
        topics_zh: List[str] = []
        topics_en: List[str] = []
        extra_rows_zh: List[Dict[str, str]] = []
        extra_rows_en: List[Dict[str, str]] = []
        for fact in key_facts:
            if not isinstance(fact, dict):
                continue
            fz = str(fact.get("factZh") or fact.get("zh") or "")
            fe = str(fact.get("factEn") or fact.get("en") or "")
            if fz:
                topics_zh.append(fz)
                extra_rows_zh.append({"k": "要点", "v": fz})
            if fe:
                topics_en.append(fe)
                extra_rows_en.append({"k": "Point", "v": fe})
        if topics_zh:
            out["topicsZh"] = topics_zh
        if topics_en:
            out["topicsEn"] = topics_en
        if extra_rows_zh:
            out["profile"]["rowsZh"] = list(out["profile"].get("rowsZh") or []) + extra_rows_zh
        if extra_rows_en:
            out["profile"]["rowsEn"] = list(out["profile"].get("rowsEn") or []) + extra_rows_en

    out["assets"] = _coerce_summary_section(parsed.get("assets"), "资产盘点", "Asset Snapshot")
    out["risk"] = _coerce_risk_section(parsed.get("risk"))
    out["topicsZh"] = list(parsed.get("topicsZh") or out.get("topicsZh") or [])
    out["topicsEn"] = list(parsed.get("topicsEn") or out.get("topicsEn") or [])
    out["actions"] = _coerce_mimo_actions(
        parsed.get("actions") or parsed.get("actionItems") or parsed.get("recommendedActions")
    )
    out["emailDraftZh"] = str(parsed.get("emailDraftZh") or "")
    out["emailDraftEn"] = str(parsed.get("emailDraftEn") or "")

    out.setdefault("summaryZh", "")
    out.setdefault("summaryEn", "")
    return out


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
    # Some free-tier models (e.g. gpt-oss-20b:free, qwen3-next-80b-a3b:free)
    # return actions shaped as {"zh": "...", "en": "..."} or omit the required
    # `id` field even when strict=True is set. Run the same lenient coercion
    # path used for Xiaomi MiMo so we accept either shape, then fall back to
    # strict validation only if coercion produces nothing usable.
    try:
        coerced = _coerce_mimo_summary_dict(parsed)
        return SummaryOutput.model_validate(coerced)
    except (ValidationError, RuntimeError, ValueError):
        return SummaryOutput.model_validate(parsed)


def _chat_summary_mimo(client: OpenAI, model: str, req: SummarizeMeetingRequest) -> SummaryOutput:
    messages = _build_messages(req)
    messages[0]["content"] += (
        " Output JSON must use top-level keys summaryZh, summaryEn, profile, assets, risk, "
        "topicsZh, topicsEn, actions, emailDraftZh, emailDraftEn."
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise RuntimeError("empty_response_content")
    parsed = json.loads(content)
    coerced = _coerce_mimo_summary_dict(parsed)
    output = SummaryOutput.model_validate(coerced)
    if not (output.summaryZh.strip() or output.summaryEn.strip()):
        raise RuntimeError("mimo_empty_summary")
    return output


def summarize_with_openai(req: SummarizeMeetingRequest) -> SummaryOutput:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client_kwargs: Dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL.rstrip("/")
    client_kwargs["http_client"] = _openai_http_client()
    client = OpenAI(**client_kwargs)
    return _chat_summary_json_schema(client, SUMMARY_MODEL, req)


def summarize_with_volc_ark(req: SummarizeMeetingRequest) -> SummaryOutput:
    if not VOLC_ARK_API_KEY:
        raise RuntimeError("VOLC_ARK_API_KEY is missing")
    client = OpenAI(
        api_key=VOLC_ARK_API_KEY,
        base_url=_volc_ark_base_url(),
        http_client=_openai_http_client(),
    )
    model = _resolved_volc_ark_model()
    return _chat_summary_json_schema(client, model, req)


def summarize_with_xiaomi_mimo(req: SummarizeMeetingRequest) -> SummaryOutput:
    client = _mimo_openai_client()
    model = _resolved_mimo_model()
    return _chat_summary_mimo(client, model, req)


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
        if provider == "xiaomi_mimo":
            output = summarize_with_xiaomi_mimo(req)
            return {
                "ok": True,
                "degraded": False,
                "provider": "xiaomi_mimo",
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

