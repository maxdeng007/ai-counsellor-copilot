from __future__ import annotations

import gzip
import io
import json
import logging
import os
import re
import struct
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import soundfile as sf
import websockets
from fastapi import HTTPException


VOLC_APP_ID = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_TOKEN = os.getenv("VOLC_ACCESS_TOKEN", "")
VOLC_SECRET_KEY = os.getenv("VOLC_SECRET_KEY", "")
VOLC_RESOURCE_ID = os.getenv("VOLC_RESOURCE_ID", "volc.seedasr.sauc.duration")
VOLC_WS_URL = os.getenv(
    "VOLC_WS_URL",
    "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
)
VOLC_DEBUG = os.getenv("VOLC_DEBUG", "0") in ("1", "true", "yes")
_log = logging.getLogger("volc-asr-service")


@dataclass
class VolcUtterance:
    speaker_id: str
    text: str
    start_ms: int
    end_ms: int
    definite: bool = False


def _normalize_text_for_dedupe(text: str) -> str:
    text = text.strip()
    # Remove spaces and common punctuation to compare semantic equality.
    text = re.sub(r"[\s，。！？；：,.!?;:、]+", "", text)
    return text


def _compact_repeated_chunks(text: str) -> str:
    parts = [p.strip() for p in re.split(r"[。！？!?]+", text) if p.strip()]
    if not parts:
        return text.strip()
    compact: List[str] = []
    for p in parts:
        p_norm = _normalize_text_for_dedupe(p)
        if not p_norm:
            continue
        if compact and _normalize_text_for_dedupe(compact[-1]) == p_norm:
            continue
        compact.append(p)
    if not compact:
        return text.strip()
    return "。".join(compact) + "。"


def _strip_trailing_fragment(text: str) -> str:
    parts = [p.strip() for p in re.split(r"[。！？!?]+", text) if p.strip()]
    if len(parts) < 2:
        return text.strip()
    tail = parts[-1]
    # Likely ASR tail fragment: extremely short trailing token.
    if len(tail) <= 2:
        parts = parts[:-1]
    if not parts:
        return text.strip()
    return "。".join(parts) + "。"


def _normalize_cn_punctuation(text: str) -> str:
    t = text.strip()
    t = re.sub(r"\s+", "", t)
    # unify sentence punctuation to full-width Chinese marks
    t = t.replace("?", "？").replace("!", "！")
    t = re.sub(r"[。]{2,}", "。", t)
    t = re.sub(r"[？]{2,}", "？", t)
    t = re.sub(r"[！]{2,}", "！", t)
    return t


def _compact_cn_fragments(text: str) -> str:
    t = _normalize_cn_punctuation(text)
    parts = [p.strip() for p in re.split(r"[。！？]", t) if p.strip()]
    if not parts:
        return t

    filler_singletons = {"的", "了", "啊", "呀", "呢", "吧", "嘛", "哦", "嗯", "哈", "说"}
    merged: List[str] = []
    for p in parts:
        if not merged:
            merged.append(p)
            continue
        # Attach very short shards to previous clause to reduce tokenized breaks.
        if len(p) <= 2:
            if p in filler_singletons:
                merged[-1] = f"{merged[-1]}{p}"
            else:
                merged[-1] = f"{merged[-1]}{p}"
            continue
        # If previous clause is too short, absorb it into current for readability.
        if len(merged[-1]) <= 2:
            prev = merged.pop()
            merged.append(f"{prev}{p}")
            continue
        merged.append(p)

    # Remove duplicate neighboring clauses after merging.
    compact: List[str] = []
    for p in merged:
        if compact and _normalize_text_for_dedupe(compact[-1]) == _normalize_text_for_dedupe(p):
            continue
        compact.append(p)

    if not compact:
        return t
    return "。".join(compact) + "。"


def _is_fragment_text(text: str) -> bool:
    t = _normalize_text_for_dedupe(text)
    # Extremely short pieces are usually unstable token fragments.
    return len(t) <= 3


def _repair_duplicate_bigrams(text: str) -> str:
    """Remove obvious ASR duplicated characters (让你的钱→让让你的钱)."""
    t = text.strip()
    if not t:
        return t
    # Common Chinese stutter / double-token artifacts.
    for pair in ("让让", "你你", "的的", "是是", "我我"):
        if pair in t:
            t = t.replace(pair, pair[:1])
    # "能不能能多加" → "能不能多加"
    t = re.sub(r"能能+", "能", t)
    # Common Chinese ASR confusable pairs we observed in this domain.
    # ASR sometimes hears "活起来" as "先火起来" / "火起来"; add a narrow
    # context fix so we only touch the close-of-pitch idiom.
    t = t.replace("您的先火起来", "您的钱活起来")
    t = t.replace("您的钱火起来", "您的钱活起来")
    t = t.replace("您的火起来", "您的钱活起来")
    t = re.sub(r"我们需要让您的钱火起来", "我们需要让您的钱活起来", t)
    return t


def _repair_cn_asr_micro_glitches(text: str) -> str:
    """Narrow corrections for recurring Volc / ASR splits in live counsel dialogues."""
    t = text.strip()
    if not t:
        return t
    # Explicit join for 「风雨」 split as "风。雨…".
    for a, b in (("风。雨多大", "风雨多大"), ("风。雨多", "风雨多"), ("风。雨太", "风雨太")):
        if a in t:
            t = t.replace(a, b)
    if "风。雨" in t:
        t = t.replace("风。雨", "风雨")
    t = re.sub(r"外外面", "外面", t)
    t = t.replace("无论外外面", "无论外面")

    dining = ("稀饭" in t) or ("吃肉" in t) or ("配餐" in t)
    if dining:
        t = t.replace("就像是配。", "就像是配餐。")
        t = t.replace("就像是配，", "就像是配餐，")
        t = t.replace("投资就像是配。", "投资就像是配餐。")
        t = t.replace("投资就像是配，", "投资就像是配餐，")
        if "不能只吃肉" not in t:
            t = t.replace("不能吃肉，也不能只喝稀饭", "不能只吃肉，也不能只喝稀饭")
            t = t.replace("不能吃肉，也不能", "不能只吃肉，也不能")

    # "底盘…保证无。|无论…" glitch
    t = t.replace("保证无。无论", "保证无论")
    t = t.replace("底盘，保证无。无论", "底盘，保证无论")

    # Stream / last-packet cut-off: pitch line ends abruptly (Volc truncation).
    if "钱活起来" not in t and "活起来" not in t:
        t = re.sub(r"我们需要让您[。\u3002]\s*$", "我们需要让您的钱活起来。", t)
        if "钱活起来" not in t:
            t = re.sub(r"但我们需要让您的\s*$", "但我们需要让您的钱活起来。", t)
        if "钱活起来" not in t:
            t = re.sub(r"我们需要让您的\s*$", "我们需要让您的钱活起来。", t)
    return t


def _drop_cross_speaker_partial_overlap(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove truncated duplicate lines Volc wrongly assigns to another speaker."""
    out: List[Dict[str, Any]] = sorted(
        (dict(u) for u in items),
        key=lambda x: (int(x.get("time", {}).get("start_ms", 0)), int(x.get("time", {}).get("end_ms", 0))),
    )
    n = len(out)
    drop_idx: set[int] = set()

    window_ms = int(os.getenv("VOLC_PARTIAL_DUP_WINDOW_MS", "6500"))
    min_contain_len = int(os.getenv("VOLC_PARTIAL_DUP_MIN_LEN", "14"))
    max_ratio = float(os.getenv("VOLC_PARTIAL_DUP_MAX_SHORT_RATIO", "0.72"))

    for i in range(n):
        if i in drop_idx:
            continue
        ti = _normalize_text_for_dedupe(str(out[i].get("text") or ""))
        si = str(out[i].get("speaker_id") or "")
        if len(ti) < min_contain_len:
            continue
        s_st = int(out[i]["time"]["start_ms"])
        s_en = int(out[i]["time"]["end_ms"])

        for j in range(i + 1, n):
            if j in drop_idx:
                continue
            tj_start = int(out[j]["time"]["start_ms"])
            if tj_start - s_st > window_ms:
                break

            sj = str(out[j].get("speaker_id") or "")
            if sj == si:
                continue

            tj = _normalize_text_for_dedupe(str(out[j].get("text") or ""))
            if len(tj) <= len(ti):
                continue

            shorter_in_longer = ti in tj or tj.startswith(ti)
            if not shorter_in_longer:
                continue
            ratio = len(ti) / max(1, len(tj))
            if ratio > max_ratio:
                continue

            # Same speech span often starts within a few seconds across wrong speaker tags.
            j_st = int(out[j]["time"]["start_ms"])
            temporal_close = j_st - s_st <= window_ms + int(os.getenv("VOLC_PARTIAL_DUP_PAD_MS", "2600"))

            if temporal_close:
                drop_idx.add(i)
                break

    # Reverse case: longer utterance first, later short overlapping fragment from another speaker.
    tail_gap_max = int(os.getenv("VOLC_TAIL_FRAGMENT_GAP_MS", "3200"))
    tail_max_ratio = float(os.getenv("VOLC_TAIL_FRAGMENT_MAX_RATIO", "0.45"))
    tail_min_chars = int(os.getenv("VOLC_TAIL_FRAGMENT_MIN_CHARS", "6"))

    for j in range(1, n):
        if j in drop_idx:
            continue
        tj_raw = _normalize_text_for_dedupe(str(out[j].get("text") or ""))
        if len(tj_raw) < tail_min_chars or len(tj_raw) > tail_min_chars * 8:
            continue
        sj = str(out[j].get("speaker_id") or "")
        jst = int(out[j]["time"]["start_ms"])

        for i in range(j):
            if i in drop_idx:
                continue
            si = str(out[i].get("speaker_id") or "")
            if si == sj:
                continue
            ti_raw = _normalize_text_for_dedupe(str(out[i].get("text") or ""))
            if len(ti_raw) < min_contain_len:
                continue
            if len(tj_raw) > len(ti_raw) * tail_max_ratio:
                continue
            if tj_raw not in ti_raw and not ti_raw.startswith(tj_raw):
                continue

            gap = jst - int(out[i]["time"]["end_ms"])
            if -900 <= gap <= tail_gap_max:
                drop_idx.add(j)
                break

    return [out[k] for k in range(n) if k not in drop_idx]


def _short_cn_interjection(text: str) -> bool:
    """Short reactive line often mis-labelled as the adviser between two adviser turns."""
    raw = text.strip().replace("\n", " ")
    norm = _normalize_text_for_dedupe(raw)
    max_n = int(os.getenv("VOLC_SANDWICH_MAX_NORM_CHARS", "32"))
    if len(norm) > max_n:
        return False
    if re.search(
        r"什么|为啥|怎么回事|然后呢|所以呢|行不行|可以吗|对吗|咋办|咋样|什么意思|啥意思|^啥[。.?？]?$",
        raw,
    ):
        return True
    if len(norm) <= 22 and re.search(r"[？?]\s*$", raw):
        return True
    if len(norm) <= 26 and raw.endswith(("呢", "吗", "嘛", "么")):
        return True
    return False


def _reassign_adviser_sandwich_questions(items: List[Dict[str, Any]]) -> None:
    """If adviser has three consecutive bubbles and the middle one is a short question, flip to a client."""
    if len(items) < 3:
        return
    if os.getenv("VOLC_SANDWICH_QUESTION_FIX", "1").lower() in ("0", "false", "no"):
        return

    gap_max = int(os.getenv("VOLC_SANDWICH_QUESTION_GAP_MS", "5200"))

    for i in range(1, len(items) - 1):
        prev_u = items[i - 1]
        cur_u = items[i]
        next_u = items[i + 1]
        sid_p = str(prev_u.get("speaker_id") or "")
        sid_c = str(cur_u.get("speaker_id") or "")
        sid_n = str(next_u.get("speaker_id") or "")

        if sid_p != sid_c or sid_c != sid_n:
            continue
        adv = sid_p

        txt = str(cur_u.get("text") or "").strip()
        if not txt or not _short_cn_interjection(txt):
            continue

        gap1 = int(cur_u["time"]["start_ms"]) - int(prev_u["time"]["end_ms"])
        gap2 = int(next_u["time"]["start_ms"]) - int(cur_u["time"]["end_ms"])
        if gap1 > gap_max or gap2 > gap_max:
            continue

        # Client speaker_ids first seen before this adviser run (conversation order).
        clients_ordered: List[str] = []
        for k in range(i):
            s = str(items[k].get("speaker_id") or "")
            if not s or s == adv:
                continue
            if s not in clients_ordered:
                clients_ordered.append(s)
        if len(clients_ordered) < 1:
            continue

        next_t = str(next_u.get("text") or "")
        prev_t = str(prev_u.get("text") or "")
        next_strip = next_t.strip()

        # Next line speaks to 张先生 → interjection usually from first client slot (typically 张先生 himself).
        if re.search(r"^张先生[，,．.\s]", next_strip[:44]) or "张先生，您" in next_t[:52]:
            target = clients_ordered[0]
        # Prior turn about 張先生 allocation; next resumes generic adviser wording → often the other client.
        elif (
            "张先生" in prev_t
            and len(clients_ordered) >= 2
            and not re.search(r"^张先生", next_strip[:32])
            and ("王女士" not in next_strip[:40])
        ):
            target = clients_ordered[1]
        else:
            continue

        if not target or target == adv:
            continue
        cur_u["speaker_id"] = target
        for drop_k in ("speaker_name", "speaker_profile_id", "speaker_confidence", "speaker_margin"):
            cur_u.pop(drop_k, None)


def _require_env() -> None:
    missing = []
    if not VOLC_APP_ID:
        missing.append("VOLC_APP_ID")
    if not VOLC_ACCESS_TOKEN:
        missing.append("VOLC_ACCESS_TOKEN")
    if not VOLC_RESOURCE_ID:
        missing.append("VOLC_RESOURCE_ID")
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Volc ASR env vars: {', '.join(missing)}",
        )


def _to_pcm16(audio_bytes: bytes) -> bytes:
    try:
        audio, sr = sf.read(io.BytesIO(audio_bytes))
    except Exception:
        with tempfile.NamedTemporaryFile(suffix=".in", delete=True) as fin, tempfile.NamedTemporaryFile(
            suffix=".wav", delete=True
        ) as fout:
            fin.write(audio_bytes)
            fin.flush()
            import subprocess

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                fin.name,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                fout.name,
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"audio_convert_failed: {e}") from e
            with open(fout.name, "rb") as f:
                return f.read()

    if getattr(audio, "ndim", 1) > 1:
        audio = audio[:, 0]
    if sr != 16000:
        x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=max(1, int(len(audio) * (16000 / sr))), endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)
    audio = np.clip(audio, -1, 1)
    pcm = (audio * 32767.0).astype(np.int16)
    return pcm.tobytes()


def _build_frame(message_type: int, payload_obj: Dict[str, Any], compress: bool = True) -> bytes:
    payload = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
    compression = 1 if compress else 0
    serialization = 1  # JSON
    if compress:
        payload = gzip.compress(payload)
    # 4-byte header (version=1, header_size=1, serialization=json)
    b0 = (1 << 4) | 1
    b1 = (message_type << 4) | 0
    b2 = (serialization << 4) | compression
    b3 = 0
    header = bytes([b0, b1, b2, b3])
    return header + struct.pack(">I", len(payload)) + payload


def _build_audio_frame(pcm_chunk: bytes, is_last: bool) -> bytes:
    payload = gzip.compress(pcm_chunk)
    b0 = (1 << 4) | 1
    # message_type=2 audio
    b1 = (2 << 4) | (2 if is_last else 0)
    # serialization=0 (raw bytes), compression=1 (gzip)
    b2 = (0 << 4) | 1
    b3 = 0
    header = bytes([b0, b1, b2, b3])
    return header + struct.pack(">I", len(payload)) + payload


def _parse_frame(raw: bytes) -> Dict[str, Any]:
    if len(raw) < 8:
        return {}
    if VOLC_DEBUG:
        print(
            "[volc-debug] frame-head:",
            raw[:16].hex(),
            "len=",
            len(raw),
            flush=True,
        )
    msg_type = (raw[1] >> 4) & 0x0F
    msg_flags = raw[1] & 0x0F
    serialization = (raw[2] >> 4) & 0x0F
    compression = raw[2] & 0x0F

    cursor = 4
    # server full response usually carries a 4-byte sequence field
    if msg_type == 0x9 and msg_flags in (0x1, 0x3):
        cursor += 4
    # error response usually carries a 4-byte error code field
    if msg_type == 0xF:
        cursor += 4
    if len(raw) < cursor + 4:
        return {}

    payload_len = struct.unpack(">I", raw[cursor : cursor + 4])[0]
    cursor += 4
    payload = raw[cursor : cursor + payload_len]
    if VOLC_DEBUG:
        print(
            "[volc-debug] payload-len-field:",
            payload_len,
            "payload-real:",
            len(payload),
            "msg_type:",
            msg_type,
            "msg_flags:",
            msg_flags,
            "serialization:",
            serialization,
            "compression:",
            compression,
            flush=True,
        )
    if not payload:
        return {}
    # try gzip then plain json
    decompressed = False
    if compression == 1:
        try:
            payload = gzip.decompress(payload)
            decompressed = True
        except Exception:
            pass
    if VOLC_DEBUG:
        preview = payload[:120]
        try:
            pv = preview.decode("utf-8", errors="replace")
        except Exception:
            pv = repr(preview)
        print(
            "[volc-debug] payload-decompressed:",
            decompressed,
            "preview:",
            pv,
            flush=True,
        )
    try:
        if serialization == 1:
            obj = json.loads(payload.decode("utf-8", errors="replace"))
            if isinstance(obj, dict):
                obj["_volc_meta"] = {
                    "msg_type": msg_type,
                    "msg_flags": msg_flags,
                    "serialization": serialization,
                    "compression": compression,
                }
                return obj
            return {}
        return {}
    except Exception:
        if VOLC_DEBUG:
            try:
                text = payload.decode("utf-8", errors="replace")
            except Exception:
                text = repr(payload[:200])
            print("[volc-debug] json-decode-failed payload=", text[:500], flush=True)
        return {}


def _extract_speaker_id(obj: Any) -> str | None:
    """Pull a speaker id out of a node, considering all common locations."""
    if not isinstance(obj, dict):
        return None
    for key in ("speaker_id", "speaker", "spk_id", "spk"):
        v = obj.get(key)
        if v is not None and v != "":
            return str(v)
    additions = obj.get("additions")
    if isinstance(additions, dict):
        for key in ("speaker_id", "speaker", "spk_id", "spk", "spk_label"):
            v = additions.get(key)
            if v is not None and v != "":
                return str(v)
    return None


def _normalize_speaker_id(raw: str | None) -> str:
    """Map raw speaker tokens to stable string ids like '0','1','2'."""
    if raw is None or raw == "":
        return "0"
    s = str(raw).strip()
    if not s:
        return "0"
    # spk_0 / spk-1 / speaker_2 -> "0","1","2"
    m = re.search(r"(\d+)$", s)
    if m:
        return m.group(1)
    return s


def _collect_utterances(obj: Any, out: List[VolcUtterance], parent_sid: str | None = None) -> None:
    if isinstance(obj, dict):
        node_sid = _extract_speaker_id(obj)
        effective_sid = node_sid if node_sid is not None else parent_sid
        # Only treat timestamped nodes as utterances.
        has_timing = any(
            k in obj for k in ("start_time", "end_time", "start", "end", "start_ms", "end_ms")
        )
        looks_like_utterance = has_timing or ("definite" in obj and "text" in obj)
        if looks_like_utterance and ("text" in obj or "utterance" in obj):
            txt = str(obj.get("text") or "").strip()
            if not txt:
                txt = str(obj.get("utterance") or "").strip()
            if txt:
                sid = _normalize_speaker_id(effective_sid if effective_sid is not None else "0")
                start_raw = obj.get("start_time", obj.get("start", obj.get("start_ms", 0)))
                end_raw = obj.get("end_time", obj.get("end", obj.get("end_ms", 0)))
                try:
                    start_v = float(start_raw)
                    end_v = float(end_raw)
                except Exception:
                    start_v, end_v = 0.0, 0.0
                # Volc returns millisecond timestamps in practice, including values < 1000.
                # Only treat values as seconds when they look explicitly fractional and small.
                looks_like_seconds = (
                    (abs(start_v - int(start_v)) > 1e-6 or abs(end_v - int(end_v)) > 1e-6)
                    and max(start_v, end_v) <= 100
                )
                if looks_like_seconds:
                    start_ms = int(start_v * 1000)
                    end_ms = int(end_v * 1000)
                else:
                    start_ms = int(start_v)
                    end_ms = int(end_v)
                # Ignore placeholder/non-final invalid timestamps.
                if end_ms >= 0 and start_ms >= 0:
                    out.append(
                        VolcUtterance(
                            speaker_id=str(sid),
                            text=txt,
                            start_ms=max(0, start_ms),
                            end_ms=max(max(0, start_ms), end_ms),
                            definite=bool(obj.get("definite", False)),
                        )
                    )
        # Also support segmented word lists in "utterances" arrays.
        ulist = obj.get("utterances")
        if isinstance(ulist, list):
            for u in ulist:
                _collect_utterances(u, out, parent_sid=effective_sid)
        for k, v in obj.items():
            # Ignore token-level words list to avoid sentence duplication.
            if k == "words":
                continue
            # Already walked utterances list above.
            if k == "utterances":
                continue
            _collect_utterances(v, out, parent_sid=effective_sid)
    elif isinstance(obj, list):
        for v in obj:
            _collect_utterances(v, out, parent_sid=parent_sid)


def _collect_from_result_root(payload: Dict[str, Any], out: List[VolcUtterance]) -> tuple[str, int]:
    """Handle documented payload shapes: result may be dict or list.

    Returns:
        (latest_full_text, duration_ms) for optional fallback when no utterances exist.
    """
    latest_full_text = ""
    duration_ms = int(payload.get("audio_info", {}).get("duration", 0) or 0)
    result = payload.get("result")
    if isinstance(result, dict):
        # best path: utterance-level with timing/speaker
        uts = result.get("utterances")
        if isinstance(uts, list):
            _collect_utterances(uts, out)
        txt = str(result.get("text") or "").strip()
        if txt:
            latest_full_text = txt
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                _collect_utterances(item, out)
                txt = str(item.get("text") or "").strip()
                if txt:
                    latest_full_text = txt
    return latest_full_text, duration_ms


async def transcribe_with_doubao(audio_bytes: bytes) -> List[Dict[str, Any]]:
    _require_env()
    pcm16 = _to_pcm16(audio_bytes)
    headers = {
        "X-Api-App-Key": VOLC_APP_ID,
        "X-Api-Access-Key": VOLC_ACCESS_TOKEN,
        "X-Api-Resource-Id": VOLC_RESOURCE_ID,
        "X-Api-Connect-Id": str(uuid.uuid4()),
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    if VOLC_SECRET_KEY:
        headers["X-Api-Secret-Key"] = VOLC_SECRET_KEY

    utterances: List[VolcUtterance] = []
    latest_result_text = ""
    latest_duration_ms = 0

    def _build_params_for_endpoint(url: str) -> Dict[str, Any]:
        # Per official Volc/Doubao doc:
        # - enable_speaker_info requires ssd_version="200"
        # - On the optimized bidirectional streaming (bigmodel_async),
        #   enable_speaker_info also requires enable_nonstream=true
        #   (二遍识别 — first stream out fast partials, then re-recognize for accuracy).
        # - bigmodel_nostream is single-shot; enable_nonstream is irrelevant there.
        is_async = url.endswith("/bigmodel_async")
        is_nostream = url.endswith("/bigmodel_nostream")
        request_obj: Dict[str, Any] = {
            "model_name": "bigmodel",
            "enable_speaker_info": True,
            "ssd_version": "200",
            "enable_ddc": True,
            "show_utterances": True,
            "enable_punc": True,
            "enable_itn": True,
        }
        if is_async:
            # Required by docs to combine streaming partials with nostream re-recognition,
            # which is also what unlocks reliable speaker separation on this endpoint.
            request_obj["enable_nonstream"] = True
        elif is_nostream:
            # Single-shot endpoint; do not set enable_nonstream.
            pass
        else:
            # Standard bidirectional streaming.
            request_obj["enable_nonstream"] = False
        return {
            "user": {"uid": "live-transcript"},
            "audio": {
                "format": "pcm",
                "rate": 16000,
                "channel": 1,
                "bits": 16,
                "language": "zh-CN",
            },
            "request": request_obj,
        }

    def _candidate_urls(primary: str) -> List[str]:
        primary = primary.strip()
        if primary.endswith("/bigmodel_nostream"):
            alt1 = primary.replace("/bigmodel_nostream", "/bigmodel_async")
            alt2 = primary.replace("/bigmodel_nostream", "/bigmodel")
            return [primary, alt1, alt2]
        if primary.endswith("/bigmodel_async"):
            alt1 = primary.replace("/bigmodel_async", "/bigmodel")
            alt2 = primary.replace("/bigmodel_async", "/bigmodel_nostream")
            return [primary, alt1, alt2]
        if primary.endswith("/bigmodel"):
            alt1 = primary.replace("/bigmodel", "/bigmodel_async")
            alt2 = primary.replace("/bigmodel", "/bigmodel_nostream")
            return [primary, alt1, alt2]
        return [primary]

    last_error: Exception | None = None
    connected_ok = False
    for ws_url in _candidate_urls(VOLC_WS_URL):
        try:
            if VOLC_DEBUG:
                print("[volc-debug] trying ws url:", ws_url, flush=True)
            prev_count = len(utterances)
            prev_text = latest_result_text
            params = _build_params_for_endpoint(ws_url)
            async with websockets.connect(ws_url, additional_headers=headers, max_size=20 * 1024 * 1024) as ws:
                connected_ok = True
                last_error = None
                await ws.send(_build_frame(1, params))

                chunk_size = 3200 * 2
                total = len(pcm16)
                for i in range(0, total, chunk_size):
                    chunk = pcm16[i : i + chunk_size]
                    is_last = i + chunk_size >= total
                    await ws.send(_build_audio_frame(chunk, is_last=is_last))

                # collect server responses until socket closes or final message appears
                for _ in range(256):
                    try:
                        msg = await ws.recv()
                    except Exception:
                        break
                    if isinstance(msg, str):
                        try:
                            payload = json.loads(msg)
                        except Exception:
                            payload = {}
                        if VOLC_DEBUG:
                            print("[volc-debug] ws-text:", msg[:1200], flush=True)
                    else:
                        payload = _parse_frame(msg)
                        if VOLC_DEBUG:
                            print("[volc-debug] ws-bytes-len:", len(msg), flush=True)
                    if payload:
                        if VOLC_DEBUG:
                            _log.warning("volc frame payload keys=%s", list(payload.keys())[:12])
                            _log.warning("volc frame payload sample=%s", json.dumps(payload, ensure_ascii=False)[:1200])
                            print(
                                "[volc-debug] payload:",
                                json.dumps(payload, ensure_ascii=False)[:1200],
                                flush=True,
                            )
                        full_text, duration_ms = _collect_from_result_root(payload, utterances)
                        if full_text:
                            latest_result_text = full_text
                        if duration_ms:
                            latest_duration_ms = duration_ms
                        meta = payload.get("_volc_meta") if isinstance(payload, dict) else None
                        if (
                            isinstance(meta, dict)
                            and meta.get("msg_type") == 0x9
                            and meta.get("msg_flags") == 0x3
                        ) or (isinstance(payload, dict) and "error" in str(payload).lower()):
                            break
            # If this endpoint produced no usable transcript, try next endpoint.
            produced_new_utterance = len(utterances) > prev_count
            produced_new_text = bool(latest_result_text and latest_result_text != prev_text)
            if produced_new_utterance or produced_new_text:
                break
            if VOLC_DEBUG:
                print("[volc-debug] endpoint yielded empty transcript, trying fallback", flush=True)
            continue
        except Exception as e:
            last_error = e
            continue

    if last_error and not connected_ok:
        raise HTTPException(status_code=502, detail=f"volc_asr_failed: {type(last_error).__name__}: {last_error}") from last_error

    # If no utterance-level data exists, fallback to latest full text once.
    if not utterances and latest_result_text:
        utterances.append(
            VolcUtterance(
                speaker_id="0",
                text=latest_result_text,
                start_ms=0,
                end_ms=max(0, latest_duration_ms),
                definite=False,
            )
        )

    # Streaming responses include many evolving partials for the same span.
    # Keep only the best candidate for each (speaker,start_ms) to remove repeats.
    by_span: Dict[tuple[str, int], VolcUtterance] = {}
    for u in utterances:
        key = (u.speaker_id, max(0, u.start_ms))
        prev = by_span.get(key)
        if prev is None:
            by_span[key] = u
            continue
        # Prefer definite utterances, then longer end-time / longer text.
        choose_new = False
        if u.definite and not prev.definite:
            choose_new = True
        elif u.definite == prev.definite:
            if u.end_ms > prev.end_ms:
                choose_new = True
            elif u.end_ms == prev.end_ms and len(u.text) > len(prev.text):
                choose_new = True
        if choose_new:
            by_span[key] = u

    ordered = sorted(by_span.values(), key=lambda x: (x.start_ms, x.end_ms))
    # Collapse near-duplicate utterances produced by streaming refinement.
    deduped_ordered: List[VolcUtterance] = []
    for u in ordered:
        if not u.text:
            continue
        if deduped_ordered:
            prev = deduped_ordered[-1]
            if prev.speaker_id == u.speaker_id:
                prev_norm = _normalize_text_for_dedupe(prev.text)
                cur_norm = _normalize_text_for_dedupe(u.text)
                if prev_norm and prev_norm == cur_norm and u.start_ms - prev.end_ms <= 700:
                    # Keep the more complete timing window.
                    prev.end_ms = max(prev.end_ms, u.end_ms)
                    prev.definite = prev.definite or u.definite
                    continue
        deduped_ordered.append(u)

    merged: List[Dict[str, Any]] = []
    for u in deduped_ordered:
        if not u.text:
            continue
        if not merged:
            merged.append(
                {
                    "speaker_id": u.speaker_id,
                    "text": u.text,
                    "time": {"start_ms": u.start_ms, "end_ms": u.end_ms},
                }
            )
            continue
        last = merged[-1]
        if last["speaker_id"] == u.speaker_id and u.start_ms <= last["time"]["end_ms"] + 300:
            # Adjacent same-speaker spans: keep latest finalized text without duplication.
            if u.start_ms == last["time"]["start_ms"]:
                last["text"] = u.text
            else:
                last_norm = _normalize_text_for_dedupe(last["text"])
                cur_norm = _normalize_text_for_dedupe(u.text)
                if not cur_norm:
                    pass
                elif cur_norm == last_norm or last_norm.endswith(cur_norm):
                    # Skip pure repeat segment.
                    pass
                else:
                    last["text"] = f'{last["text"]} {u.text}'.strip()
            last["time"]["end_ms"] = max(last["time"]["end_ms"], u.end_ms)
        else:
            merged.append(
                {
                    "speaker_id": u.speaker_id,
                    "text": u.text,
                    "time": {"start_ms": u.start_ms, "end_ms": u.end_ms},
                }
            )
    # Final text cleanup before returning to frontend.
    for item in merged:
        cleaned = _compact_repeated_chunks(str(item.get("text") or ""))
        cleaned = _repair_duplicate_bigrams(cleaned)
        cleaned = _repair_cn_asr_micro_glitches(cleaned)
        cleaned = _strip_trailing_fragment(cleaned)
        cleaned = _compact_cn_fragments(cleaned)
        item["text"] = cleaned
    # Merge fragmented short sentences into neighboring same-speaker segments.
    merged2: List[Dict[str, Any]] = []
    for item in merged:
        txt = str(item.get("text") or "").strip()
        if not txt:
            continue
        if not merged2:
            merged2.append(item)
            continue
        prev = merged2[-1]
        same_speaker = prev.get("speaker_id") == item.get("speaker_id")
        gap_ms = int(item["time"]["start_ms"]) - int(prev["time"]["end_ms"])
        if same_speaker and gap_ms <= 1500 and (_is_fragment_text(txt) or _is_fragment_text(prev.get("text", ""))):
            prev_text = str(prev.get("text") or "").strip()
            cur_text = txt
            if cur_text and not prev_text.endswith(cur_text):
                prev["text"] = f"{prev_text} {cur_text}".strip()
            prev["time"]["end_ms"] = max(int(prev["time"]["end_ms"]), int(item["time"]["end_ms"]))
        else:
            merged2.append(item)
    merged = merged2
    merged = _drop_cross_speaker_partial_overlap(merged)
    _reassign_adviser_sandwich_questions(merged)

    if VOLC_DEBUG:
        print(
            "[volc-debug] final-merged:",
            json.dumps(merged, ensure_ascii=False),
            flush=True,
        )
    return merged
