from __future__ import annotations

import re
from typing import Dict, List

from app.schemas.summary_schema import ExtractEntitiesResponse, TranscriptPayload


CLIENT_PATTERNS = [
    re.compile(r"(王女士|李太太|李先生|张总|陈博士|周先生)"),
    re.compile(r"\b(Mrs\. Wang|Mr\. Li|Mrs\. Li|Mr\. Zhang|Dr\. Chen|Mr\. Zhou)\b", re.I),
]

TOPIC_KEYWORDS = {
    "退休规划": ["退休", "retire", "retirement"],
    "资产配置": ["资产", "配置", "portfolio", "allocation"],
    "保险规划": ["保险", "重疾", "寿险", "insurance"],
    "教育金规划": ["留学", "教育金", "education", "overseas studies"],
}

KNOWN_CLIENT_IDS = {
    "王女士": "c-wang",
    "Mrs. Wang": "c-wang",
    "李先生": "c-li-family",
    "李太太": "c-li-family",
    "Mr. Li": "c-li-family",
    "Mrs. Li": "c-li-family",
    "张总": "c-zhang",
    "Mr. Zhang": "c-zhang",
    "陈博士": "c-chen",
    "Dr. Chen": "c-chen",
    "周先生": "c-zhou",
    "Mr. Zhou": "c-zhou",
}


def _collect_text(transcript: TranscriptPayload) -> str:
    lines = []
    for seg in transcript.segments:
        txt = str(seg.text or "").strip()
        if txt:
            lines.append(txt)
    return "\n".join(lines)


def _guess_name(text: str) -> str:
    for pattern in CLIENT_PATTERNS:
        m = pattern.search(text)
        if m:
            return str(m.group(1)).strip()
    return ""


def _extract_topics(text: str) -> List[str]:
    lowered = text.lower()
    topics: List[str] = []
    for label, kws in TOPIC_KEYWORDS.items():
        if any(kw.lower() in lowered for kw in kws):
            topics.append(label)
    return topics


def extract_entities(transcript: TranscriptPayload, locale: str = "zh") -> ExtractEntitiesResponse:
    text = _collect_text(transcript)
    guessed = _guess_name(text)
    matched_id = KNOWN_CLIENT_IDS.get(guessed, "")
    topics = _extract_topics(text)

    if locale == "zh":
        name_zh = guessed if guessed and re.search(r"[\u4e00-\u9fff]", guessed) else ""
        name_en = ""
        hint_zh = f"从「{guessed}」识别" if guessed else "未检测到明确姓名，建议手动关联"
        hint_en = f'Detected from "{guessed}"' if guessed else "No clear name detected, please link manually"
    else:
        name_en = guessed if guessed and not re.search(r"[\u4e00-\u9fff]", guessed) else ""
        name_zh = ""
        hint_en = f'Detected from "{guessed}"' if guessed else "No clear name detected, please link manually"
        hint_zh = f"从「{guessed}」识别" if guessed else "未检测到明确姓名，建议手动关联"

    confidence = 0.9 if guessed else 0.35
    extracted = {
        "nameZh": name_zh,
        "nameEn": name_en,
        "hintZh": hint_zh,
        "hintEn": hint_en,
        "matchClientId": matched_id,
        "confidence": confidence,
    }
    candidates = [matched_id] if matched_id else []

    return ExtractEntitiesResponse(
        extractedClient=extracted,
        candidateClientIds=candidates,
        topics=topics,
    )


def transcript_to_prompt_lines(transcript: TranscriptPayload) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    for seg in transcript.segments:
        speaker = str(seg.speakerId or "").strip() or "speaker"
        text = str(seg.text or "").strip()
        if not text:
            continue
        lines.append({"speaker": speaker, "text": text})
    return lines

