<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 'idle' | 'recording' | 'processing' | 'reviewing' | 'linking' | 'summarizing' | 'summarized'
  state: { type: String, default: 'idle' },
  elapsedSeconds: { type: Number, default: 0 },
  labels: { type: Object, required: true },
  // v2: when true, render without card chrome (border + shadow) so the dock
  // can sit at the bottom of the transcript card without looking like a
  // second card.
  inline: { type: Boolean, default: false },
  // 0..1, used by parent to drive the processing progress bar.
  processingProgress: { type: Number, default: 0 },
})

const emit = defineEmits(['toggle'])

const isRecording = computed(() => props.state === 'recording')
const isProcessing = computed(() => props.state === 'processing')
// Mic stays available for multi-round capture.
// We only lock during states where a transition is in-flight or mandatory modal
// interaction is open.
const isLocked = computed(() => ['processing', 'linking', 'summarizing'].includes(props.state))
const isDisabled = computed(() => isLocked.value)

const hint = computed(() => {
  if (isRecording.value) return props.labels.hintRecording
  if (isProcessing.value) return props.labels.hintProcessing ?? props.labels.hintStopped
  if (isLocked.value) return props.labels.hintStopped
  return props.labels.hintIdle
})

const ariaLabel = computed(() => (isRecording.value ? props.labels.ariaStop : props.labels.ariaStart))

const progressStyle = computed(() => {
  const scale = Math.max(0, Math.min(1, props.processingProgress))
  return { '--progress-scale': String(scale) }
})
</script>

<template>
  <div
    class="record-bar"
    :class="{
      'record-bar--inline': inline,
      'record-bar--recording': isRecording,
      'record-bar--processing': isProcessing,
      'record-bar--locked': isLocked && !isProcessing,
    }"
  >
    <div v-if="!inline" class="record-meta">
      <template v-if="isRecording">
        <div class="record-hint record-hint--recording">
          {{ hint }}
        </div>
      </template>
      <template v-else-if="isProcessing">
        <div class="processing-stack">
          <div class="processing-tag-row">
            <span class="processing-spinner" />
            <span class="processing-tag">{{ labels.processing ?? 'Finalizing…' }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="progressStyle" />
          </div>
        </div>
      </template>
      <template v-else>
        <div class="record-hint" :class="{ 'record-hint--stopped': isLocked }">
          {{ hint }}
        </div>
      </template>
    </div>

    <button
      type="button"
      class="mic-button"
      :class="{
        'mic-button--recording': isRecording,
        'mic-button--locked': isLocked,
      }"
      :aria-label="ariaLabel"
      :disabled="isDisabled"
      @click="emit('toggle')"
    >
      <span class="mic-ring mic-ring--1" />
      <span class="mic-ring mic-ring--2" />
      <span class="mic-ring mic-ring--3" />
      <span class="mic-core">
        <svg
          v-if="!isRecording"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          class="mic-icon"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="9" y="3" width="6" height="12" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0" />
          <path d="M12 18v3" />
        </svg>
        <span v-else class="stop-square" />
      </span>
    </button>
  </div>
</template>

<style scoped>
.record-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 14px 24px -22px rgba(28, 25, 23, 0.12);
  transition: border-color 0.4s ease, box-shadow 0.4s ease, background 0.4s ease;
}

/* v2: when the dock sits inside the transcript card, drop the card chrome and
   become a flat bottom bar with a hairline divider on top. */
.record-bar--inline {
  border: none;
  border-top: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: none;
  padding: 12px 16px;
  justify-content: center;
}

.record-bar--recording {
  border-color: rgba(244, 63, 94, 0.18);
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 14px 24px -22px rgba(225, 29, 72, 0.26);
}

.record-bar--inline.record-bar--recording {
  border: none;
  border-top: 1px solid rgba(244, 63, 94, 0.14);
  background: var(--color-surface);
  box-shadow: none;
}

.record-bar--processing {
  border-color: rgba(99, 102, 241, 0.22);
}

.record-bar--inline.record-bar--processing {
  border: none;
  border-top: 1px solid rgba(99, 102, 241, 0.18);
  background: var(--color-surface);
}

.record-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: row;
  gap: 16px;
}

.processing-stack {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.processing-tag-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-accent-text);
}

.processing-spinner {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 1.5px solid rgba(13, 61, 92, 0.22);
  border-top-color: var(--color-accent);
  animation: processing-spin 0.9s linear infinite;
}

@keyframes processing-spin {
  to { transform: rotate(360deg); }
}

.processing-tag {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.record-hint {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.record-hint--stopped {
  color: var(--color-accent-text);
  font-weight: 600;
}

.record-hint--recording {
  color: var(--color-text-secondary);
  font-weight: 600;
}

.progress-track {
  width: 100%;
  height: 6px;
  background: var(--color-accent-soft);
  border-radius: 999px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent-strong), var(--color-accent));
  border-radius: 999px;
  transform-origin: left center;
  transform: scaleX(var(--progress-scale, 0));
  transition: transform 0.1s linear;
  box-shadow: 0 0 6px rgba(13, 61, 92, 0.25);
}

.progress-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  background-size: 60% 100%;
  background-repeat: no-repeat;
  animation: progress-shimmer 1.4s ease-in-out infinite;
}

@keyframes progress-shimmer {
  0% { background-position: -50% 0; }
  100% { background-position: 150% 0; }
}

.mic-button {
  position: relative;
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: grid;
  place-items: center;
  isolation: isolate;
  -webkit-tap-highlight-color: transparent;
}

/* The full chrome size is reserved for the standalone variant. Inline shrinks
   slightly so it doesn't dominate the transcript card footer. */
.record-bar:not(.record-bar--inline) .mic-button {
  width: 76px;
  height: 76px;
}

.mic-button::before,
.mic-button::after {
  content: '';
  position: absolute;
  inset: 14px;
  border-radius: 999px;
  border: 1.5px solid rgba(13, 61, 92, 0.35);
  pointer-events: none;
  opacity: 0;
  transform: scale(0.9);
}

.mic-button:not(.mic-button--recording):not(.mic-button--locked)::before,
.mic-button:not(.mic-button--recording):not(.mic-button--locked)::after {
  animation: mic-ripple 2.6s ease-out infinite;
}

.mic-button:not(.mic-button--recording):not(.mic-button--locked)::after {
  animation-delay: 1.3s;
}

.mic-button--recording::before,
.mic-button--recording::after,
.mic-button--locked::before,
.mic-button--locked::after {
  display: none;
}

.mic-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mic-core {
  position: relative;
  z-index: 3;
  width: 46px;
  height: 46px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: linear-gradient(165deg, var(--color-accent) 0%, var(--color-accent-strong) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    inset 0 -3px 9px rgba(0, 0, 0, 0.15),
    0 8px 22px -8px rgba(13, 61, 92, 0.42),
    0 0 0 2px var(--color-warm-ring);
  transition: transform 0.18s ease, background 0.3s ease, box-shadow 0.3s ease;
}

.record-bar:not(.record-bar--inline) .mic-core {
  width: 54px;
  height: 54px;
}

.mic-icon {
  width: 20px;
  height: 20px;
  color: var(--color-on-accent);
}

.record-bar:not(.record-bar--inline) .mic-icon {
  width: 22px;
  height: 22px;
}

.stop-square {
  display: block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--color-on-accent);
}

.record-bar:not(.record-bar--inline) .stop-square {
  width: 16px;
  height: 16px;
}

.mic-button:hover:not(:disabled):not(.mic-button--recording):not(.mic-button--locked) .mic-core {
  transform: scale(1.04);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.26),
    inset 0 -3px 9px rgba(0, 0, 0, 0.15),
    0 14px 32px -8px rgba(13, 61, 92, 0.48),
    0 0 0 2px var(--color-warm-ring);
}

.mic-button:active:not(:disabled) .mic-core {
  transform: scale(0.94);
}

.mic-button--recording .mic-core {
  background: #f43f5e;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    inset 0 -3px 8px rgba(0, 0, 0, 0.16),
    0 8px 16px -10px rgba(225, 29, 72, 0.42);
}

.mic-button--locked .mic-core {
  background: #94a3b8;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.4),
    inset 0 -4px 10px rgba(0, 0, 0, 0.1),
    0 6px 14px -8px rgba(15, 23, 42, 0.3);
}

.mic-ring {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  pointer-events: none;
}

.mic-ring--1 {
  background: radial-gradient(circle at 50% 50%, rgba(13, 61, 92, 0.22), transparent 70%);
}

.mic-button--recording .mic-ring--1 {
  background: radial-gradient(circle at 50% 50%, rgba(225, 29, 72, 0.28), transparent 70%);
}

.mic-button--locked .mic-ring--1 {
  background: radial-gradient(circle at 50% 50%, rgba(148, 163, 184, 0.18), transparent 70%);
}

.mic-ring--2,
.mic-ring--3 {
  opacity: 0;
}

.mic-button--recording .mic-ring--2 {
  animation: mic-pulse 1.8s ease-out infinite;
  background: radial-gradient(circle, rgba(225, 29, 72, 0.34) 0%, transparent 70%);
}

.mic-button--recording .mic-ring--3 {
  animation: mic-pulse 1.8s ease-out infinite;
  animation-delay: 0.9s;
  background: radial-gradient(circle, rgba(225, 29, 72, 0.24) 0%, transparent 70%);
}

@keyframes mic-pulse {
  0% { transform: scale(0.7); opacity: 0.6; }
  70% { transform: scale(1.4); opacity: 0; }
  100% { transform: scale(1.4); opacity: 0; }
}

@keyframes mic-ripple {
  0% { opacity: 0; transform: scale(0.88); }
  20% { opacity: 0.5; }
  100% { opacity: 0; transform: scale(1.9); }
}

.reveal-enter-active,
.reveal-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.reveal-enter-from,
.reveal-leave-to {
  opacity: 0;
  transform: translateY(-2px);
}
</style>
