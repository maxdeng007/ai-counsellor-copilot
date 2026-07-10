# Launch Guide (Backend + Frontend)

Use this quick guide to relaunch the project locally.

## 1) Backend env setup (`diarization-service/.env`)

Required Volc ASR variables:

```bash
VOLC_APP_ID=...
VOLC_ACCESS_TOKEN=...
VOLC_SECRET_KEY=...
VOLC_RESOURCE_ID=volc.bigasr.sauc.durationc
VOLC_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
```

Meeting summary (pick **one** provider via `SUMMARY_PROVIDER`):

**OpenAI** (default; needs reachable `api.openai.com` or a proxy from your server):

```bash
SUMMARY_PROVIDER=openai
OPENAI_API_KEY=...
SUMMARY_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1
```

**OpenRouter** (any OpenAI-compatible model, including `:free` tier — set `OPENAI_BASE_URL` to OpenRouter and pick a model from `https://openrouter.ai/models`):

```bash
SUMMARY_PROVIDER=openai
OPENAI_API_KEY=sk-or-v1-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
SUMMARY_MODEL=openai/gpt-oss-20b:free
```

Free-tier notes (learned the hard way — see also § Troubleshooting below):

- OpenRouter's `:free` models are routed through various upstream providers (Venice, Cerebras, etc.). All free models on the same upstream share a **global per-account quota**, so picking a different `:free` model does **not** avoid a 429 if it routes through the same overloaded upstream.
- The frontend displays a "degraded" banner whenever the backend returns a placeholder summary (e.g. 429 from the upstream), so a 429 is visible immediately rather than silently showing an empty panel.
- Confirmed working free models for Chinese meeting summaries:
  - `openai/gpt-oss-20b:free` (recommended default — supports `structured_outputs`, returns bilingual JSON)
  - `google/gemma-4-26b-a4b-it:free` (supports `structured_outputs`, larger context)
  - `nvidia/nemotron-3-super-120b-a12b:free` (supports `structured_outputs`)
- Avoid: `qwen/qwen3-next-80b-a3b-instruct:free` — frequently rate-limited by upstream Venice (429 with `retry_after_seconds=29`); `nvidia/nemotron-3-ultra-550b-a55b:free` — does not support `response_format`.
- For zero rate-limit risk, use a paid model (e.g. `openai/gpt-4o-mini`) or your own OpenAI key.

**Volcano Ark / 豆包** (OpenAI-compatible Chat API; typical for mainland-hosted backends):

```bash
SUMMARY_PROVIDER=volc_ark
VOLC_ARK_API_KEY=...
VOLC_ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VOLC_ARK_MODEL_TIER=lite
# Or: VOLC_ARK_MODEL=ep-m-...
```

## 2) Start backend (Terminal A)

Use **one** Python install for the venv. If you use Miniconda/Anaconda `(base)` and plain `python -m venv`, you can end up with a broken mix: the venv’s `python` points at conda while `pyvenv.cfg` still references Homebrew (or the opposite). That produces `ValueError: failed to parse CPython sys.version` inside `platform.python_version()` and breaks `pip`, some HTTP clients, and ASR handlers.

**Recommended (macOS + Homebrew Python):** deactivate conda, remove the old venv, recreate with an explicit interpreter:

```bash
conda deactivate   # if you see "(base)" in the prompt
cd diarization-service
rm -rf .venv
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -c "import platform; print(platform.python_version())"   # should run without error
pip install -r requirements.txt
set -a && source .env && set +a
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

From repo root (generic `python`, only if `which python` is already the interpreter you want):

```bash
cd diarization-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

If `.venv` already exists and works:

```bash
cd diarization-service
source .venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

## 3) Start frontend (Terminal B)

From repo root:

```bash
npm run dev
```

## 4) Quick health checks

Backend:

```bash
curl http://localhost:8090/healthz
```

Expected result includes:

- `"ok": true`
- `"service": "live-transcript"`

Frontend:

- Open the local Vite URL shown in terminal (usually `http://localhost:5173`)
- Enter **Live** mode and run:
  - Record -> Stop -> Reviewing
  - Continue link client -> Summarizing -> Summarized

## 5) Common relaunch commands

Stop processes:

- press `Ctrl + C` in backend/frontend terminals

Relaunch:

```bash
# Terminal A
cd diarization-service
source .venv/bin/activate
set -a && source .env && set +a
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload

# Terminal B
cd ..
npm run dev
```

## 6) Notes

- The FastAPI app reads Volc/OpenAI settings from the process environment only (no automatic `.env` load in code). Use `set -a && source .env && set +a` from `diarization-service/` before `uvicorn`, or export variables another way you prefer.
- If summary does not generate, check `SUMMARY_PROVIDER` and keys in `diarization-service/.env` (`OPENAI_API_KEY` for OpenAI, `VOLC_ARK_API_KEY` for `volc_ark`).
- If the summary panel shows a **yellow "AI 分析暂不可用 · 当前为占位纪要"** banner with an error message underneath, the LLM call failed and the backend returned a placeholder. Common causes:
  1. `429 RateLimitError` from a free upstream (e.g. OpenRouter `:free` hitting Venice) → switch to a paid model or wait for the upstream's `retry_after_seconds`.
  2. `APIConnectionError` / `nodename nor servname provided` → `OPENAI_BASE_URL` host is unreachable from this machine (DNS / VPN / firewall). Verify with `curl -v $OPENAI_BASE_URL/models`.
  3. Pydantic `ValidationError` on the LLM response → the model's JSON shape doesn't match the schema. The backend now runs lenient coercion first, so most free-model quirks (e.g. `titleZh/descriptionZh` instead of `textZh/textEn`) are handled automatically. If you still see one, capture the raw content from the backend log and add a coercion rule in `_normalize_action_items` / `_coerce_mimo_summary_dict` in `diarization-service/app/services/summary_provider.py`.
- `uvicorn --reload` only watches `.py` files, not `.env`. After editing `.env` you must fully restart the backend (`Ctrl+C` and re-run `uvicorn`); otherwise the new env vars won't take effect.
- To capture raw LLM responses for debugging, temporarily set the `_log.error("DEBUG_RAW_LLM_CONTENT:\n%s", content)` line in `_chat_summary_json_schema` in `summary_provider.py`, restart, and grep the backend log.
- If transcript fails, check Volc env variables and backend logs. Match `VOLC_RESOURCE_ID` to the product enabled in your Volc console (often `volc.bigasr.sauc.duration` for the async big-model stream).
- Keep secrets only in local `.env` files; do not commit real keys.

## 7) Deploy updates to Tencent Cloud

Production site: https://max2ai.top — see **[`deploy-tencent.md`](./deploy-tencent.md)** for SSH, `git pull`, frontend rsync, backend restart, and troubleshooting.
