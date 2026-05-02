# Counsellor Meeting Demo (v3) — product narrative

This file restores the **long-form Demo mode** UX and architecture notes from an earlier root `README` (before the GitHub-oriented README rewrite). Use it for **onboarding, PM/design review, and beta documentation**.

**Scope:** The **Demo** path uses mocked audio and scripted chunks. The app also supports **Live** mode (real mic + `diarization-service` + Volc); that pipeline is documented in the root `README`, `docs/launch.md`, and `diarization-service/README.md`.

---

# Counsellor Meeting Demo (v3)

A polished, fully-mocked demo of an **AI Financial Counsellor Meeting Assistant**.

v3 mirrors how the backend actually works: the audio stream is broken into
paragraph-sized **chunks** (silence-bounded by VAD), each chunk is sent to the
backend for ASR + speaker diarization, and the UI renders three things:

1. A **live caption** while a chunk is being captured — soft gray italic, with
   a `· 实时识别 / · Live transcribing` tag and a blinking cursor.
2. An **inter-chunk pill** (`正在分析这一段… / Analyzing this segment…`) while
   that chunk is being processed by the backend.
3. **Diarized speaker bubbles** when the chunk arrives, sliding in with a
   gentle stagger. Each speaker is anonymous (`说话人 1/2/3 · Speaker 1/2/3`)
   until the user links a client.

This is the honest version of the live story: the frontend shows what was
heard (the caption), and the backend's diarization decides who said what
once the chunk is closed.

## End-to-end flow

```text
idle → recording → processing → reviewing → linking → summarized
```

1. **Idle** — neutral header (date only, no client name). Single transcript
   card with the mic dock at the bottom.
2. **Recording** — for each chunk: a soft gray live caption block streams the
   raw transcribed text word-by-word; a brief `正在分析这一段…` pill shows
   while the backend processes; then the caption fades out and the chunk's
   diarized bubbles appear, staggered, with anonymous labels (`说话人 1/2/3`).
   The next chunk starts streaming immediately afterwards. Keep recording —
   chunks keep arriving until you stop.
3. **Processing** — Stop pressed. Any in-flight chunk is flushed (a final
   `正在分析…` pill, then bubbles), the dock shows a slim progress bar with a
   "Finalizing transcript" tag, and a `终稿已就绪 / Final transcript ready`
   toast appears.
4. **Reviewing** — bubbles still anonymous. The counsellor can rename a
   speaker if they want, or just continue.
5. **Linking** — required, non-dismissible modal. Detected client is
   prefilled. A small note inside the modal explains that the N detected
   speakers will be auto-attributed once the link is confirmed.
6. **After link** — every bubble flips from `说话人 N` to its real role
   (`理财顾问 / 客户·王女士 / 李太太`) with a name-flip animation. Header
   swaps to the linked client. Summary panel reveals client profile, asset
   snapshot, risk profile, topics, action items, and follow-up email draft.

## Demo scripts

- **Retirement planning** — 2 speakers, 3 chunks. Counsellor and Mrs. Wang
  alternate cleanly; bubbles flip to `理财顾问` / `客户·王女士` after link.
- **Family portfolio review** — 3 speakers, 3 chunks. Mrs. Li (`说话人 3`)
  emerges in the very first chunk, demonstrating that anonymous diarization
  is not capped at 2. After link, bubbles become `理财顾问` / `李先生` /
  `李太太`.

Switch between scripts via the `Switch Demo Script` pill in the header.

## Tech stack (demo UI)

- Vue 3 + Vite
- Tailwind CSS v4 (via `@tailwindcss/vite`)
- Vant 4 (Icon + showToast)
- animate.css

## Run locally

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## What is mocked vs real (Demo mode)

| Feature | This demo |
| --- | --- |
| Audio recording | Mocked (no microphone access) |
| Live caption streaming | Mocked (each chunk's raw text is typed into the caption block before being diarized) |
| Chunked ASR + diarization | Mocked (each script ships pre-grouped `chunks` with `processingMs` per chunk for the simulated backend latency) |
| Anonymous → real speaker flip | Real CSS animation triggered by data update on link |
| Cross-chunk speaker consistency | Mocked (segments carry stable `speakerId`s; in production this requires speaker-embedding matching across chunks) |
| AI summary | Mocked (pre-built per script, revealed after ~2.6s shimmer post-link) |
| Client extraction & matching | Mocked (each script has a fixed `extractedClient` + match against a fake CRM list of 5 clients) |
| ClientLinker modal | Real component logic — non-dismissible, two paths (link existing / create new) |
| Save | Real `localStorage` only |
| Copy email | Real clipboard API |
| Locale | Real (zh-CN / en) |

## Next iteration (intentionally NOT built yet)

> **Note:** The product has since added **Live** mode (real mic, Volc ASR, `diarization-service`). The bullets below are the **original Demo-centric** wishlist; some items are addressed in Live, while others (CRM, compliance UI, email send) may still be open.

- Real microphone capture (`MediaRecorder` + chunked audio upload at VAD
  silence boundaries)
- Real chunk-level ASR (Whisper / Paraformer / cloud)
- Real speaker diarization with cross-chunk speaker-embedding matching
  (pyannote / commercial) so 说话人 N stays the same person across chunks
- Real entity extraction and CRM matching
- **Compliance / consent UI** before recording (audit trail, residency,
  retention)
- Multi-meeting history view
- Real email send + CRM write-back
- Speaker merge/split affordances in reviewing (rename only, for now)
- Permission control and audit trail

## Architecture pointers

- `src/data/mockDialog.js` — scripts, mock CRM, helpers. Each script carries
  flat `segments` (with a single `speakerId` per turn) and a `chunks` array
  grouping segment indices into paragraphs with per-chunk `processingMs`
  latency. `anonymousSpeakerLabel(n, locale)` produces the temporary
  `说话人 N / Speaker N` label used during recording.
- `src/views/CounsellorMeeting.vue` — owns the state machine and the
  chunked playback driver: stream caption → analyzing pill → emit bubbles →
  next chunk. Stop mid-chunk flushes the in-flight paragraph cleanly.
  Linking triggers `applyRealNames()` which flips all speaker labels at
  once — the bubble watcher animates the swap.
- `src/components/LiveCaption.vue` — soft gray italic streaming caption
  block with `· 实时识别` tag and blinking cursor; switches to a blue
  shimmering `正在分析这一段…` pill while the backend processes; fades out
  before the chunk's bubbles land.
- `src/components/SpeakerBubble.vue` — entrance animation with parent-
  supplied stagger delay (per-chunk). The name-flip animation runs on every
  visible bubble when the parent renames the speaker (anonymous → real).
- `src/components/RecordButton.vue` — `inline` variant (no card chrome) for
  embedding inside the transcript card; `processing` state with a slim
  progress bar for the post-stop tail.
- `src/components/ClientLinker.vue` — non-dismissible modal, two tabs
  (existing / new), required step to reach the summary. Renders a small
  `N speakers detected — roles will be assigned automatically after linking`
  hint.
