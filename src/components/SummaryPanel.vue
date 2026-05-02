<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Icon, showToast } from 'vant'

const props = defineProps({
  state: { type: String, default: 'collapsed' },
  aiOutput: { type: Object, default: null },
  locale: { type: String, default: 'zh' },
  labels: { type: Object, required: true },
  generatedAt: { type: Number, default: 0 },
})

const taskCreated = reactive({})
const emailExpanded = ref(false)

const isCollapsed = computed(() => props.state === 'collapsed')
const isAnalyzing = computed(() => props.state === 'analyzing')
const isReady = computed(() => props.state === 'ready' && !!props.aiOutput)
const generatedMeta = computed(() => {
  if (!isReady.value || !props.generatedAt) return ''
  const t = new Date(props.generatedAt).toLocaleTimeString(
    props.locale === 'zh' ? 'zh-CN' : 'en-US',
    { hour: '2-digit', minute: '2-digit', hour12: false },
  )
  return props.locale === 'zh' ? `刚刚生成 · ${t}` : `Generated · ${t}`
})

const summary = computed(() => {
  if (!props.aiOutput) return ''
  return props.locale === 'zh' ? props.aiOutput.summaryZh : props.aiOutput.summaryEn
})

const profileLabel = computed(() => {
  if (!props.aiOutput?.profile) return ''
  return props.locale === 'zh' ? props.aiOutput.profile.labelZh : props.aiOutput.profile.labelEn
})
const profileRows = computed(() => {
  if (!props.aiOutput?.profile) return []
  return props.locale === 'zh' ? props.aiOutput.profile.rowsZh : props.aiOutput.profile.rowsEn
})

const assetsLabel = computed(() => {
  if (!props.aiOutput?.assets) return ''
  return props.locale === 'zh' ? props.aiOutput.assets.labelZh : props.aiOutput.assets.labelEn
})
const assetsRows = computed(() => {
  if (!props.aiOutput?.assets) return []
  return props.locale === 'zh' ? props.aiOutput.assets.rowsZh : props.aiOutput.assets.rowsEn
})

const riskLabel = computed(() => {
  if (!props.aiOutput?.risk) return ''
  return props.locale === 'zh' ? props.aiOutput.risk.labelZh : props.aiOutput.risk.labelEn
})
const riskLevel = computed(() => {
  if (!props.aiOutput?.risk) return ''
  return props.locale === 'zh' ? props.aiOutput.risk.levelZh : props.aiOutput.risk.levelEn
})
const riskTarget = computed(() => {
  if (!props.aiOutput?.risk) return ''
  return props.locale === 'zh' ? props.aiOutput.risk.targetZh : props.aiOutput.risk.targetEn
})

const topics = computed(() => {
  if (!props.aiOutput) return []
  return props.locale === 'zh' ? props.aiOutput.topicsZh : props.aiOutput.topicsEn
})

const actions = computed(() => {
  if (!props.aiOutput?.actions) return []
  return props.aiOutput.actions.map((a) => ({
    id: a.id,
    text: props.locale === 'zh' ? a.textZh : a.textEn,
    due: props.locale === 'zh' ? a.dueZh : a.dueEn,
  }))
})

const emailDraft = computed(() => {
  if (!props.aiOutput) return ''
  return props.locale === 'zh' ? props.aiOutput.emailDraftZh : props.aiOutput.emailDraftEn
})

watch(
  () => props.aiOutput,
  () => {
    Object.keys(taskCreated).forEach((k) => delete taskCreated[k])
    emailExpanded.value = false
  },
)

function createTask(item) {
  if (taskCreated[item.id]) return
  taskCreated[item.id] = true
  showToast({
    message: props.labels.notifyTaskCreated,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1300,
  })
}

async function copyEmail() {
  try {
    await navigator.clipboard.writeText(emailDraft.value)
    showToast({
      message: props.labels.notifyEmailCopied,
      icon: 'success',
      className: 'save-notes-toast',
      position: 'middle',
      duration: 1300,
    })
  } catch {
    /* clipboard not available in this context */
  }
}
</script>

<template>
  <section class="summary-panel">
    <header class="summary-header">
      <div class="summary-eyebrow">
        {{ labels.eyebrow }}
      </div>
      <div v-if="generatedMeta" class="summary-meta">{{ generatedMeta }}</div>
    </header>

    <transition name="fade" mode="out-in">
      <!-- ───────── Collapsed (waiting for stop) ───────── -->
      <div v-if="isCollapsed" key="collapsed" class="summary-empty" role="note">
        <Icon name="clock-o" size="13" class="summary-empty__icon" />
        <p class="summary-empty__text">{{ labels.emptyText }}</p>
      </div>

      <!-- ───────── Analyzing ───────── -->
      <div v-else-if="isAnalyzing" key="analyzing" class="summary-analyzing">
        <div class="analyze-loader" aria-hidden="true">
          <span class="loader-ring loader-ring--outer" />
          <span class="loader-ring loader-ring--mid" />
          <span class="loader-core" />
          <span class="loader-glint loader-glint--1" />
          <span class="loader-glint loader-glint--2" />
        </div>
        <p class="analyze-title">{{ labels.analyzingTitle }}</p>
        <div class="analyze-subline">
          <span class="analyze-subline-dot" />
          <span class="analyze-subtitle">{{ labels.analyzingSubtitle }}</span>
        </div>
      </div>

      <!-- ───────── Ready ───────── -->
      <div v-else-if="isReady" key="ready" class="summary-ready">
        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="comment-o" size="14" />
            </div>
            <div class="block-title">{{ labels.summaryHeading }}</div>
          </div>
          <p class="block-text">{{ summary }}</p>
        </article>

        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="contact" size="14" />
            </div>
            <div class="block-title">{{ profileLabel }}</div>
          </div>
          <dl class="kv-grid">
            <div v-for="row in profileRows" :key="row.k" class="kv-row">
              <dt>{{ row.k }}</dt>
              <dd>{{ row.v }}</dd>
            </div>
          </dl>
        </article>

        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="balance-list-o" size="14" />
            </div>
            <div class="block-title">{{ assetsLabel }}</div>
          </div>
          <dl class="kv-grid">
            <div v-for="row in assetsRows" :key="row.k" class="kv-row">
              <dt>{{ row.k }}</dt>
              <dd>{{ row.v }}</dd>
            </div>
          </dl>
        </article>

        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="warning-o" size="14" />
            </div>
            <div class="block-title">{{ riskLabel }}</div>
          </div>
          <div class="risk-row">
            <span class="risk-pill">{{ riskLevel }}</span>
            <span class="risk-target">{{ riskTarget }}</span>
          </div>
        </article>

        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="label-o" size="14" />
            </div>
            <div class="block-title">{{ labels.topicsHeading }}</div>
          </div>
          <div class="topic-chips">
            <span v-for="t in topics" :key="t" class="topic-chip">{{ t }}</span>
          </div>
        </article>

        <article class="summary-block">
          <div class="block-head">
            <div class="block-icon">
              <Icon name="todo-list-o" size="14" />
            </div>
            <div class="block-title">{{ labels.actionsHeading }}</div>
          </div>
          <ul class="action-list">
            <li v-for="(item, idx) in actions" :key="item.id" class="action-row">
              <div class="action-index">{{ idx + 1 }}</div>
              <div class="action-body">
                <div class="action-text">{{ item.text }}</div>
                <div v-if="item.due" class="action-due">
                  <Icon name="clock-o" size="11" /> {{ item.due }}
                </div>
              </div>
              <button
                type="button"
                class="action-btn"
                :class="{ 'action-btn--done': taskCreated[item.id] }"
                @click="createTask(item)"
              >
                <template v-if="taskCreated[item.id]">
                  <Icon name="success" size="11" /> {{ labels.added }}
                </template>
                <template v-else>{{ labels.createTask }}</template>
              </button>
            </li>
          </ul>
        </article>

        <article class="summary-block summary-block--email">
          <button type="button" class="email-toggle" @click="emailExpanded = !emailExpanded">
            <div class="block-head" style="margin: 0">
              <div class="block-icon">
                <Icon name="envelop-o" size="14" />
              </div>
              <div class="block-title">{{ labels.emailHeading }}</div>
            </div>
            <Icon :name="emailExpanded ? 'arrow-up' : 'arrow-down'" size="14" class="email-chevron" />
          </button>
          <transition name="reveal">
            <div v-if="emailExpanded" class="email-body">
              <pre class="email-text">{{ emailDraft }}</pre>
              <div class="email-actions">
                <button type="button" class="copy-btn" @click="copyEmail">
                  <Icon name="completed" size="12" />
                  {{ labels.copyEmail }}
                </button>
              </div>
            </div>
          </transition>
        </article>
      </div>
    </transition>
  </section>
</template>

<style scoped>
.summary-panel {
  padding: 20px;
  border-radius: var(--radius-xl);
  background: var(--color-card-bg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-card);
}

.summary-header {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-border);
}

.summary-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.summary-eyebrow::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

.summary-meta {
  margin-top: 6px;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--color-text-secondary);
  letter-spacing: 0.01em;
  font-variant-numeric: tabular-nums;
}

/* ───────── Empty / Collapsed — ultra-minimal hint ───────── */
.summary-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 18px;
  text-align: center;
}

.summary-empty__icon {
  color: var(--color-text-muted);
  opacity: 0.38;
  flex-shrink: 0;
}

.summary-empty__text {
  font-size: 11px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--color-text-muted);
  max-width: 28ch;
  margin: 0;
  opacity: 0.72;
}

[data-theme="dark"] .summary-empty__text {
  opacity: 0.5;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .summary-empty__text {
    opacity: 0.5;
  }
}

/* ───────── Analyzing ───────── */
.summary-analyzing {
  padding: 24px 8px 14px;
  text-align: center;
}

.analyze-loader {
  position: relative;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
}

.loader-ring {
  position: absolute;
  border-radius: 999px;
  border: 1px solid rgba(100, 116, 139, 0.3);
}

.loader-ring--outer {
  inset: 0;
  border-top-color: var(--color-accent);
  animation: loader-spin 1.1s linear infinite;
}

.loader-core {
  position: absolute;
  inset: 16px;
  border-radius: 999px;
  background: var(--color-accent);
}

.analyze-title {
  margin: 4px 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  font-family: var(--font-display);
  letter-spacing: -0.01em;
}

.analyze-subline {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-soft);
}

.analyze-subline-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--color-accent);
  animation: dot-blink 1s ease-in-out infinite;
}

.analyze-subtitle {
  margin: 0;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

@keyframes loader-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes dot-blink {
  0%, 100% { opacity: 0.45; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .loader-ring--outer,
  .loader-core,
  .analyze-subline-dot {
    animation: none !important;
  }
}

/* ───────── Ready ───────── */
.summary-ready {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.summary-block {
  padding: 0;
  background: transparent;
  border: none;
  position: relative;
}

.summary-block + .summary-block {
  padding-top: 18px;
  border-top: 1px solid var(--color-border);
}

.block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.block-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.block-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.005em;
  color: var(--color-text-primary);
  font-family: var(--font-display);
}

.block-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-secondary);
}

.kv-grid {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px 10px;
}

.kv-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
  border-bottom: 1px dashed var(--color-border);
  padding-bottom: 6px;
}

.kv-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.kv-row dt {
  margin: 0;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.kv-row dd {
  margin: 0;
  color: var(--color-text-primary);
  font-weight: 600;
}

.risk-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.risk-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.1);
  color: #b45309;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid rgba(217, 119, 6, 0.18);
}

.risk-pill::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

[data-theme="dark"] .risk-pill {
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.22);
}

.risk-target {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-chip {
  padding: 5px 11px;
  border-radius: 999px;
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  border: 1px solid var(--color-border);
}

.action-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-row {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--color-surface-subtle);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: background 0.2s, border-color 0.2s;
}

.action-row:hover {
  border-color: var(--color-border-strong);
}

.action-index {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: var(--color-text-primary);
  color: var(--color-surface);
  font-size: 11px;
  font-weight: 700;
  display: grid;
  place-items: center;
  font-variant-numeric: tabular-nums;
}

.action-text {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.action-due {
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.action-btn {
  border: none;
  background: var(--color-accent);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
}

.action-btn:hover {
  background: var(--color-accent-strong);
  box-shadow: 0 4px 12px -4px var(--color-accent-soft);
}

.action-btn:active {
  transform: scale(0.96);
}

.action-btn--done {
  background: #10b981;
}

.action-btn--done:hover {
  background: #059669;
}

.summary-block--email {
  padding: 0;
}

.email-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.email-chevron {
  color: var(--color-text-muted);
  transition: transform 0.2s;
}

.email-body {
  padding: 12px 0 0;
}

.email-text {
  margin: 0;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-text-secondary);
  padding: 14px 16px;
  background: var(--color-surface-subtle);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.email-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.copy-btn {
  border: 1px solid var(--color-accent-soft);
  background: var(--color-accent-soft);
  color: var(--color-accent-text);
  font-size: 11px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.2s, color 0.2s;
}

.copy-btn:hover {
  background: var(--color-accent);
  color: #ffffff;
  border-color: var(--color-accent);
}

.copy-btn:active {
  transform: scale(0.96);
}

/* ───────── Transitions ───────── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.32s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.reveal-enter-active,
.reveal-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}
.reveal-enter-from,
.reveal-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.reveal-enter-to,
.reveal-leave-from {
  opacity: 1;
  transform: translateY(0);
}
</style>
