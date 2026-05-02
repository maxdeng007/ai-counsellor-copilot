<script setup>
import { computed, ref, watch } from 'vue'
import { Locale } from 'vant'
import zhCN from 'vant/es/locale/lang/zh-CN'
import enUS from 'vant/es/locale/lang/en-US'
import CounsellorMeeting from './views/CounsellorMeeting.vue'
import LiveTranscript from './views/LiveTranscript.vue'
import VoiceprintSettings from './views/VoiceprintSettings.vue'

const locale = ref('zh')
const mode = ref('live') // 'live' | 'demo' | 'voiceprint'
const showModePanel = ref(false)
const transcriptViewMode = ref('speaker')

const SHOW_TEST_PANEL =
  import.meta.env?.VITE_SHOW_TEST_PANEL === 'true' ||
  import.meta.env?.VITE_SHOW_TEST_PANEL === '1'

const theme = ref('system') // 'system' | 'light' | 'dark'

const applyTheme = (t) => {
  const root = document.documentElement
  if (t === 'dark') {
    root.setAttribute('data-theme', 'dark')
  } else if (t === 'light') {
    root.setAttribute('data-theme', 'light')
  } else {
    root.removeAttribute('data-theme')
  }
}

watch(theme, (t) => applyTheme(t))

// React to system theme changes
const mq = window.matchMedia('(prefers-color-scheme: dark)')
mq.addEventListener('change', (e) => {
  if (theme.value === 'system') applyTheme('system')
})

// Init: apply system resolve on mount
applyTheme(theme.value)

const viewLabel = computed(() => {
  if (mode.value === 'demo') return locale.value === 'zh' ? '演示' : 'Demo'
  if (mode.value === 'voiceprint') return locale.value === 'zh' ? '声纹' : 'Voiceprint'
  return locale.value === 'zh' ? '实时转写' : 'Live Transcript'
})

watch(
  locale,
  (code) => {
    document.documentElement.lang = code === 'zh' ? 'zh-CN' : 'en'
    Locale.use(code === 'zh' ? 'zh-CN' : 'en-US', code === 'zh' ? zhCN : enUS)
  },
  { immediate: true },
)
</script>

<template>
  <main class="app-shell">
    <div class="page">
      <header class="page-topbar">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2 L20 7 V17 L12 22 L4 17 V7 Z" />
              <path d="M12 7 V12 L16 14" opacity="0.6" />
            </svg>
          </span>
          <span class="brand-text">
            <span class="brand-name">{{ locale === 'zh' ? '理财咨询助手' : 'Counsellor Copilot' }}</span>
            <span class="brand-eyebrow">AI · CFP</span>
          </span>
        </div>
        <div class="topbar-actions">
          <button
            v-if="SHOW_TEST_PANEL"
            type="button"
            class="settings-trigger"
            :aria-label="locale === 'zh' ? '设置' : 'Settings'"
            :aria-expanded="showModePanel ? 'true' : 'false'"
            @click="showModePanel = !showModePanel"
          >
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <span class="settings-trigger__label">{{ locale === 'zh' ? '设置' : 'Settings' }}</span>
          </button>
          <div class="topbar-toolbar" role="presentation">
          <div class="theme-toggle" role="group" aria-label="Theme">
            <button
              type="button"
              class="theme-toggle__btn"
              :class="{ 'theme-toggle__btn--active': theme === 'system' }"
              title="System"
              aria-label="System theme"
              @click="theme = 'system'"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <path d="M8 21h8M12 17v4" />
              </svg>
            </button>
            <button
              type="button"
              class="theme-toggle__btn"
              :class="{ 'theme-toggle__btn--active': theme === 'light' }"
              title="Light"
              aria-label="Light theme"
              @click="theme = 'light'"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
              </svg>
            </button>
            <button
              type="button"
              class="theme-toggle__btn"
              :class="{ 'theme-toggle__btn--active': theme === 'dark' }"
              title="Dark"
              aria-label="Dark theme"
              @click="theme = 'dark'"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            </button>
          </div>
          <div class="lang-toggle" role="group" aria-label="Language">
            <button
              type="button"
              class="lang-toggle__btn"
              :class="{ 'lang-toggle__btn--active': locale === 'zh' }"
              @click="locale = 'zh'"
            >
              中
            </button>
            <button
              type="button"
              class="lang-toggle__btn"
              :class="{ 'lang-toggle__btn--active': locale === 'en' }"
              @click="locale = 'en'"
            >
              EN
            </button>
          </div>
          </div>
        </div>
      </header>

      <transition name="panel-drop">
        <section v-if="showModePanel && SHOW_TEST_PANEL" class="test-panel" aria-label="Testing settings">
          <div class="test-panel__title">{{ locale === 'zh' ? '应用模式（测试）' : 'App Mode (Testing)' }}</div>
          <div class="mode-toggle" role="group" aria-label="App mode">
            <button
              type="button"
              class="mode-toggle__btn"
              :class="{ 'mode-toggle__btn--active': mode === 'live' }"
              @click="mode = 'live'"
            >
              {{ locale === 'zh' ? '实时' : 'Live' }}
            </button>
            <button
              type="button"
              class="mode-toggle__btn"
              :class="{ 'mode-toggle__btn--active': mode === 'demo' }"
              @click="mode = 'demo'"
            >
              {{ locale === 'zh' ? '演示' : 'Demo' }}
            </button>
            <button
              type="button"
              class="mode-toggle__btn"
              :class="{ 'mode-toggle__btn--active': mode === 'voiceprint' }"
              @click="mode = 'voiceprint'"
            >
              {{ locale === 'zh' ? '声纹' : 'Voice' }}
            </button>
          </div>
          <template v-if="mode === 'live'">
            <div class="test-panel__title">{{ locale === 'zh' ? '转写视图（测试）' : 'Transcript View (Testing)' }}</div>
            <div class="mode-toggle" role="group" aria-label="Transcript view mode">
              <button
                type="button"
                class="mode-toggle__btn"
                :class="{ 'mode-toggle__btn--active': transcriptViewMode === 'simple' }"
                @click="transcriptViewMode = 'simple'"
              >
                Simple
              </button>
              <button
                type="button"
                class="mode-toggle__btn"
                :class="{ 'mode-toggle__btn--active': transcriptViewMode === 'speaker' }"
                @click="transcriptViewMode = 'speaker'"
              >
                Speaker
              </button>
            </div>
          </template>
        </section>
      </transition>

      <LiveTranscript
        v-if="mode === 'live'"
        :locale="locale"
        :view-mode="transcriptViewMode"
        @update:view-mode="transcriptViewMode = $event"
      />
      <VoiceprintSettings v-else-if="mode === 'voiceprint'" :locale="locale" />
      <CounsellorMeeting v-else :locale="locale" />
    </div>
  </main>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--color-bg);
  padding-bottom: env(safe-area-inset-bottom);
}

.page {
  margin: 0 auto;
  max-width: 100%;
  min-height: 100vh;
  background: var(--color-surface);
  position: relative;
}

.page-topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  background: var(--color-topbar-bg);
  -webkit-backdrop-filter: saturate(140%) blur(14px);
  backdrop-filter: saturate(140%) blur(14px);
  border-bottom: 1px solid var(--color-border);
}

.topbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-shrink: 0;
}

/* Theme + language sit together as one trailing control cluster on mobile. */
.topbar-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.settings-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  border-radius: 999px;
  padding: 6px 11px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.settings-trigger:hover {
  border-color: var(--color-text-muted);
  color: var(--color-text-primary);
}

.settings-trigger:active {
  color: var(--color-text-primary);
  transform: scale(0.97);
}

.settings-trigger svg {
  opacity: 0.7;
}

.settings-trigger__label {
  display: inline;
}

.mode-toggle {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
}

.mode-toggle__btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border-radius: 999px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
  -webkit-tap-highlight-color: transparent;
  white-space: nowrap;
}

.mode-toggle__btn:hover:not(.mode-toggle__btn--active) {
  color: var(--color-text-secondary);
}

.mode-toggle__btn--active {
  background: var(--color-accent);
  color: var(--color-on-accent);
  box-shadow: 0 2px 8px -2px rgba(13, 61, 92, 0.35);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-orbit);
  background: linear-gradient(145deg, var(--color-accent) 0%, var(--color-accent-strong) 100%);
  color: var(--color-on-accent);
  flex-shrink: 0;
  box-shadow:
    0 0 0 2px var(--color-surface),
    0 0 0 4px var(--color-warm-ring);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
}

.brand:hover .brand-mark {
  transform: rotate(-6deg) scale(1.05);
}

.brand-text {
  display: inline-flex;
  flex-direction: column;
  line-height: 1;
  min-width: 0;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 14.5px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-eyebrow {
  margin-top: 3px;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: var(--color-text-muted);
  text-transform: uppercase;
  white-space: nowrap;
}

.lang-toggle {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
}

.lang-toggle__btn {
  border: none;
  background: transparent;
  padding: 5px 10px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  border-radius: 999px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.2s, background 0.2s, box-shadow 0.2s;
  -webkit-tap-highlight-color: transparent;
  min-width: 28px;
}

.lang-toggle__btn:hover:not(.lang-toggle__btn--active) {
  color: var(--color-text-secondary);
}

.lang-toggle__btn--active {
  background: var(--color-accent);
  color: var(--color-on-accent);
  box-shadow: 0 2px 8px -2px rgba(13, 61, 92, 0.35);
}

.theme-toggle {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
}

.theme-toggle__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  width: 28px;
  height: 24px;
  color: var(--color-text-muted);
  cursor: pointer;
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
  transition: color 0.2s, background 0.2s;
}

.theme-toggle__btn:hover:not(.theme-toggle__btn--active) {
  color: var(--color-text-secondary);
}

.theme-toggle__btn--active {
  background: var(--color-accent);
  color: var(--color-on-accent);
  box-shadow: 0 2px 8px -2px rgba(13, 61, 92, 0.35);
}

.test-panel {
  margin: 10px 14px 0;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface-subtle);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.test-panel__title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.panel-drop-enter-active,
.panel-drop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-drop-enter-from,
.panel-drop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 639px) {
  .page-topbar {
    flex-direction: row;
    align-items: center;
    gap: 10px;
    padding: 10px max(12px, env(safe-area-inset-right)) 10px max(12px, env(safe-area-inset-left));
    padding-top: max(10px, env(safe-area-inset-top));
  }

  .brand {
    flex: 1;
    min-width: 0;
  }

  .topbar-actions {
    width: auto;
    justify-content: flex-end;
    gap: 6px;
    flex-wrap: nowrap;
  }

  .topbar-toolbar {
    gap: 6px;
  }

  /* Icon-only settings on narrow phones — saves horizontal space beside toggles. */
  .settings-trigger {
    padding: 8px;
    border-radius: 10px;
  }

  .settings-trigger__label {
    display: none;
  }

  .theme-toggle {
    padding: 2px;
  }

  .theme-toggle__btn {
    width: 26px;
    height: 22px;
  }

  .theme-toggle__btn svg {
    width: 13px;
    height: 13px;
  }

  .lang-toggle {
    padding: 2px;
  }

  .lang-toggle__btn {
    padding: 5px 8px;
    font-size: 11px;
    min-width: 26px;
  }

  .mode-toggle,
  .theme-toggle {
    min-width: 0;
  }

  .test-panel .mode-toggle__btn {
    padding: 6px 10px;
    font-size: 10.5px;
  }

  .brand-mark {
    width: 28px;
    height: 28px;
  }

  .brand-name {
    font-size: 13.5px;
  }

  .brand-eyebrow {
    font-size: 9px;
  }
}

/* Ultra-narrow: hide subtitle line so the bar stays one clean row. */
@media (max-width: 380px) {
  .brand-eyebrow {
    display: none;
  }
}

@media (min-width: 640px) and (max-width: 899px) {
  .page {
    max-width: 720px;
  }
}

@media (min-width: 900px) {
  .page {
    max-width: 1120px;
    background: var(--color-surface);
    box-shadow: 0 30px 60px -40px rgba(28, 25, 23, 0.18);
  }
  .page-topbar {
    padding: 16px 28px;
  }
}
</style>

<style>
/* Global toast tweak */
.save-notes-toast {
  border-radius: 14px !important;
  font-size: 13px !important;
  padding: 10px 14px !important;
  box-shadow: 0 18px 40px -18px rgba(28, 25, 23, 0.3) !important;
}
</style>
