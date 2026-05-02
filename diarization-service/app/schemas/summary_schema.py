from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SummaryKeyValue(BaseModel):
    k: str = ""
    v: str = ""


class SummarySection(BaseModel):
    labelZh: str = ""
    labelEn: str = ""
    rowsZh: List[SummaryKeyValue] = Field(default_factory=list)
    rowsEn: List[SummaryKeyValue] = Field(default_factory=list)


class SummaryRisk(BaseModel):
    labelZh: str = ""
    labelEn: str = ""
    levelZh: str = ""
    levelEn: str = ""
    targetZh: str = ""
    targetEn: str = ""


class SummaryAction(BaseModel):
    id: str
    textZh: str = ""
    textEn: str = ""
    dueZh: str = ""
    dueEn: str = ""


class SummaryOutput(BaseModel):
    summaryZh: str = ""
    summaryEn: str = ""
    profile: SummarySection = Field(default_factory=SummarySection)
    assets: SummarySection = Field(default_factory=SummarySection)
    risk: SummaryRisk = Field(default_factory=SummaryRisk)
    topicsZh: List[str] = Field(default_factory=list)
    topicsEn: List[str] = Field(default_factory=list)
    actions: List[SummaryAction] = Field(default_factory=list)
    emailDraftZh: str = ""
    emailDraftEn: str = ""


class TranscriptSegment(BaseModel):
    speakerId: str
    startMs: int = 0
    endMs: int = 0
    text: str = ""


class TranscriptSpeaker(BaseModel):
    id: str
    displayName: str = ""
    color: str = ""


class TranscriptPayload(BaseModel):
    sessionId: str = ""
    locale: str = "zh"
    durationMs: int = 0
    speakers: List[TranscriptSpeaker] = Field(default_factory=list)
    segments: List[TranscriptSegment] = Field(default_factory=list)


class LinkedClientPayload(BaseModel):
    id: str = ""
    nameZh: str = ""
    nameEn: str = ""
    industryZh: str = ""
    industryEn: str = ""


class SummarizeMeetingRequest(BaseModel):
    sessionId: str = ""
    locale: str = "zh"
    linkedClient: LinkedClientPayload = Field(default_factory=LinkedClientPayload)
    transcript: TranscriptPayload = Field(default_factory=TranscriptPayload)


class SummarizeMeetingResponse(BaseModel):
    ok: bool = True
    degraded: bool = False
    provider: str = "openai"
    aiOutput: SummaryOutput = Field(default_factory=SummaryOutput)


class ExtractedClient(BaseModel):
    nameZh: str = ""
    nameEn: str = ""
    hintZh: str = ""
    hintEn: str = ""
    matchClientId: str = ""
    confidence: float = 0.0


class ExtractEntitiesResponse(BaseModel):
    extractedClient: ExtractedClient = Field(default_factory=ExtractedClient)
    candidateClientIds: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)

