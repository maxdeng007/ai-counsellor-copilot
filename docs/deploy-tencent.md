# Tencent Cloud Update Guide (max2ai.top)

How to deploy code changes from your Mac to the live **腾讯云 CVM** server.

For local development, see [`launch.md`](./launch.md).

---

## Architecture (your server)

```text
Internet
   │
   ▼
Nginx (:443 HTTPS)  →  https://max2ai.top
   ├── /              →  static files in /var/www/ai-counsellor-copilot/
   └── /api, /healthz →  FastAPI (diarization.service) on 127.0.0.1:8090
```

| Item | Value |
|------|--------|
| Public site | https://max2ai.top |
| SSH | `ssh ubuntu@124.222.38.73` |
| Git repo on server | `/home/ubuntu/apps/ai-counsellor-copilot` |
| Nginx web root | `/var/www/ai-counsellor-copilot` |
| Backend service | `diarization.service` |
| Backend env file | `/home/ubuntu/apps/ai-counsellor-copilot/diarization-service/.env` |
| GitHub remote | `maxdeng007/ai-counsellor-copilot` (`main`) |

**Important:** `npm run build` writes to `dist/` inside the project folder. Nginx does **not** read that path automatically — you must **rsync `dist/` into `/var/www/ai-counsellor-copilot/`** after every frontend build.

---

## Standard workflow

Always follow this order:

```text
Mac: fix + test locally
  ↓  git commit + git push
GitHub (origin/main)
  ↓  git pull on server
腾讯云 CVM: restart backend and/or sync frontend
```

Do **not** edit production `.env` on your Mac and expect it to affect the server. Secrets and provider keys live only in **`diarization-service/.env` on the CVM**.

---

## What kind of change did you make?

Use the table below, then run the matching commands on the **server** (after `git pull`).

| Change type | Examples | Server steps |
|-------------|----------|--------------|
| **Backend only** | `diarization-service/app/**`, Python logic, ASR/summary providers | `git pull` → restart `diarization.service` |
| **Frontend only** | `src/**`, Vue/CSS, UI copy | `git pull` → `npm run build` → rsync `dist/` → reload nginx |
| **Both** | Full feature touching API + UI | Backend steps + frontend steps |
| **Python deps** | `requirements.txt` changed | `git pull` → `pip install -r requirements.txt` → restart service |
| **Secrets / `.env` only** | MiMo key, Volc ASR keys, `SUMMARY_PROVIDER` | Edit server `.env` → restart service (no git pull needed) |
| **`VITE_*` build vars** | API base URL, feature flags baked into `dist/` | Set `.env.local` on server → rebuild frontend → rsync → reload nginx |

---

## Step 0 — Push from your Mac (required)

```bash
cd /Users/dengzhou/Desktop/Project/AI-record

git status
git add <files>
git commit -m "describe your change"
git push origin main
```

---

## Step 1 — SSH into the server

```bash
ssh ubuntu@124.222.38.73
```

If SSH fails (`Connection closed`), use **腾讯云控制台 → 云服务器 → 登录 → 标准登录方式** (web terminal).

---

## Step 2 — Pull latest code

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot
git pull origin main
```

---

## Backend update

Run when anything under `diarization-service/` changed (or `requirements.txt`).

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot

# If requirements.txt changed:
cd diarization-service
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Restart API (loads diarization-service/.env via systemd)
sudo systemctl restart diarization.service

# Verify
systemctl status diarization.service --no-pager
curl -s http://127.0.0.1:8090/healthz
curl -s https://max2ai.top/healthz
```

Expected health response: `{"ok":true,"mode":"doubao_streaming","service":"live-transcript"}`.

### Backend logs (when debugging)

```bash
sudo journalctl -u diarization.service -f
```

---

## Frontend update

Run when anything under `src/`, `public/`, or root frontend config changed.

### ⚠️ REQUIRED FIRST: `.env.local` must exist before every build

> **This is the #1 deploy footgun.** The API base URL is **baked into the bundle at build time**.
> If `.env.local` is missing when you run `npm run build`, the frontend code falls back to
> `http://localhost:8090` (see `src/views/LiveTranscript.vue`). The result:
> the site **works on your PC** (because your laptop happens to run a local backend on :8090)
> but is **completely broken on mobile** (no `localhost` on the phone). Always confirm `.env.local`
> exists in the **project root** (`/home/ubuntu/apps/ai-counsellor-copilot/.env.local`, **not** `~/`)
> before building.

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot

# Confirm it exists and is correct (must show the line below)
cat .env.local 2>/dev/null || echo "MISSING — create it now"
```

It must contain:

```bash
VITE_DIARIZATION_API_BASE=https://max2ai.top
VITE_USE_VOLC=true
```

If missing or wrong, (re)create it in the **project root**:

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot
cat > .env.local <<'EOF'
VITE_DIARIZATION_API_BASE=https://max2ai.top
VITE_USE_VOLC=true
EOF
```

This file is gitignored and lives only on the server, so it survives `git pull` but is **not** restored by it — never delete it.

### Build and publish

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot

npm install          # if package.json / lockfile changed
npm run build

# Copy built assets to nginx web root
sudo rsync -av --delete dist/ /var/www/ai-counsellor-copilot/

sudo systemctl reload nginx
```

### Verify the live bundle

Always run all three checks after a frontend deploy:

```bash
NEW=$(curl -s https://max2ai.top/ | grep -o 'index-[^"]*\.js')
echo "bundle: $NEW"
curl -s "https://max2ai.top/assets/$NEW" | grep -c 'http://localhost:8090'        # want 0
curl -s "https://max2ai.top/assets/$NEW" | grep -o 'https://max2ai.top' | head -1 # want the domain
```

Expected:

- the hash **changed** vs your previous deploy (proves nginx serves the new build)
- `localhost:8090` count is **0** (proves `.env.local` was picked up)
- `https://max2ai.top` is printed (the baked API origin)

If the hash didn't change, nginx serves the wrong directory — see [Troubleshooting](#troubleshooting).
If `localhost:8090` count is **not 0**, you built without `.env.local` — recreate it (above) and rebuild.

---

## Full update (backend + frontend)

Copy-paste block for a typical release:

```bash
cd /home/ubuntu/apps/ai-counsellor-copilot
git pull origin main

# Backend
cd diarization-service
source .venv/bin/activate
pip install -r requirements.txt
cd ..
sudo systemctl restart diarization.service

# Frontend — REQUIRED: confirm .env.local exists first (else build bakes localhost)
cat .env.local || { echo "MISSING .env.local — see Frontend update section"; exit 1; }
npm install
npm run build
sudo rsync -av --delete dist/ /var/www/ai-counsellor-copilot/
sudo systemctl reload nginx

# Smoke checks
curl -s https://max2ai.top/healthz
NEW=$(curl -s https://max2ai.top/ | grep -o 'index-[^"]*\.js'); echo "bundle: $NEW"
curl -s "https://max2ai.top/assets/$NEW" | grep -c 'http://localhost:8090'   # want 0
git log -1 --oneline
```

---

## Update secrets only (no code deploy)

```bash
ssh ubuntu@124.222.38.73
nano /home/ubuntu/apps/ai-counsellor-copilot/diarization-service/.env
sudo systemctl restart diarization.service
curl -s http://127.0.0.1:8090/healthz
```

Keep Volc ASR keys and summary provider keys (`SUMMARY_PROVIDER`, `MIMO_*`, etc.) on the server only. Never commit real keys.

---

## Browser verification

After deploy:

1. Open https://max2ai.top in a **private/incognito tab** (avoids cached old JS).
2. Confirm **实时 (Live)** mode (not 演示 Demo).
3. **Record → Stop → Reviewing** (ASR / Volc path).
4. **Link client → Summarize** (summary / MiMo path).

On phone: mic access requires **HTTPS** (already configured for max2ai.top).

---

## Troubleshooting

### Site shows old UI after `npm run build`

**Symptom:** `curl https://max2ai.top/` references an old `index-*.js` filename.

**Cause:** Build output stayed in `~/apps/.../dist/` but nginx serves `/var/www/ai-counsellor-copilot/`.

**Fix:**

```bash
sudo rsync -av --delete /home/ubuntu/apps/ai-counsellor-copilot/dist/ /var/www/ai-counsellor-copilot/
sudo systemctl reload nginx
```

Confirm nginx root:

```bash
sudo nginx -T 2>/dev/null | grep -E 'server_name|root ' | grep -B1 -A1 max2ai
# Should show: root /var/www/ai-counsellor-copilot;
```

### Works on PC but recording is dead on mobile (or PC is janky)

**Symptom:** Recording works on your desktop but does nothing on the phone; desktop feels slow/janky.

**Cause:** The bundle was built **without `.env.local`**, so the API base fell back to `http://localhost:8090`. Your PC has a local backend on :8090 (so it silently works), but the phone has no `localhost` → every request fails.

**Confirm:**

```bash
NEW=$(curl -s https://max2ai.top/ | grep -o 'index-[^"]*\.js')
curl -s "https://max2ai.top/assets/$NEW" | grep -c 'http://localhost:8090'   # if > 0, this is the bug
```

**Fix:** create `.env.local` in the project root (see [Frontend update](#frontend-update)), then rebuild + rsync + reload. Recheck — the count must be `0`.

### “AI Service temporarily unavailable” on Stop

**Symptom:** Toast after stopping recording in Live mode.

**Check:**

```bash
curl -s https://max2ai.top/healthz
sudo journalctl -u diarization.service -n 50 --no-pager
```

Common causes: Volc ASR credentials in server `.env`, `VOLC_RESOURCE_ID` mismatch, or (local dev only) SOCKS proxy env vars interfering with Doubao WebSocket — fixed in code via direct connection (`proxy=None`).

### Summary works but Live ASR fails (or vice versa)

| Feature | Config |
|---------|--------|
| Live ASR | `VOLC_*` in `diarization-service/.env` |
| Meeting summary | `SUMMARY_PROVIDER` + provider keys (`MIMO_*`, `OPENAI_*`, `VOLC_ARK_*`) |

These are independent; update and restart once after any `.env` edit.

### `nano` fails over SSH (“Error opening terminal”)

Use the Tencent Cloud web console editor, or:

```bash
vi /path/to/file
```

Or edit with `sed` for small changes.

---

## Quick reference card

```bash
# --- Backend only ---
cd /home/ubuntu/apps/ai-counsellor-copilot && git pull origin main
sudo systemctl restart diarization.service

# --- Frontend only ---
cd /home/ubuntu/apps/ai-counsellor-copilot && git pull origin main
npm run build
sudo rsync -av --delete dist/ /var/www/ai-counsellor-copilot/
sudo systemctl reload nginx

# --- Check live version ---
curl -s https://max2ai.top/healthz
curl -s https://max2ai.top/ | grep -o 'index-[^"]*\.js'
```
