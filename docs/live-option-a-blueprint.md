# Live Option A Blueprint (Phase Plan)

Status: approved direction, implementation pending.

Goal: productize Live mode by extending from transcript-only to full workflow:

`idle -> recording -> processing -> reviewing -> linking -> summarized`

## 1) Current constraints (accepted)

- Storage: use IndexedDB temporarily (company production storage pending).
- Client linker: use `MOCK_CLIENTS` temporarily (company CRM integration pending).
- LLM summary provider: use OpenAI key for testing (swap to company API later).

These constraints are intentional and keep progress unblocked.

## 2) Scope for Option A

### A1. Live post-stop workflow

- Extend `src/views/LiveTranscript.vue` state machine to include:
  - `reviewing`
  - `linking`
  - `summarized`
- Reuse existing components from Demo path:
  - `src/components/ClientLinker.vue`
  - `src/components/SummaryPanel.vue`
- Keep transcript/bubble rendering pipeline from Live path untouched.

### A2. Summary generation

- Add backend summary endpoint in `diarization-service`:
  - `POST /api/summarize-meeting`
- Use OpenAI as current summary provider via backend (never expose key in frontend).
- Return strict JSON matching the existing Summary panel shape.

### A3. Temporary persistence

- Save meeting records to IndexedDB in browser:
  - draft after transcript finalization
  - updated after client link
  - final after summary ready
- Include `schemaVersion` from day one for future migration safety.

## 3) Adapter boundaries (future-proofing)

Define stable interfaces now so future migration is swap-only:

- `ClientRepository`
  - now: `MOCK_CLIENTS`
  - later: company CRM API
- `MeetingRepository`
  - now: IndexedDB
  - later: company storage
- `SummaryProvider`
  - now: OpenAI
  - later: company official LLM API

## 4) Proposed file-level changes

### Frontend

- `src/views/LiveTranscript.vue`
  - extend state machine and transitions
  - open linker after reviewing
  - call summarize API after link
  - persist records through repository
- `src/App.vue`
  - pass locale into Live view (if needed by reused components)
- New service wrappers:
  - `src/services/clientRepo.js`
  - `src/services/meetingRepo.js`
  - `src/services/summaryClient.js`
- New IndexedDB utility:
  - `src/db/indexeddb.js`

### Backend (`diarization-service`)

- `app/main.py`
  - add `POST /api/summarize-meeting`
  - optional: add `POST /api/extract-entities` for linker prefill
- New service/schema modules:
  - `app/services/summary_provider.py`
  - `app/services/entity_extractor.py` (optional first pass)
  - `app/schemas/summary_schema.py`

## 5) Data contracts (must lock before coding)

- Final transcript payload:
  - session id, locale, duration, speakers, segments
- Extracted client payload:
  - detected name, confidence, hint, candidate IDs
- Summary payload:
  - match existing `SummaryPanel` shape exactly
  - include zh/en fields currently expected by UI
- Saved meeting record:
  - id, timestamps, schemaVersion, status, transcript, linked client, aiOutput

## 6) Delivery sequence

1. A1.0: add repository/service scaffolding (no UX changes yet)
2. A1.1: wire post-stop extraction + reviewing/linking transitions
3. A1.2: persist flow states to IndexedDB
4. A2.0: backend OpenAI summary endpoint with strict JSON validation
5. A2.1: render `SummaryPanel` from real backend output
6. A2.2: zh/en parity and degraded fallback UX

## 7) Verification checklist

- Record in Live mode and stop successfully.
- Reviewing state appears with transcript intact.
- Linker opens, selects a client, and applies names to bubbles.
- Summary analyzes then renders with real generated content.
- Refresh retains the latest saved state via IndexedDB.
- Backend summary failure falls back to safe degraded UX (no hard crash).

## 8) Out of scope for this phase

- Company production storage integration
- Company CRM integration
- Company official LLM provider integration
- Multi-meeting history page (can be next phase)
- Compliance workflow hardening (consent/audit/residency)

## 9) Handoff note

When company APIs are available, keep UI and state machine unchanged. Only replace:

- repository adapters (`clientRepo`, `meetingRepo`)
- summary provider implementation (`summary_provider`)

This preserves delivery speed and reduces regression risk.
