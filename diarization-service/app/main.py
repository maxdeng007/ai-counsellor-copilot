from __future__ import annotations

import logging
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.schemas.summary_schema import (
    ExtractEntitiesResponse,
    SummarizeMeetingRequest,
    SummarizeMeetingResponse,
    TranscriptPayload,
)
from app.services.entity_extractor import extract_entities
from app.services.summary_provider import summarize_meeting
from app.services.volc_asr_service import transcribe_with_doubao
from app.services.voiceprint_service import (
    clear_session_voiceprints,
    delete_profile,
    enroll_profile,
    identify_utterances,
    link_session_utterances,
    list_profiles,
)


class VolcProcessResponse(BaseModel):
    utterances: List[dict]


class VolcPreviewResponse(BaseModel):
    text: str
    utterances: List[dict]


class VoiceprintProfile(BaseModel):
    profile_id: str
    display_name: str
    sample_count: int
    updated_at: float = 0.0


class VoiceprintEnrollResponse(BaseModel):
    profile_id: str
    display_name: str
    sample_count: int


class VoiceprintListResponse(BaseModel):
    profiles: List[VoiceprintProfile]


app = FastAPI(title="Live Transcript API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
_log = logging.getLogger("diarization-service")


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "mode": "doubao_streaming",
        "service": "live-transcript",
    }


@app.post("/api/process-voice-volc", response_model=VolcProcessResponse)
async def process_voice_volc(
    audio: UploadFile = File(..., alias="file"),
    sessionId: str = Form(""),
    mode: str = Form("final"),
) -> VolcProcessResponse:
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio payload")
    utterances = await transcribe_with_doubao(raw)
    try:
        utterances = identify_utterances(raw, utterances)
    except Exception:
        _log.exception("voiceprint identification failed; fallback to diarization-only labels")
    if sessionId and mode == "incremental":
        try:
            utterances = link_session_utterances(sessionId, raw, utterances)
        except Exception:
            _log.exception("session voiceprint linking failed; fallback to per-commit labels")
    elif mode == "refresh":
        # Keep Volc's current full-audio diarization snapshot for this refresh.
        pass
    elif sessionId and mode == "final":
        clear_session_voiceprints(sessionId)
    return VolcProcessResponse(utterances=utterances)


@app.post("/api/process-voice-volc-preview", response_model=VolcPreviewResponse)
async def process_voice_volc_preview(audio: UploadFile = File(..., alias="file")) -> VolcPreviewResponse:
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio payload")
    utterances = await transcribe_with_doubao(raw)
    latest = ""
    if utterances:
        latest = str(utterances[-1].get("text") or "").strip()
    return VolcPreviewResponse(text=latest, utterances=utterances)


@app.get("/api/voiceprint/profiles", response_model=VoiceprintListResponse)
def voiceprint_profiles() -> VoiceprintListResponse:
    return VoiceprintListResponse(profiles=[VoiceprintProfile(**p) for p in list_profiles()])


@app.post("/api/voiceprint/enroll", response_model=VoiceprintEnrollResponse)
async def voiceprint_enroll(
    audio: UploadFile = File(..., alias="file"),
    displayName: str = Form(""),
    profileId: str = Form(""),
) -> VoiceprintEnrollResponse:
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio payload")
    if not displayName.strip() and not profileId.strip():
        raise HTTPException(status_code=400, detail="displayName or profileId is required")
    try:
        data = enroll_profile(raw, display_name=displayName, profile_id=(profileId or None))
        return VoiceprintEnrollResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"voiceprint_enroll_failed: {type(e).__name__}") from e


@app.delete("/api/voiceprint/profiles/{profile_id}")
def voiceprint_delete(profile_id: str) -> dict:
    deleted = delete_profile(profile_id)
    return {"profile_id": profile_id, "deleted": bool(deleted)}


@app.on_event("startup")
def startup() -> None:
    _log.info("Starting in Doubao-only mode.")


@app.post("/api/extract-entities", response_model=ExtractEntitiesResponse)
def api_extract_entities(payload: TranscriptPayload) -> ExtractEntitiesResponse:
    return extract_entities(payload, locale=payload.locale)


@app.post("/api/summarize-meeting", response_model=SummarizeMeetingResponse)
def api_summarize_meeting(payload: SummarizeMeetingRequest) -> SummarizeMeetingResponse:
    data = summarize_meeting(payload)
    return SummarizeMeetingResponse(**data)
