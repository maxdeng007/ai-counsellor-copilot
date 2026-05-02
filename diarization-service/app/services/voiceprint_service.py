from __future__ import annotations

import io
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf


VOICEPRINT_DB_PATH = Path(
    os.getenv(
        "VOICEPRINT_DB_PATH",
        str(Path(__file__).resolve().parents[2] / "data" / "voiceprints.json"),
    )
)
VOICEPRINT_MATCH_THRESHOLD = float(os.getenv("VOICEPRINT_MATCH_THRESHOLD", "0.82"))
VOICEPRINT_MIN_IDENTIFY_MS = int(os.getenv("VOICEPRINT_MIN_IDENTIFY_MS", "900"))
VOICEPRINT_SHORT_UTTERANCE_MS = int(os.getenv("VOICEPRINT_SHORT_UTTERANCE_MS", "1600"))
VOICEPRINT_STRONG_MATCH_THRESHOLD = float(os.getenv("VOICEPRINT_STRONG_MATCH_THRESHOLD", "0.9"))
VOICEPRINT_MIN_MARGIN = float(os.getenv("VOICEPRINT_MIN_MARGIN", "0.035"))
VOICEPRINT_SMOOTH_GAP_MS = int(os.getenv("VOICEPRINT_SMOOTH_GAP_MS", "1200"))
VOICEPRINT_TARGET_SR = 16000
SESSION_VOICEPRINT_MATCH_THRESHOLD = float(os.getenv("SESSION_VOICEPRINT_MATCH_THRESHOLD", "0.80"))
SESSION_VOICEPRINT_STRONG_MATCH_THRESHOLD = float(os.getenv("SESSION_VOICEPRINT_STRONG_MATCH_THRESHOLD", "0.88"))
SESSION_VOICEPRINT_MIN_MARGIN = float(os.getenv("SESSION_VOICEPRINT_MIN_MARGIN", "0.025"))
SESSION_VOICEPRINT_MIN_IDENTIFY_MS = int(os.getenv("SESSION_VOICEPRINT_MIN_IDENTIFY_MS", "550"))
SESSION_VOICEPRINT_MAX_SPEAKERS = int(os.getenv("SESSION_VOICEPRINT_MAX_SPEAKERS", "6"))
SESSION_VOICEPRINT_EXPIRE_SECONDS = int(os.getenv("SESSION_VOICEPRINT_EXPIRE_SECONDS", "1800"))

_lock = threading.Lock()


@dataclass
class _SessionSpeaker:
    speaker_id: str
    feature: np.ndarray
    sample_count: int = 1
    updated_at: float = field(default_factory=time.time)


@dataclass
class _SessionVoiceprints:
    next_index: int = 1
    speakers: Dict[str, _SessionSpeaker] = field(default_factory=dict)
    raw_to_stable: Dict[str, str] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


_session_voiceprints: Dict[str, _SessionVoiceprints] = {}


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n <= 1e-9:
        return vec
    return vec / n


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio.astype(np.float32, copy=False)
    if audio.size == 0:
        return np.zeros((0,), dtype=np.float32)
    x_old = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=max(1, int(audio.size * (dst_sr / src_sr))), endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _decode_to_mono(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    wav, sr = sf.read(io.BytesIO(audio_bytes))
    if getattr(wav, "ndim", 1) > 1:
        wav = wav[:, 0]
    mono = np.asarray(wav, dtype=np.float32)
    return mono, int(sr)


def _extract_feature(audio: np.ndarray, sample_rate: int) -> Optional[np.ndarray]:
    if audio.size < int(0.6 * sample_rate):
        return None
    x = _resample(audio, sample_rate, VOICEPRINT_TARGET_SR)
    if x.size < int(0.6 * VOICEPRINT_TARGET_SR):
        return None
    x = np.clip(x, -1.0, 1.0)
    x = x - float(np.mean(x))
    rms = float(np.sqrt(np.mean(x * x) + 1e-9))
    if rms < 1e-4:
        return None
    x = x / rms

    # Lightweight spectral fingerprint: mel-like log-band energies + dynamics.
    frame = int(0.025 * VOICEPRINT_TARGET_SR)  # 25ms
    hop = int(0.010 * VOICEPRINT_TARGET_SR)  # 10ms
    if x.size < frame:
        return None
    win = np.hanning(frame).astype(np.float32)
    frames = []
    for i in range(0, x.size - frame + 1, hop):
        seg = x[i : i + frame] * win
        mag = np.abs(np.fft.rfft(seg, n=512)).astype(np.float32)
        frames.append(mag)
    if not frames:
        return None
    spec = np.stack(frames, axis=0)  # [T, F]
    spec = np.log1p(spec)

    # 24 coarse frequency bands.
    n_bands = 24
    n_bins = spec.shape[1]
    band_edges = np.linspace(0, n_bins, num=n_bands + 1, dtype=int)
    band_means = []
    for b in range(n_bands):
        lo = band_edges[b]
        hi = max(lo + 1, band_edges[b + 1])
        band_means.append(np.mean(spec[:, lo:hi], axis=1))
    band_energy = np.stack(band_means, axis=1)  # [T, B]

    mean = np.mean(band_energy, axis=0)
    std = np.std(band_energy, axis=0)
    delta = np.mean(np.abs(np.diff(band_energy, axis=0)), axis=0) if band_energy.shape[0] > 1 else np.zeros_like(mean)

    # Extra robust cues.
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0))
    p95 = float(np.percentile(np.abs(x), 95))
    feat = np.concatenate([mean, std, delta, np.array([zcr, p95], dtype=np.float32)]).astype(np.float32)
    return _l2_normalize(feat)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return -1.0
    denom = (float(np.linalg.norm(a)) * float(np.linalg.norm(b))) + 1e-9
    if denom <= 0:
        return -1.0
    return float(np.dot(a, b) / denom)


def _cleanup_session_voiceprints_locked() -> None:
    now = time.time()
    stale = [
        sid
        for sid, state in _session_voiceprints.items()
        if now - state.updated_at > SESSION_VOICEPRINT_EXPIRE_SECONDS
    ]
    for sid in stale:
        _session_voiceprints.pop(sid, None)


def clear_session_voiceprints(session_id: str) -> bool:
    """Drop live-only speaker fingerprints for a recording session."""
    if not session_id:
        return False
    with _lock:
        return _session_voiceprints.pop(str(session_id), None) is not None


def _get_session_voiceprints_locked(session_id: str) -> _SessionVoiceprints:
    _cleanup_session_voiceprints_locked()
    key = str(session_id)
    state = _session_voiceprints.get(key)
    if state is None:
        state = _SessionVoiceprints()
        _session_voiceprints[key] = state
    state.updated_at = time.time()
    return state


def _assign_session_speaker_locked(
    state: _SessionVoiceprints,
    raw_speaker_id: str,
    feat: Optional[np.ndarray],
) -> Tuple[str, float]:
    """Map Volc per-request speaker ids to stable live-session speaker ids."""
    raw_key = str(raw_speaker_id or "")
    mapped = state.raw_to_stable.get(raw_key)
    if mapped and mapped in state.speakers:
        # Keep per-commit raw cluster continuity unless we have strong evidence to move.
        speaker = state.speakers[mapped]
        if feat is not None:
            merged = (speaker.feature * speaker.sample_count + feat) / (speaker.sample_count + 1)
            speaker.feature = _l2_normalize(merged.astype(np.float32))
            speaker.sample_count += 1
            speaker.updated_at = time.time()
        return mapped, 0.72 if feat is not None else 0.5

    def _new_speaker(confidence: float) -> Tuple[str, float]:
        stable_id = f"session_spk_{state.next_index}"
        state.next_index += 1
        state.speakers[stable_id] = _SessionSpeaker(
            speaker_id=stable_id,
            feature=feat if feat is not None else np.zeros((74,), dtype=np.float32),
            sample_count=1,
        )
        if raw_key:
            state.raw_to_stable[raw_key] = stable_id
        return stable_id, confidence

    if feat is None:
        if not raw_key:
            # No reliable raw speaker id and no acoustic feature: keep unknown.
            return "unknown_live", 0.0
        # No embedding: preserve raw cluster diversity (avoid collapsing everything to dominant speaker).
        if raw_key and len(state.speakers) < SESSION_VOICEPRINT_MAX_SPEAKERS:
            return _new_speaker(0.42)
        if state.speakers:
            stable = max(state.speakers.values(), key=lambda sp: sp.sample_count).speaker_id
            if raw_key:
                state.raw_to_stable[raw_key] = stable
            return stable, 0.45

    best_id = ""
    best_score = -1.0
    second_score = -1.0
    if feat is not None:
        for sid, speaker in state.speakers.items():
            score = _cosine(feat, speaker.feature)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_id = sid
            elif score > second_score:
                second_score = score

    margin = max(0.0, best_score - second_score)
    confident_match = (
        bool(best_id)
        and best_score >= SESSION_VOICEPRINT_MATCH_THRESHOLD
        and (
            margin >= SESSION_VOICEPRINT_MIN_MARGIN
            or best_score >= SESSION_VOICEPRINT_STRONG_MATCH_THRESHOLD
        )
    )

    if confident_match:
        speaker = state.speakers[best_id]
        if feat is not None:
            merged = (speaker.feature * speaker.sample_count + feat) / (speaker.sample_count + 1)
            speaker.feature = _l2_normalize(merged.astype(np.float32))
            speaker.sample_count += 1
            speaker.updated_at = time.time()
        if raw_key:
            state.raw_to_stable[raw_key] = best_id
        return best_id, float(best_score)

    if feat is None and state.speakers:
        fallback = max(state.speakers.values(), key=lambda sp: sp.sample_count).speaker_id
        if raw_key:
            state.raw_to_stable[raw_key] = fallback
        return fallback, 0.45

    if len(state.speakers) >= SESSION_VOICEPRINT_MAX_SPEAKERS and best_id:
        speaker = state.speakers[best_id]
        if feat is not None:
            merged = (speaker.feature * speaker.sample_count + feat) / (speaker.sample_count + 1)
            speaker.feature = _l2_normalize(merged.astype(np.float32))
            speaker.sample_count += 1
            speaker.updated_at = time.time()
        if raw_key:
            state.raw_to_stable[raw_key] = best_id
        return best_id, float(best_score)

    if raw_key and len(state.speakers) < SESSION_VOICEPRINT_MAX_SPEAKERS:
        # For unseen raw cluster ids, prefer creating a provisional distinct speaker
        # over forcing a weak similarity merge.
        return _new_speaker(0.58 if feat is not None else 0.42)

    return _new_speaker(0.6 if feat is not None else 0.4)


def _load_db() -> Dict[str, Any]:
    if not VOICEPRINT_DB_PATH.exists():
        return {"profiles": []}
    try:
        return json.loads(VOICEPRINT_DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": []}


def _save_db(db: Dict[str, Any]) -> None:
    VOICEPRINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    VOICEPRINT_DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def list_profiles() -> List[Dict[str, Any]]:
    with _lock:
        db = _load_db()
        out = []
        for p in db.get("profiles", []):
            out.append(
                {
                    "profile_id": p.get("profile_id"),
                    "display_name": p.get("display_name"),
                    "sample_count": int(p.get("sample_count", 0) or 0),
                    "updated_at": float(p.get("updated_at", 0) or 0),
                }
            )
        return out


def delete_profile(profile_id: str) -> bool:
    with _lock:
        db = _load_db()
        arr = db.get("profiles", [])
        kept = [p for p in arr if str(p.get("profile_id")) != str(profile_id)]
        changed = len(kept) != len(arr)
        if changed:
            db["profiles"] = kept
            _save_db(db)
        return changed


def enroll_profile(audio_bytes: bytes, display_name: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    mono, sr = _decode_to_mono(audio_bytes)
    feat = _extract_feature(mono, sr)
    if feat is None:
        raise ValueError("audio_too_short_or_too_noisy")
    now = time.time()
    with _lock:
        db = _load_db()
        profiles = db.setdefault("profiles", [])
        pid = (profile_id or "").strip() or f"vp_{uuid.uuid4().hex[:10]}"
        existing = None
        for p in profiles:
            if str(p.get("profile_id")) == pid:
                existing = p
                break
        if existing is None:
            existing = {
                "profile_id": pid,
                "display_name": display_name.strip() or pid,
                "feature": feat.tolist(),
                "sample_count": 1,
                "created_at": now,
                "updated_at": now,
            }
            profiles.append(existing)
        else:
            old = np.asarray(existing.get("feature", []), dtype=np.float32)
            if old.size == feat.size and old.size > 0:
                n = int(existing.get("sample_count", 1) or 1)
                merged = _l2_normalize((old * n + feat) / (n + 1))
                existing["feature"] = merged.tolist()
                existing["sample_count"] = n + 1
            else:
                existing["feature"] = feat.tolist()
                existing["sample_count"] = int(existing.get("sample_count", 0) or 0) + 1
            if display_name.strip():
                existing["display_name"] = display_name.strip()
            existing["updated_at"] = now
        _save_db(db)
        return {
            "profile_id": existing["profile_id"],
            "display_name": existing["display_name"],
            "sample_count": int(existing.get("sample_count", 0) or 0),
        }


def identify_segment(audio_bytes: bytes) -> Optional[Dict[str, Any]]:
    mono, sr = _decode_to_mono(audio_bytes)
    feat = _extract_feature(mono, sr)
    if feat is None:
        return None
    return _identify_from_feature(feat)


def link_session_utterances(
    session_id: str,
    audio_bytes: bytes,
    utterances: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Assign stable live-session speaker ids across independent Volc commits.

    Volc speaker ids are local to each request, so a one-speaker slice often returns
    "0" even if that voice is the third person globally. This uses the same lightweight
    voiceprint feature extractor as persistent profiles, but stores centroids only in
    memory for the current recording session.
    """
    sid = str(session_id or "").strip()
    if not sid or not utterances:
        return utterances

    mono, sr = _decode_to_mono(audio_bytes)
    out: List[Dict[str, Any]] = []
    min_len_ms = max(300, int(SESSION_VOICEPRINT_MIN_IDENTIFY_MS))
    raw_ids = {str((u or {}).get("speaker_id") or "") for u in utterances if isinstance(u, dict)}
    raw_reliable = len([r for r in raw_ids if r]) >= 2

    with _lock:
        state = _get_session_voiceprints_locked(sid)
        for u in utterances:
            item = dict(u)
            t = item.get("time") if isinstance(item.get("time"), dict) else {}
            start_ms = int(t.get("start_ms", 0) or 0)
            end_ms = int(t.get("end_ms", start_ms) or start_ms)
            raw_speaker_id = str(item.get("speaker_id") or "")
            link_raw_id = raw_speaker_id if raw_reliable else ""

            feat: Optional[np.ndarray] = None
            if end_ms - start_ms >= min_len_ms:
                i0 = max(0, int((start_ms / 1000.0) * sr))
                i1 = min(mono.size, int((end_ms / 1000.0) * sr))
                if i1 > i0:
                    feat = _extract_feature(mono[i0:i1], sr)

            stable_id, confidence = _assign_session_speaker_locked(state, link_raw_id, feat)
            item["raw_speaker_id"] = raw_speaker_id
            item["speaker_id"] = stable_id
            if stable_id.startswith("session_spk_"):
                item["speaker_name"] = f"Speaker {stable_id.rsplit('_', 1)[-1]}"
            else:
                item["speaker_name"] = "Unconfirmed speaker"
            item["speaker_confidence"] = round(float(confidence), 4)
            item["speaker_scope"] = "session"
            out.append(item)

        state.updated_at = time.time()
    return out


def _identify_from_feature(feat: np.ndarray) -> Optional[Dict[str, Any]]:
    with _lock:
        db = _load_db()
        best = None
        best_score = -1.0
        second_score = -1.0
        for p in db.get("profiles", []):
            f = np.asarray(p.get("feature", []), dtype=np.float32)
            if f.size != feat.size or f.size == 0:
                continue
            score = _cosine(feat, f)
            if score > best_score:
                second_score = best_score
                best_score = score
                best = p
            elif score > second_score:
                second_score = score
        if best is None or best_score < VOICEPRINT_MATCH_THRESHOLD:
            return None
        margin = max(0.0, float(best_score - second_score))
        if margin < VOICEPRINT_MIN_MARGIN and best_score < VOICEPRINT_STRONG_MATCH_THRESHOLD:
            return None
        return {
            "profile_id": str(best.get("profile_id")),
            "display_name": str(best.get("display_name") or best.get("profile_id") or "Unknown"),
            "confidence": float(best_score),
            "margin": margin,
        }


def identify_utterances(audio_bytes: bytes, utterances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mono, sr = _decode_to_mono(audio_bytes)
    out: List[Dict[str, Any]] = []
    min_len_ms = max(300, int(VOICEPRINT_MIN_IDENTIFY_MS))
    for u in utterances:
        item = dict(u)
        t = item.get("time") if isinstance(item.get("time"), dict) else {}
        s = int(t.get("start_ms", 0) or 0)
        e = int(t.get("end_ms", s) or s)
        if e - s < min_len_ms:
            out.append(item)
            continue
        i0 = max(0, int((s / 1000.0) * sr))
        i1 = min(mono.size, int((e / 1000.0) * sr))
        if i1 <= i0:
            out.append(item)
            continue
        buf = io.BytesIO()
        sf.write(buf, mono[i0:i1], sr, format="WAV", subtype="PCM_16")
        ident = identify_segment(buf.getvalue())
        if ident:
            # For very short phrases (e.g. "什么意思？"), require stronger evidence
            # before overriding diarization speaker to reduce speaker swaps.
            dur_ms = max(0, e - s)
            conf = float(ident.get("confidence", 0.0) or 0.0)
            if dur_ms < VOICEPRINT_SHORT_UTTERANCE_MS and conf < VOICEPRINT_STRONG_MATCH_THRESHOLD:
                out.append(item)
                continue
            item["speaker_profile_id"] = ident["profile_id"]
            item["speaker_name"] = ident["display_name"]
            item["speaker_confidence"] = round(conf, 4)
            item["speaker_margin"] = round(float(ident.get("margin", 0.0) or 0.0), 4)
            # Override speaker id with persistent profile id for UI stability.
            item["speaker_id"] = ident["profile_id"]
        out.append(item)

    # NOTE: previously we ran a "neighbor-majority smoothing" pass here that
    # reassigned a short middle turn to the flanking speaker when both flanks
    # matched. That hurt accuracy because Volc's two-pass diarization often
    # already correctly puts a brief interjection on the *other* speaker, and
    # the pass would force it back. We trust Volc's speaker_id here and let
    # the volc_asr_service post-processing handle remaining edge cases.
    for i, cur in enumerate(out):
        if i <= 0 or i >= len(out) - 1:
            continue
        t = cur.get("time") if isinstance(cur.get("time"), dict) else {}
        s = int(t.get("start_ms", 0) or 0)
        e = int(t.get("end_ms", s) or s)
        dur = max(0, e - s)
        if dur > VOICEPRINT_SHORT_UTTERANCE_MS:
            continue
        if cur.get("speaker_profile_id"):
            continue
        prev = out[i - 1]
        nxt = out[i + 1]
        prev_sid = str(prev.get("speaker_id", ""))
        next_sid = str(nxt.get("speaker_id", ""))
        cur_sid = str(cur.get("speaker_id", ""))
        # Only "smooth" when this short turn was already collapsed into the
        # same speaker as both flanks — i.e. nothing actually changes. Keeps
        # the hook for future logic without overriding a real speaker.
        if not prev_sid or prev_sid != next_sid or prev_sid != cur_sid:
            continue
        pt = prev.get("time") if isinstance(prev.get("time"), dict) else {}
        nt = nxt.get("time") if isinstance(nxt.get("time"), dict) else {}
        pe = int(pt.get("end_ms", 0) or 0)
        ns = int(nt.get("start_ms", 0) or 0)
        if s - pe > VOICEPRINT_SMOOTH_GAP_MS:
            continue
        if ns - e > VOICEPRINT_SMOOTH_GAP_MS:
            continue
        cur["speaker_id"] = prev_sid
        if prev.get("speaker_name"):
            cur["speaker_name"] = prev.get("speaker_name")
    return out
