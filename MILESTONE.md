# Milestone · Live transcript core (multi-segment MVP)

_A polished in-app recording experience: keep the conversation thread, stabilize speakers across takes, and stay focused on what’s streaming._

---

## What shipped

### Multi-session transcripts (append, never erase)

Stopping a recording and starting again **no longer wipes** prior bubbles or plain-text lines. Earlier dialogue stays visible; each new capture **continues beneath** what you already have.

### Segment boundaries you can scan

Whenever you press Record after **Transcript ready**, the UI inserts a clear **segment divider**—labeled **New recording** with a timestamp—in **Speaker** view, and a matching separator line in **Simple** view. Long sessions read as chapters, not one blur.

### Speaker palette that remembers you

Speaker colors and labels **carry forward** across segments instead of restarting from scratch each time—so returning to the mic feels continuous, not like a blank slate.

### Honest numbering under Volc churn

Underlying ASR passes can assign **new internal speaker IDs** per commit or refresh; we **prune** unused speaker slots and **renumber** plain auto labels (`Speaker 1`, `Speaker 2`, …) so the UI doesn’t creep into misleading “Speaker 5” clutter. Speakers from **finished** segments stay **fixed**—no surprise relabel of history.

### Final & refresh scoped to “this clip”

Full-file refresh and stop-time finalize **replace only the active segment**, not your whole thread. Dividers and prior segments stay untouched.

### Transcript pane that follows the moment

While you’re recording, processing, or the live caption is active, the **Transcript** panel **scrolls to the tail** automatically so **Live transcribing** stays in view as text grows—without hijacking scroll when you’re quietly reviewing finished text.

---

## Scope (explicit)

| In scope | Out of scope (this milestone) |
|----------|-------------------------------|
| In-memory transcript + speaker UI | Backend / IndexedDB persistence |
| Plain text + segmented bubbles only | Persisting raw audio |
| Stability & continuity across taps | Enrollment-voice-print perfection (future tuning) |

---

## Where it lives (code)

Changes center on **`src/views/LiveTranscript.vue`** (segment indices, divider nodes, prune/renumber helpers, transcript scroll pinning) alongside existing **`SpeakerBubble`**, **`LiveCaption`**, and the **diarization / Volc** pipeline you already wired.

---

## Closing note

This milestone turns “one-off capture” into a **conversation surface**: multiple takes, one thread, sane speakers, and an always-visible tail while you speak. Iterate from here toward persistence or richer linking when you’re ready.

---

## Next stage blueprint

Option A implementation blueprint is documented in `docs/live-option-a-blueprint.md`.
