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
- If transcript fails, check Volc env variables and backend logs. Match `VOLC_RESOURCE_ID` to the product enabled in your Volc console (often `volc.bigasr.sauc.duration` for the async big-model stream).
- Keep secrets only in local `.env` files; do not commit real keys.

## 7) Deploy updates to Tencent Cloud

Production site: https://max2ai.top — see **[`deploy-tencent.md`](./deploy-tencent.md)** for SSH, `git pull`, frontend rsync, backend restart, and troubleshooting.
