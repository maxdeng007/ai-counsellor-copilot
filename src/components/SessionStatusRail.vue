<script setup>
import { computed } from 'vue'

/**
 * Persistent session-state rail.
 *
 * Renders a slim bar with a colored side strip + state dot + label so the
 * counsellor can always tell at a glance whether the session is idle, live,
 * processing, paused, or finished — even when the mic button has scrolled
 * out of view.
 *
 * `state` controls tone (idle / recording / paused / progress / success /
 * danger). `label` is the human-readable status; `subLabel` is an optional
 * secondary line. `elapsed` is shown only while recording.
 */
const props = defineProps({
  state: { type: String, default: 'idle' },
  label: { type: String, default: '' },
  subLabel: { type: String, default: '' },
  elapsed: { type: String, default: '' },
  pendingChunks: { type: Number, default: 0 },
  locale: { type: String, default: 'en' },
  /** When true, rail uses tighter padding for inline use inside cards. */
  compact: { type: Boolean, default: false },
  /** Flat style for placement inside hero headers — no floating card shadow. */
  embedded: { type: Boolean, default: false },
  /** Inline pill: one line, minimal height — for hero eyebrow row. */
  capsule: { type: Boolean, default: false },
})

const tone = computed(() => {
  switch (props.state) {
    case 'recording':
      return 'recording'
    case 'paused':
      return 'warning'
    case 'processing':
    case 'summarizing':
    case 'linking':
      return 'progress'
    case 'reviewing':
    case 'summarized':
      return 'success'
    case 'error':
    case 'danger':
      return 'danger'
    default:
      return 'idle'
  }
})

const defaultLabel = computed(() => {
  const zh = props.locale === 'zh'
  switch (props.state) {
    case 'recording':
      return zh ? '正在录制' : 'Recording'
    case 'paused':
      return zh ? '已暂停' : 'Paused'
    case 'processing':
      return zh ? '终稿处理中' : 'Finalizing'
    case 'reviewing':
      return zh ? '终稿已就绪' : 'Transcript ready'
    case 'linking':
      return zh ? '正在关联客户' : 'Linking client'
    case 'summarizing':
      return zh ? 'AI 分析中' : 'AI analyzing'
    case 'summarized':
      return zh ? '会谈摘要已生成' : 'Summary ready'
    case 'error':
      return zh ? '出现问题' : 'Something went wrong'
    default:
      return zh ? '准备就绪' : 'Ready'
  }
})

const displayLabel = computed(() => props.label || defaultLabel.value)

const pendingHint = computed(() => {
  if (props.pendingChunks <= 0) return ''
  const zh = props.locale === 'zh'
  return zh
    ? `${props.pendingChunks} 段处理中`
    : `${props.pendingChunks} segment${props.pendingChunks > 1 ? 's' : ''} in flight`
})

const subText = computed(() => props.subLabel || pendingHint.value)
</script>

<template>
  <div
    class="status-rail"
    :class="[
      `status-rail--${tone}`,
      {
        'status-rail--compact': compact && !capsule,
        'status-rail--embedded': embedded && !capsule,
        'status-rail--capsule': capsule,
      },
    ]"
    role="status"
    aria-live="polite"
  >
    <div
      class="status-rail__indicator"
      :class="{ 'status-rail__indicator--capsule': capsule }"
      aria-hidden="true"
    >
      <span
        v-if="capsule && tone === 'recording'"
        class="status-rail__wave"
        aria-hidden="true"
      >
        <span class="status-rail__wave-bar" />
        <span class="status-rail__wave-bar" />
        <span class="status-rail__wave-bar" />
        <span class="status-rail__wave-bar" />
        <span class="status-rail__wave-bar" />
      </span>
      <span v-else class="status-rail__dot" />
    </div>
    <div class="status-rail__body" :class="{ 'status-rail__body--capsule': capsule }">
      <template v-if="capsule">
        <span class="status-rail__label">{{ displayLabel }}</span>
        <template v-if="subText">
          <span class="status-rail__sep" aria-hidden="true">·</span>
          <span class="status-rail__meta">{{ subText }}</span>
        </template>
      </template>
      <template v-else>
        <div class="status-rail__label">{{ displayLabel }}</div>
        <div v-if="subText" class="status-rail__sub">{{ subText }}</div>
      </template>
    </div>
    <div
      v-if="elapsed && tone === 'recording'"
      class="status-rail__elapsed"
      :class="{ 'status-rail__elapsed--capsule': capsule }"
      aria-label="elapsed time"
    >
      {{ elapsed }}
    </div>
  </div>
</template>

<style scoped>
.status-rail {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px 11px 18px;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-card);
  font-family: var(--font-body);
  overflow: hidden;
  --rail-tone: var(--color-text-muted);
  --rail-tone-soft: color-mix(in srgb, var(--rail-tone) 12%, transparent);
}

.status-rail--compact {
  padding: 8px 12px 8px 16px;
  border-radius: var(--radius-md);
}

.status-rail--embedded {
  box-shadow: none;
  background: color-mix(in srgb, var(--color-surface-elevated) 78%, transparent);
  border-color: color-mix(in srgb, var(--color-border-strong) 85%, transparent);
}

[data-theme="dark"] .status-rail--embedded {
  background: color-mix(in srgb, var(--color-surface-elevated) 55%, transparent);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .status-rail--embedded {
    background: color-mix(in srgb, var(--color-surface-elevated) 55%, transparent);
  }
}

/* ── Capsule: single-line orbital pill (hero eyebrow / tight chrome) ── */
.status-rail--capsule {
  display: inline-flex;
  align-items: center;
  align-self: center;
  width: fit-content;
  max-width: min(100%, 20rem);
  min-height: 0;
  padding: 4px 8px 4px 8px;
  gap: 7px;
  border-radius: var(--radius-orbit);
  box-shadow: none;
  background: color-mix(in srgb, var(--color-surface-elevated) 76%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-border-strong) 88%, transparent);
}

.status-rail--capsule::before {
  display: none;
}

[data-theme="dark"] .status-rail--capsule {
  background: color-mix(in srgb, var(--color-surface-elevated) 48%, transparent);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .status-rail--capsule {
    background: color-mix(in srgb, var(--color-surface-elevated) 48%, transparent);
  }
}

.status-rail__indicator--capsule {
  width: auto;
  height: auto;
  flex-shrink: 0;
}

.status-rail--capsule .status-rail__dot {
  width: 6px;
  height: 6px;
}

.status-rail--capsule.status-rail--success .status-rail__dot {
  box-shadow: 0 0 0 2px var(--rail-tone-soft);
}

.status-rail__body--capsule {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: nowrap;
  gap: 5px;
  flex: 1;
  min-width: 0;
}

.status-rail--capsule .status-rail__label {
  font-size: 11px;
  font-weight: 750;
  letter-spacing: 0.02em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-rail__sep {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 800;
  color: var(--color-text-muted);
  opacity: 0.55;
  line-height: 1;
}

.status-rail__meta {
  font-size: 10.5px;
  font-weight: 650;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.status-rail__elapsed--capsule {
  flex-shrink: 0;
  padding: 2px 7px;
  font-size: 10.5px;
  margin-left: 1px;
  margin-right: 3px;
}

/* Mini live waveform — replaces the static dot while recording inside a capsule. */
.status-rail__wave {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 12px;
  width: 18px;
}

.status-rail__wave-bar {
  display: block;
  width: 2px;
  border-radius: 2px;
  background: var(--rail-tone);
  transform-origin: center;
  animation: rail-wave 900ms ease-in-out infinite;
  height: 30%;
}

.status-rail__wave-bar:nth-child(1) { animation-duration: 720ms; animation-delay: 0ms; }
.status-rail__wave-bar:nth-child(2) { animation-duration: 980ms; animation-delay: 120ms; }
.status-rail__wave-bar:nth-child(3) { animation-duration: 640ms; animation-delay: 60ms; }
.status-rail__wave-bar:nth-child(4) { animation-duration: 1100ms; animation-delay: 220ms; }
.status-rail__wave-bar:nth-child(5) { animation-duration: 820ms; animation-delay: 160ms; }

@keyframes rail-wave {
  0%, 100% {
    height: 30%;
    opacity: 0.55;
  }
  50% {
    height: 100%;
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-rail__wave-bar {
    animation: none !important;
    height: 60%;
    opacity: 0.85;
  }
}

.status-rail::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--rail-tone);
  border-top-left-radius: inherit;
  border-bottom-left-radius: inherit;
}

.status-rail--idle {
  --rail-tone: var(--color-text-muted);
}
.status-rail--recording {
  --rail-tone: var(--color-danger);
}
.status-rail--warning {
  --rail-tone: var(--color-warning);
}
.status-rail--progress {
  --rail-tone: var(--color-accent);
}
.status-rail--success {
  --rail-tone: var(--color-success);
}
.status-rail--danger {
  --rail-tone: var(--color-danger);
}

.status-rail__indicator {
  width: 14px;
  height: 14px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.status-rail__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--rail-tone);
}

.status-rail--recording .status-rail__dot {
  animation: rail-pulse 1.6s ease-out infinite;
}

.status-rail--progress .status-rail__dot {
  animation: rail-blink 1.6s ease-in-out infinite;
}

.status-rail--success .status-rail__dot {
  box-shadow: 0 0 0 3px var(--rail-tone-soft);
}

@keyframes rail-pulse {
  0% {
    box-shadow: 0 0 0 0 var(--rail-tone);
    transform: scale(1);
  }
  70% {
    box-shadow: 0 0 0 8px transparent;
    transform: scale(1.08);
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
    transform: scale(1);
  }
}

@keyframes rail-blink {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-rail__dot {
    animation: none !important;
  }
}

.status-rail__body {
  flex: 1;
  min-width: 0;
}

.status-rail__label {
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.01em;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-rail__sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-rail__elapsed {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--rail-tone);
  font-variant-numeric: tabular-nums;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--rail-tone-soft);
}

@media (max-width: 639px) {
  .status-rail:not(.status-rail--capsule) {
    padding: 10px 12px 10px 16px;
  }
  .status-rail:not(.status-rail--capsule) .status-rail__label {
    font-size: 12px;
  }
  .status-rail:not(.status-rail--capsule) .status-rail__sub {
    font-size: 10.5px;
  }

  .status-rail--capsule {
    max-width: min(100%, 70vw);
  }
}
</style>
