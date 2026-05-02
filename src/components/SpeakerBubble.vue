<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  speaker: { type: Object, required: true },
  text: { type: String, required: true },
  partial: { type: Boolean, default: false },
  /** Incremental / live commit copy; finalized after stop in Volc pipeline. */
  draft: { type: Boolean, default: false },
  /** Live draft mode: hide speaker identity until periodic/full finalize refresh. */
  draftPlain: { type: Boolean, default: false },
  timestamp: { type: String, default: '' },
  align: { type: String, default: 'left' },
  editable: { type: Boolean, default: true },
  // v3: When a chunk arrives from the backend, parent staggers each bubble's
  // entrance animation by this amount so the paragraph "lands" with a soft
  // sequential motion rather than appearing all at once.
  entranceDelayMs: { type: Number, default: 0 },
})

const emit = defineEmits(['rename'])

const isEditing = ref(false)
const draftName = ref('')
const inputRef = ref(null)

const PALETTE_KEYS = ['violet', 'emerald', 'amber', 'sky', 'rose']

/** Stable palette class for bubble / avatar CSS (light + dark in stylesheet). */
const paletteKey = computed(() => {
  const c = props.speaker.color
  return PALETTE_KEYS.includes(c) ? c : 'violet'
})
const displaySpeakerName = computed(() => (props.draft ? `${props.speaker.name}?` : props.speaker.name))
const speakerAriaLabel = computed(() => {
  const name = displaySpeakerName.value || 'Speaker'
  return name.length > 24 ? `${name.slice(0, 24)}…` : name
})

// Avatar shows a number ("1") while the speaker is anonymous, and a single
// CJK character ("理") or 1-2 Latin initials once the speaker is renamed.
const initials = computed(() => {
  const name = props.speaker.name?.trim?.() ?? ''
  if (!name) return '?'
  // If the parent passed an explicit short avatar (used during anonymous
  // phase, e.g. "1"/"2"/"3"), prefer it.
  if (props.speaker.avatarText) {
    const short = String(props.speaker.avatarText).trim()
    return short.length <= 2 ? short : short.slice(0, 2)
  }
  const cjk = /[\u4e00-\u9fa5]/
  if (cjk.test(name)) {
    return name.replace(/\s/g, '').slice(0, 1)
  }
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
})

// Brief flip animation when the speaker name changes (anonymous → real on
// link, or user manual rename).
const namePulseKey = ref(0)
watch(
  () => props.speaker?.name,
  (next, prev) => {
    if (prev && next && prev !== next) namePulseKey.value += 1
  },
)

// Same flip for the avatar character, in case it changes (e.g. "1" → "理").
const avatarPulseKey = ref(0)
watch(
  () => initials.value,
  (next, prev) => {
    if (prev && next && prev !== next) avatarPulseKey.value += 1
  },
)

const entranceStyle = computed(() => ({
  '--entrance-delay': `${props.entranceDelayMs}ms`,
}))

function startEdit() {
  if (!props.editable) return
  draftName.value = props.speaker.name
  isEditing.value = true
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function commitEdit() {
  const next = draftName.value.trim()
  if (next && next !== props.speaker.name) {
    emit('rename', next)
  }
  isEditing.value = false
}

function cancelEdit() {
  isEditing.value = false
}
</script>

<template>
  <div
    class="bubble-row"
    :class="[`bubble-row--${props.align}`, { 'bubble-row--draft-plain': props.draftPlain }]"
    :style="entranceStyle"
  >
    <button
      v-if="!props.draftPlain"
      type="button"
      class="avatar"
      :class="[`avatar--${paletteKey}`, { 'avatar--editable': props.editable }]"
      :aria-label="speakerAriaLabel"
      :disabled="!props.editable"
      @click="startEdit"
    >
      <span class="avatar-initials" :key="avatarPulseKey">{{ initials }}</span>
    </button>

    <div class="bubble-stack">
      <div v-if="!props.draftPlain" class="bubble-meta">
        <template v-if="isEditing">
          <input
            ref="inputRef"
            v-model="draftName"
            class="rename-input"
            maxlength="16"
            @keydown.enter.prevent="commitEdit"
            @keydown.esc.prevent="cancelEdit"
            @blur="commitEdit"
          />
        </template>
        <template v-else>
          <button
            type="button"
            class="speaker-name"
            :class="[`speaker-name--${paletteKey}`, { 'speaker-name--editable': props.editable }]"
            :key="namePulseKey"
            :disabled="!props.editable"
            @click="startEdit"
          >
            {{ displaySpeakerName }}
          </button>
        </template>

        <span v-if="timestamp" class="timestamp">{{ timestamp }}</span>
        <span v-if="draft" class="draft-pill">Draft · speaker tentative</span>
      </div>
      <div v-else class="bubble-meta bubble-meta--draft-plain">
        <span class="draft-pill">Live draft · speaker unconfirmed</span>
      </div>

      <div
        class="bubble"
        :class="[`bubble--${paletteKey}`, { 'bubble--partial': partial, 'bubble--draft': draft }]"
      >
        <span class="bubble-text">{{ text }}</span>
        <span v-if="partial" class="caret" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
  width: 100%;
}

.bubble-row--right {
  flex-direction: row-reverse;
}

.bubble-row--draft-plain {
  justify-content: flex-start;
}

.avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: none;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.02em;
  cursor: default;
  transition: transform 0.15s, background-color 0.45s ease, color 0.45s ease, box-shadow 0.45s ease;
  -webkit-tap-highlight-color: transparent;
}

.avatar--editable {
  cursor: pointer;
}

.avatar--editable:active {
  transform: scale(0.94);
}

.avatar:disabled {
  cursor: default;
}

.avatar-initials {
  line-height: 1;
  display: inline-block;
  max-width: 28px;
  overflow: hidden;
  text-overflow: clip;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  animation: name-flip 0.5s ease;
}

.bubble-stack {
  min-width: 0;
  max-width: calc(100% - 46px);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.bubble-row--right .bubble-stack {
  align-items: flex-end;
}

.bubble-row--draft-plain .bubble-stack {
  max-width: 100%;
  align-items: flex-start;
}

.bubble-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  padding: 0 6px;
}

.bubble-meta--draft-plain {
  padding: 0 2px;
}

.speaker-name {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: default;
  -webkit-tap-highlight-color: transparent;
  animation: name-flip 0.5s ease;
  text-transform: none;
  max-width: min(44vw, 200px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.speaker-name--editable {
  cursor: pointer;
  position: relative;
}

.speaker-name--editable:hover {
  opacity: 0.78;
}

.speaker-name--editable::after {
  content: '✎';
  margin-left: 4px;
  font-size: 9px;
  opacity: 0;
  transition: opacity 0.15s;
}

.speaker-name--editable:hover::after {
  opacity: 0.55;
}

@keyframes name-flip {
  0% { opacity: 0.0; transform: translateY(-3px); }
  60% { opacity: 1; transform: translateY(0); }
  100% { opacity: 1; }
}

.rename-input {
  border: none;
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  outline: 1.5px solid var(--color-border-strong);
  width: 120px;
  font-family: inherit;
}

.timestamp {
  font-size: 10px;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.bubble {
  position: relative;
  padding: 10px 14px 11px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.65;
  letter-spacing: 0.002em;
  color: #0f172a;
  transition:
    background 0.45s ease,
    border-color 0.45s ease,
    color 0.45s ease;
  word-break: break-word;
  max-width: 100%;
  border: 1px solid transparent;
}

/* ── Speaker palettes (light) ── */
.avatar--violet {
  background: #ede9fe;
  color: #6d28d9;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.1);
}
.bubble--violet {
  background: #f6f3ff;
  border-color: rgba(124, 58, 237, 0.14);
}
.speaker-name--violet {
  color: #6d28d9;
}
.bubble--violet .caret {
  background: #6d28d9;
}

.avatar--emerald {
  background: #d1fae5;
  color: #047857;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1);
}
.bubble--emerald {
  background: #f0faf4;
  border-color: rgba(16, 185, 129, 0.16);
}
.speaker-name--emerald {
  color: #047857;
}
.bubble--emerald .caret {
  background: #047857;
}

.avatar--amber {
  background: #fef3c7;
  color: #a16207;
  box-shadow: 0 0 0 2px rgba(180, 83, 9, 0.1);
}
.bubble--amber {
  background: #fbf5e6;
  border-color: rgba(180, 83, 9, 0.18);
}
.speaker-name--amber {
  color: #a16207;
}
.bubble--amber .caret {
  background: #a16207;
}

.avatar--sky {
  background: #e0f2fe;
  color: #0369a1;
  box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.1);
}
.bubble--sky {
  background: #f0f7fc;
  border-color: rgba(2, 132, 199, 0.16);
}
.speaker-name--sky {
  color: #0369a1;
}
.bubble--sky .caret {
  background: #0369a1;
}

.avatar--rose {
  background: #ffe4e6;
  color: #be123c;
  box-shadow: 0 0 0 2px rgba(190, 18, 60, 0.1);
}
.bubble--rose {
  background: #fdf2f4;
  border-color: rgba(190, 18, 60, 0.16);
}
.speaker-name--rose {
  color: #be123c;
}
.bubble--rose .caret {
  background: #be123c;
}

/* ── Dark theme: muted tints on charcoal (no pastel “light panels”) ── */
[data-theme="dark"] .avatar--violet {
  background: rgba(124, 58, 237, 0.28);
  color: #ddd6fe;
  box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.22);
}
[data-theme="dark"] .bubble--violet {
  background: rgba(124, 58, 237, 0.14);
  border-color: rgba(167, 139, 250, 0.28);
  color: var(--color-text-primary);
}
[data-theme="dark"] .speaker-name--violet {
  color: #c4b5fd;
}
[data-theme="dark"] .bubble--violet .caret {
  background: #a78bfa;
}

[data-theme="dark"] .avatar--emerald {
  background: rgba(16, 185, 129, 0.26);
  color: #a7f3d0;
  box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.2);
}
[data-theme="dark"] .bubble--emerald {
  background: rgba(16, 185, 129, 0.11);
  border-color: rgba(52, 211, 153, 0.26);
  color: var(--color-text-primary);
}
[data-theme="dark"] .speaker-name--emerald {
  color: #6ee7b7;
}
[data-theme="dark"] .bubble--emerald .caret {
  background: #34d399;
}

[data-theme="dark"] .avatar--amber {
  background: rgba(245, 158, 11, 0.24);
  color: #fde68a;
  box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.22);
}
[data-theme="dark"] .bubble--amber {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(251, 191, 36, 0.28);
  color: var(--color-text-primary);
}
[data-theme="dark"] .speaker-name--amber {
  color: #fcd34d;
}
[data-theme="dark"] .bubble--amber .caret {
  background: #fbbf24;
}

[data-theme="dark"] .avatar--sky {
  background: rgba(14, 165, 233, 0.26);
  color: #bae6fd;
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.22);
}
[data-theme="dark"] .bubble--sky {
  background: rgba(14, 165, 233, 0.11);
  border-color: rgba(56, 189, 248, 0.26);
  color: var(--color-text-primary);
}
[data-theme="dark"] .speaker-name--sky {
  color: #7dd3fc;
}
[data-theme="dark"] .bubble--sky .caret {
  background: #38bdf8;
}

[data-theme="dark"] .avatar--rose {
  background: rgba(244, 63, 94, 0.26);
  color: #fecdd3;
  box-shadow: 0 0 0 2px rgba(251, 113, 133, 0.22);
}
[data-theme="dark"] .bubble--rose {
  background: rgba(244, 63, 94, 0.11);
  border-color: rgba(251, 113, 133, 0.26);
  color: var(--color-text-primary);
}
[data-theme="dark"] .speaker-name--rose {
  color: #fda4af;
}
[data-theme="dark"] .bubble--rose .caret {
  background: #fb7185;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .avatar--violet {
    background: rgba(124, 58, 237, 0.28);
    color: #ddd6fe;
    box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.22);
  }
  :root:not([data-theme="light"]) .bubble--violet {
    background: rgba(124, 58, 237, 0.14);
    border-color: rgba(167, 139, 250, 0.28);
    color: var(--color-text-primary);
  }
  :root:not([data-theme="light"]) .speaker-name--violet {
    color: #c4b5fd;
  }
  :root:not([data-theme="light"]) .bubble--violet .caret {
    background: #a78bfa;
  }

  :root:not([data-theme="light"]) .avatar--emerald {
    background: rgba(16, 185, 129, 0.26);
    color: #a7f3d0;
    box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.2);
  }
  :root:not([data-theme="light"]) .bubble--emerald {
    background: rgba(16, 185, 129, 0.11);
    border-color: rgba(52, 211, 153, 0.26);
    color: var(--color-text-primary);
  }
  :root:not([data-theme="light"]) .speaker-name--emerald {
    color: #6ee7b7;
  }
  :root:not([data-theme="light"]) .bubble--emerald .caret {
    background: #34d399;
  }

  :root:not([data-theme="light"]) .avatar--amber {
    background: rgba(245, 158, 11, 0.24);
    color: #fde68a;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.22);
  }
  :root:not([data-theme="light"]) .bubble--amber {
    background: rgba(245, 158, 11, 0.1);
    border-color: rgba(251, 191, 36, 0.28);
    color: var(--color-text-primary);
  }
  :root:not([data-theme="light"]) .speaker-name--amber {
    color: #fcd34d;
  }
  :root:not([data-theme="light"]) .bubble--amber .caret {
    background: #fbbf24;
  }

  :root:not([data-theme="light"]) .avatar--sky {
    background: rgba(14, 165, 233, 0.26);
    color: #bae6fd;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.22);
  }
  :root:not([data-theme="light"]) .bubble--sky {
    background: rgba(14, 165, 233, 0.11);
    border-color: rgba(56, 189, 248, 0.26);
    color: var(--color-text-primary);
  }
  :root:not([data-theme="light"]) .speaker-name--sky {
    color: #7dd3fc;
  }
  :root:not([data-theme="light"]) .bubble--sky .caret {
    background: #38bdf8;
  }

  :root:not([data-theme="light"]) .avatar--rose {
    background: rgba(244, 63, 94, 0.26);
    color: #fecdd3;
    box-shadow: 0 0 0 2px rgba(251, 113, 133, 0.22);
  }
  :root:not([data-theme="light"]) .bubble--rose {
    background: rgba(244, 63, 94, 0.11);
    border-color: rgba(251, 113, 133, 0.26);
    color: var(--color-text-primary);
  }
  :root:not([data-theme="light"]) .speaker-name--rose {
    color: #fda4af;
  }
  :root:not([data-theme="light"]) .bubble--rose .caret {
    background: #fb7185;
  }
}

.bubble-row--left .bubble {
  border-top-left-radius: 4px;
}

.bubble-row--right .bubble {
  border-top-right-radius: 4px;
}

.bubble-text {
  white-space: pre-wrap;
}

.caret {
  display: inline-block;
  width: 2px;
  height: 14px;
  margin-left: 2px;
  vertical-align: text-bottom;
  border-radius: 1px;
  animation: caret-blink 1s step-end infinite;
}

@keyframes caret-blink {
  50% { opacity: 0; }
}

.draft-pill {
  flex-shrink: 0;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-warning-text);
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--color-warning) 30%, transparent);
  background: var(--color-warning-soft);
}

.bubble--draft {
  border-style: dashed;
  opacity: 0.94;
}
</style>
