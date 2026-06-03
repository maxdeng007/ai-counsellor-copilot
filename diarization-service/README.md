# Doubao Streaming Service

Near-realtime live transcript backend focused on Doubao/Volc ASR with
session-level voiceprint linking.

## Endpoints

- `POST /api/process-voice-volc` (multipart: `file`, optional `sessionId`, optional `mode`)
  - `mode=incremental` for per-commit updates while recording
  - `mode=refresh` for periodic full-audio refresh
  - `mode=final` at stop-time finalization
- `POST /api/process-voice-volc-preview` (multipart: `file`) for live caption preview text
- `POST /api/summarize-meeting` (JSON) — meeting summary; configure `SUMMARY_PROVIDER` (`openai` or `volc_ark`) in `.env`
- `GET /api/voiceprint/profiles`
- `POST /api/voiceprint/enroll`
- `DELETE /api/voiceprint/profiles/{profile_id}`
- `GET /healthz`

## Environment

- `VOLC_APP_ID`, `VOLC_ACCESS_TOKEN`, `VOLC_SECRET_KEY`
- `VOLC_RESOURCE_ID` (default `volc.seedasr.sauc.duration`)
- `VOLC_WS_URL` (default `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`)
- Summary: `SUMMARY_PROVIDER` (`xiaomi_mimo`, `openai`, or `volc_ark`) — see `.env.example` (personal default: MiMo)
- Voiceprint tuning vars in `app/services/voiceprint_service.py` (optional)

## Local run

```bash
cd diarization-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```
