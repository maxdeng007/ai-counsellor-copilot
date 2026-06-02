<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Icon, showToast } from 'vant'
import LiveCaption from '../components/LiveCaption.vue'
import RecordButton from '../components/RecordButton.vue'
import SpeakerBubble from '../components/SpeakerBubble.vue'
import SummaryPanel from '../components/SummaryPanel.vue'
import ClientLinker from '../components/ClientLinker.vue'
import SessionStatusRail from '../components/SessionStatusRail.vue'
import { MOCK_CLIENTS } from '../data/mockDialog.js'
import { clientRepo } from '../services/clientRepo.js'
import { meetingRepo } from '../services/meetingRepo.js'
import { extractEntities, summarizeMeeting } from '../services/summaryClient.js'

const props = defineProps({
  locale: { type: String, default: 'zh' },
  viewMode: { type: String, default: 'speaker' },
})
const emit = defineEmits(['update:view-mode'])

const DIARIZATION_API_BASE = import.meta.env?.VITE_DIARIZATION_API_BASE || 'http://localhost:8090'
const USE_VOLC =
  import.meta.env?.VITE_USE_VOLC === 'false' ||
  import.meta.env?.VITE_USE_VOLC === '0'
    ? false
    : true
// Larger windows improve diarization stability for multi-speaker turns.
const CHUNK_MS = Number(import.meta.env?.VITE_CHUNK_MS || 6000)
// Keep first result fast for UX, but still long enough for diarization.
const FIRST_CHUNK_MS = Number(import.meta.env?.VITE_FIRST_CHUNK_MS || 900)
const CHUNK_OVERLAP_MS = Number(import.meta.env?.VITE_CHUNK_OVERLAP_MS || 2400)
const VAD_EVAL_INTERVAL_MS = Number(import.meta.env?.VITE_VAD_EVAL_INTERVAL_MS || 200)
const VAD_END_SILENCE_MS = Number(import.meta.env?.VITE_VAD_END_SILENCE_MS || 1600)
const VAD_MAX_UTTERANCE_MS = Number(import.meta.env?.VITE_VAD_MAX_UTTERANCE_MS || 12000)
/** WebAudio gain after MediaStreamSource (1 = unity). */
const MIC_GAIN_RAW = import.meta.env?.VITE_MIC_GAIN
const MIC_GAIN =
  MIC_GAIN_RAW === undefined || MIC_GAIN_RAW === ''
    ? 1.25
    : Math.min(4, Math.max(0.25, Number(MIC_GAIN_RAW)))

/** Scale quiet chunks up toward this RMS before encoding WAV (caps by max gain). */
const TARGET_RMS_RAW = import.meta.env?.VITE_MIC_TARGET_RMS
const CHUNK_TARGET_RMS =
  TARGET_RMS_RAW === undefined || TARGET_RMS_RAW === ''
    ? 0.075
    : Math.min(0.35, Math.max(0.04, Number(TARGET_RMS_RAW)))
const CHUNK_RMS_MAX_GAIN = Math.min(
  10,
  Math.max(1.5, Number(import.meta.env?.VITE_MIC_MAX_NORMALIZE_GAIN || 5)),
)

/** Simple VAD gate to avoid sending near-silence chunks to diarization/ASR. */
const VAD_RMS_THRESHOLD_RAW = import.meta.env?.VITE_VAD_RMS_THRESHOLD
const VAD_RMS_THRESHOLD =
  VAD_RMS_THRESHOLD_RAW === undefined || VAD_RMS_THRESHOLD_RAW === ''
    ? 0.009
    : Math.max(0.001, Number(VAD_RMS_THRESHOLD_RAW))

const PREVIEW_MIN_MS = Number(import.meta.env?.VITE_PREVIEW_MIN_MS || 800)
const PREVIEW_MIN_GAP_MS = Number(import.meta.env?.VITE_PREVIEW_MIN_GAP_MS || 600)
const VOLC_PREVIEW_WINDOW_MS = Number(import.meta.env?.VITE_VOLC_PREVIEW_WINDOW_MS || 2800)
const VOLC_PREVIEW_MAX_CHUNKS = Number(import.meta.env?.VITE_VOLC_PREVIEW_MAX_CHUNKS || 120)
const VOLC_PREVIEW_MIN_NEW_MS = Number(import.meta.env?.VITE_VOLC_PREVIEW_MIN_NEW_MS || 450)
const VOLC_COMMIT_WINDOW_MS = Number(import.meta.env?.VITE_VOLC_COMMIT_WINDOW_MS || 8000)
const VOLC_COMMIT_MIN_GAP_MS = Number(import.meta.env?.VITE_VOLC_COMMIT_MIN_GAP_MS || 2600)
const VOLC_COMMIT_MIN_NEW_MS = Number(import.meta.env?.VITE_VOLC_COMMIT_MIN_NEW_MS || 1400)
const VOLC_COMMIT_MAX_WINDOW_MS = Number(import.meta.env?.VITE_VOLC_COMMIT_MAX_WINDOW_MS || 14000)
// Overlap a small audio tail between commits so Volc diarization keeps
// speaker IDs stable across separate ASR sessions.
const VOLC_COMMIT_OVERLAP_MS = Number(import.meta.env?.VITE_VOLC_COMMIT_OVERLAP_MS || 1500)
/** If VAD misses a pause, still commit periodically so text does not stall. */
const VOLC_COMMIT_FORCE_GAP_MS = Number(
  import.meta.env?.VITE_VOLC_COMMIT_FORCE_GAP_MS || 4800,
)

/**
 * Conversation-aware acoustic pause before a Volc commit (ms).
 * Shorter after sentence-like preview tails — commit sooner after a natural chat pause.
 * Longer when preview has no/clause endings — tolerate pauses mid-thought.
 */
const VOLC_CHAT_PAUSE_SENTENCE_MS = Number(
  import.meta.env?.VITE_VOLC_CHAT_PAUSE_SENTENCE_MS || 700,
)
const VOLC_CHAT_PAUSE_CLAUSE_MS = Number(import.meta.env?.VITE_VOLC_CHAT_PAUSE_CLAUSE_MS || 950)
const VOLC_CHAT_PAUSE_INCOMPLETE_MS = Number(
  import.meta.env?.VITE_VOLC_CHAT_PAUSE_INCOMPLETE_MS || 1500,
)
const VOLC_DRAFT_FRAGMENT_MIN_CHARS = Number(
  import.meta.env?.VITE_VOLC_DRAFT_FRAGMENT_MIN_CHARS || 12,
)
const VOLC_DRAFT_BUFFER_HOLD_MS = Number(import.meta.env?.VITE_VOLC_DRAFT_BUFFER_HOLD_MS || 2200)
const VOLC_DRAFT_BUFFER_MAX_GAP_MS = Number(import.meta.env?.VITE_VOLC_DRAFT_BUFFER_MAX_GAP_MS || 2600)
const VOLC_DRAFT_SPEAKER_CONFIDENCE_MIN = Number(
  import.meta.env?.VITE_VOLC_DRAFT_SPEAKER_CONFIDENCE_MIN || 0.62,
)
const VOLC_REFRESH_MIN_GAP_MS = Number(import.meta.env?.VITE_VOLC_REFRESH_MIN_GAP_MS || 25000)
const VOLC_REFRESH_MIN_NEW_MS = Number(import.meta.env?.VITE_VOLC_REFRESH_MIN_NEW_MS || 9000)
const SHOW_VOLC_DEBUG =
  import.meta.env?.VITE_SHOW_VOLC_DEBUG === 'true' ||
  import.meta.env?.VITE_SHOW_VOLC_DEBUG === '1'

const ECHO_CANCEL =
  import.meta.env?.VITE_MIC_ECHO_CANCELLATION === 'false' ||
  import.meta.env?.VITE_MIC_ECHO_CANCELLATION === '0'
    ? false
    : true
const MIC_NOISE_SUPPRESSION =
  import.meta.env?.VITE_MIC_NOISE_SUPPRESSION === 'false' ||
  import.meta.env?.VITE_MIC_NOISE_SUPPRESSION === '0'
    ? false
    : true
const USE_AUDIO_WORKLET =
  import.meta.env?.VITE_USE_AUDIO_WORKLET === 'true' ||
  import.meta.env?.VITE_USE_AUDIO_WORKLET === '1'

/**
 * Hero title copy — segments joined for full string (Unicode-safe typing via [...str]).
 * Animation cadence inspired by common typewriter demos (e.g. ~100ms/char, pause, loop)
 * such as [Ali Imam’s Typewriter](https://aliimam.in/docs/components/typewriter).
 */
const HERO_TITLE_SEGMENTS = {
  zh: ['专业', '会谈', '记录'],
  en: ['Professional', 'session', 'notes'],
}
/** ms per character while typing — aligned with reference default speed ~100 */
const TITLE_CHAR_MS = 118
/** ms per character while deleting — slightly faster feels natural */
const TITLE_DELETE_MS = 82
/** dwell on full line before backspacing */
const TITLE_HOLD_MS = 5600
/** pause after erase before next cycle — keeps loop frequency low */
const TITLE_GAP_MS = 4200
const TITLE_LEAD_IN_MS = 1100

const heroTitleSegments = computed(() => HERO_TITLE_SEGMENTS[props.locale === 'zh' ? 'zh' : 'en'])
const heroTitleSeparator = computed(() => (props.locale === 'zh' ? '' : ' '))
const heroTitleFull = computed(() => heroTitleSegments.value.join(heroTitleSeparator.value))

const heroTitleCharCount = ref(0)
const heroTitleReduceMotion = ref(false)
const heroTitleTyped = computed(() => {
  const full = heroTitleFull.value
  const chars = [...full]
  const n = Math.min(heroTitleCharCount.value, chars.length)
  return chars.slice(0, n).join('')
})

let heroTitleTimeouts = []

function clearHeroTitleAnimation() {
  for (const id of heroTitleTimeouts) {
    clearTimeout(id)
  }
  heroTitleTimeouts = []
}

function scheduleHeroTitleStep() {
  clearHeroTitleAnimation()
  if (heroTitleReduceMotion.value) {
    heroTitleCharCount.value = [...heroTitleFull.value].length
    return
  }

  let phase = /** @type {'typing' | 'holding' | 'deleting' | 'gap'} */ ('typing')

  const tick = () => {
    const full = heroTitleFull.value
    const len = [...full].length

    if (phase === 'typing') {
      if (heroTitleCharCount.value < len) {
        heroTitleCharCount.value += 1
        heroTitleTimeouts.push(window.setTimeout(tick, TITLE_CHAR_MS))
      } else {
        phase = 'holding'
        heroTitleTimeouts.push(window.setTimeout(tick, TITLE_HOLD_MS))
      }
      return
    }
    if (phase === 'holding') {
      phase = 'deleting'
      heroTitleTimeouts.push(window.setTimeout(tick, TITLE_DELETE_MS))
      return
    }
    if (phase === 'deleting') {
      if (heroTitleCharCount.value > 0) {
        heroTitleCharCount.value -= 1
        heroTitleTimeouts.push(window.setTimeout(tick, TITLE_DELETE_MS))
      } else {
        phase = 'gap'
        heroTitleTimeouts.push(window.setTimeout(tick, TITLE_GAP_MS))
      }
      return
    }
    if (phase === 'gap') {
      phase = 'typing'
      heroTitleTimeouts.push(window.setTimeout(tick, TITLE_CHAR_MS))
    }
  }

  heroTitleCharCount.value = 0
  phase = 'typing'
  heroTitleTimeouts.push(window.setTimeout(tick, TITLE_LEAD_IN_MS))
}

const flowState = ref('idle') // 'idle' | 'recording' | 'processing' | 'reviewing' | 'linking' | 'summarizing' | 'summarized'
const elapsedSeconds = ref(0)
let timerInterval = null

const liveCaptionText = ref('')
const liveCaptionState = ref('idle') // 'idle' | 'streaming' | 'analyzing'
const transcriptText = ref('')
const pendingChunks = ref(0)
// Mobile background-recording mitigations: keep screen awake while recording and
// surface a warning if the OS suspends capture (screen lock / app switch).
const recordingInterrupted = ref(false)
let wakeLockSentinel = null
let mitigationsActive = false
const viewMode = computed({
  get: () => props.viewMode || 'speaker',
  set: (val) => emit('update:view-mode', val),
})
const linkerOpen = ref(false)
const extractedClient = ref(null)
const linkedClient = ref(null)
const aiOutput = ref(null)
const summaryGeneratedAt = ref(0)
const currentMeetingId = ref('')
const availableClients = ref([...MOCK_CLIENTS])
/** Scroll container for transcript + live caption; kept pinned to bottom while capturing. */
const transcriptScrollerEl = ref(null)
const sessionId = ref('')
const chunkSeq = ref(0)
/** Monotonic only for diarized (final) chunks; independent of live preview ASR. */
const previewSeq = ref(0)
let previewInFlight = 0

const speakers = reactive({})
const bubbles = ref([])
let bubbleSerial = 0
/** Bubbles index where the current recording segment starts (after any segment divider). */
let volcSegmentStartIndex = 0
/** transcriptText length after the latest segment divider line; used when replacing this segment only. */
let transcriptSegmentStartLength = 0
/**
 * Speaker keys carried over from completed segments. They are kept across the
 * current segment's prune + renumber pass so identities (color, number, name)
 * stay stable across recordings.
 */
let lockedSpeakerIds = new Set()
const SPEAKER_PALETTE = ['sky', 'emerald', 'amber', 'violet', 'rose']

let mediaStream = null
let finalQueue = []
let finalInFlight = 0
const MAX_FINAL_IN_FLIGHT = Number(import.meta.env?.VITE_MAX_FINAL_IN_FLIGHT || 1)
let finalDrainWaiters = []
let audioCtx = null
let audioNode = null
let audioSinkNode = null
let chunkTimer = null
let firstChunkTimer = null
let vadTimer = null
let inUtterance = false
let utteranceStartedAt = 0
let silenceMs = 0
let utteranceChunks = []
let pcmChunks = []
let recordedChunks = []
let previewPcmChunks = []
let previewSamples = 0
let previewLastSentAt = 0
let previewRequestId = 0
let previewParagraphText = ""
let volcPreviewParagraphText = ""
let volcPreviewInFlight = 0
let volcPreviewLastSentAt = 0
let volcPreviewLastText = ""
let recordedSamplesTotal = 0
let volcPreviewLastSentSamples = 0
let volcPreviewRequests = 0
let volcCommitInFlight = 0
let volcCommitLastSentAt = 0
let volcCommitLastSentSamples = 0
let volcCommittedSamples = 0
let volcRecentFingerprints = []
let volcCommitRequests = 0
let volcCommitAccepted = 0
let volcCommitEmpty = 0
let volcRefreshInFlight = 0
let volcRefreshLastSentAt = 0
let volcRefreshLastSentSamples = 0
/** Queue of mic frames used only for Volc-path VAD (same chunking as recorder). */
let volcVadPcmQueue = []
/** Volc incremental commit gated on silence / max utterance; see evaluateVolcVadTick. */
let volcCommitPending = false
let volcDraftBuffer = null
let overlapTail = new Float32Array(0)
let warnedDiarizationUnavailable = false
let lastSegmentFingerprint = ''
const TARGET_SAMPLE_RATE = 16000

const formattedElapsed = computed(() => {
  const m = String(Math.floor(elapsedSeconds.value / 60)).padStart(2, '0')
  const s = String(elapsedSeconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

const statusLine = computed(() => {
  if (flowState.value === 'recording') {
    return props.locale === 'zh' ? '实时转写' : 'Live transcript'
  }
  if (flowState.value === 'processing') return props.locale === 'zh' ? '终稿处理中…' : 'Finalizing…'
  if (flowState.value === 'reviewing') return props.locale === 'zh' ? '终稿已就绪' : 'Transcript ready'
  if (flowState.value === 'linking') return props.locale === 'zh' ? '正在关联客户' : 'Linking client'
  if (flowState.value === 'summarizing') return props.locale === 'zh' ? 'AI 分析中' : 'AI analyzing'
  if (flowState.value === 'summarized') return props.locale === 'zh' ? '会谈摘要已生成' : 'Summary ready'
  return props.locale === 'zh' ? '准备就绪' : 'Ready'
})

const recordLabels = computed(() => ({
  hintIdle: props.locale === 'zh' ? '点击开始实时转写' : 'Tap to start live transcript',
  hintRecording: props.locale === 'zh' ? '点击停止并分析' : 'Tap to stop',
  hintProcessing: props.locale === 'zh' ? '终稿处理中…' : 'Finalizing…',
  hintStopped: props.locale === 'zh' ? '处理中' : 'Locked',
  ariaStart: props.locale === 'zh' ? '开始实时转写' : 'Start live transcript',
  ariaStop: props.locale === 'zh' ? '停止实时转写' : 'Stop live transcript',
  rec: props.locale === 'zh' ? '录音中' : 'LIVE',
  processing: props.locale === 'zh' ? '终稿处理中' : 'Finalizing',
}))

const captionLabels = computed(() => ({
  liveTag:
    pendingChunks.value > 0
      ? props.locale === 'zh'
        ? `· 实时识别（${pendingChunks.value} 段处理中）`
        : `· Live transcribing (${pendingChunks.value} in flight)`
      : props.locale === 'zh'
        ? '· 实时识别'
        : '· Live transcribing',
  analyzingTag: props.locale === 'zh' ? '终稿处理中…' : 'Finalizing…',
}))

const transcriptHint = computed(() => {
  if (hasDraftBubbles.value) {
    return props.locale === 'zh'
      ? '草稿转写，停止后完成终稿'
      : 'Draft transcript · finalized when you stop'
  }
  if (viewMode.value === 'speaker') {
    return props.locale === 'zh' ? `发言人：${speakerCount.value}` : `Speakers: ${speakerCount.value}`
  }
  if (transcriptText.value) {
    const lineCount = transcriptText.value.split('\n').filter(Boolean).length
    return props.locale === 'zh' ? `行数：${lineCount}` : `Lines: ${lineCount}`
  }
  return props.locale === 'zh' ? '开始说话后显示转写' : 'Speak to start…'
})

const summaryState = computed(() => {
  if (flowState.value === 'summarizing') return 'analyzing'
  if (flowState.value === 'summarized' && aiOutput.value) return 'ready'
  return 'collapsed'
})

const isReviewing = computed(() => flowState.value === 'reviewing')

const summaryLabels = computed(() => {
  if (props.locale === 'zh') {
    return {
      eyebrow: 'AI 智能纪要',
      title: '会谈分析',
      emptyText: '关联客户后，AI 将自动生成画像、风险偏好、议题与待办。',
      analysisKickoff: '已关联客户，正在启动 AI 分析…',
      analyzingKicker: 'AI 魔法 · 语义抽取',
      analyzingTitle: '正在分析对话语义并提取要点',
      analyzingSubtitle: '识别说话人 · 提炼信息 · 结构化…',
      stepDiarize: '说话人',
      stepExtract: '提炼',
      stepStructure: '结构化',
      summaryHeading: '会谈摘要',
      topicsHeading: '议题',
      actionsHeading: '智能待办',
      emailHeading: '跟进邮件草稿',
      createTask: '创建任务',
      added: '已添加',
      copyEmail: '复制邮件',
      notifyTaskCreated: '任务已添加',
      notifyEmailCopied: '邮件已复制',
    }
  }
  return {
    eyebrow: 'AI Notes',
    title: 'Meeting Analysis',
    emptyText: 'After linking a client, AI will generate profile, risks, topics, and follow-ups.',
    analysisKickoff: 'Client linked. Starting AI analysis…',
    analyzingKicker: 'AI Magic · Semantic Extraction',
    analyzingTitle: 'Analyzing dialogue and extracting key points',
    analyzingSubtitle: 'Speaker mapping · distillation · structuring…',
    stepDiarize: 'Diarize',
    stepExtract: 'Extract',
    stepStructure: 'Structure',
    summaryHeading: 'Meeting Summary',
    topicsHeading: 'Topics',
    actionsHeading: 'Action Items',
    emailHeading: 'Follow-up Email Draft',
    createTask: 'Create task',
    added: 'Added',
    copyEmail: 'Copy email',
    notifyTaskCreated: 'Task added',
    notifyEmailCopied: 'Email copied',
  }
})

const linkerLabels = computed(() => {
  if (props.locale === 'zh') {
    return {
      eyebrow: '关联客户',
      title: '关联客户',
      detected: '识别结果',
      speakerNote: `已识别 ${speakerCount.value} 位说话人`,
      tabExisting: '关联现有客户',
      tabNew: '新建客户',
      suggested: '推荐',
      confidence: '置信度',
      confidenceHigh: '高',
      confidenceMedium: '中',
      confidenceLow: '低',
      searchPlaceholder: '搜索客户',
      noMatch: '没有找到匹配客户',
      createNameLabel: '客户姓名',
      createIndustryLabel: '行业',
      createNamePlaceholder: '输入客户姓名',
      createIndustryPlaceholder: '输入行业（可选）',
      requiredNote: '可先返回修改转写，再继续关联。',
      cancel: '返回修改',
      confirmExisting: '确认关联',
      confirmNew: '创建并关联',
    }
  }
  return {
    eyebrow: 'Link Client',
    title: 'Link Client',
    detected: 'Detected',
    speakerNote: `${speakerCount.value} speakers detected`,
    tabExisting: 'Link existing',
    tabNew: 'Create new',
    suggested: 'Suggested',
    confidence: 'Confidence',
    confidenceHigh: 'High',
    confidenceMedium: 'Medium',
    confidenceLow: 'Low',
    searchPlaceholder: 'Search clients',
    noMatch: 'No matching client',
    createNameLabel: 'Client name',
    createIndustryLabel: 'Industry',
    createNamePlaceholder: 'Enter client name',
    createIndustryPlaceholder: 'Enter industry (optional)',
    requiredNote: 'You can go back and revise transcript, then continue linking.',
    cancel: 'Back to review',
    confirmExisting: 'Link selected',
    confirmNew: 'Create and link',
  }
})

const speakerCount = computed(() => Object.keys(speakers).length)

const hasDraftBubbles = computed(
  () => USE_VOLC && flowState.value === 'recording' && bubbles.value.some((b) => b.draft),
)
const showVolcDebug = computed(() => SHOW_VOLC_DEBUG && USE_VOLC && flowState.value === 'recording')
const volcDebugLine = computed(() => {
  const now = Date.now()
  const lastCommitAgoMs = volcCommitLastSentAt > 0 ? now - volcCommitLastSentAt : 0
  const age = volcCommitLastSentAt > 0 ? `${Math.round(lastCommitAgoMs / 100) / 10}s` : '-'
  return `P:${volcPreviewRequests} C:${volcCommitRequests}/${volcCommitAccepted} empty:${volcCommitEmpty} last:${age}`
})

function shouldPinTranscriptTail() {
  return (
    flowState.value === 'recording' ||
    flowState.value === 'processing' ||
    liveCaptionState.value !== 'idle'
  )
}

function scrollTranscriptToBottom() {
  const el = transcriptScrollerEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

/** After DOM updates from streaming text / new bubbles, keep the live caption row in view. */
function scheduleTranscriptAutoScroll() {
  if (!shouldPinTranscriptTail()) return
  nextTick(() => {
    requestAnimationFrame(() => scrollTranscriptToBottom())
  })
}

watch(
  [liveCaptionText, liveCaptionState, transcriptText, pendingChunks, flowState],
  scheduleTranscriptAutoScroll,
  { flush: 'post' },
)

watch(
  bubbles,
  scheduleTranscriptAutoScroll,
  { deep: true, flush: 'post' },
)

function ensureSpeaker(speakerId, preferredName = '') {
  if (speakers[speakerId]) return speakers[speakerId]
  const insertionIdx = Object.keys(speakers).length
  const colorIdx = insertionIdx % SPEAKER_PALETTE.length
  const sid = String(speakerId || '').toLowerCase()
  const isUnknown = !sid || sid.startsWith('unknown')
  // Always present multi-speaker as 1-indexed in the UI: first detected = "Speaker 1".
  const displayName = isUnknown
    ? (String(preferredName || '').trim() || 'Unconfirmed speaker')
    : (String(preferredName || '').trim() || `Speaker ${insertionIdx + 1}`)
  const avatarText = isUnknown ? '?' : String(insertionIdx + 1)
  speakers[speakerId] = {
    id: speakerId,
    role: displayName,
    color: SPEAKER_PALETTE[colorIdx],
    name: displayName,
    avatarText,
  }
  return speakers[speakerId]
}

/**
 * Drop speaker entries that no remaining bubble references (orphans created by
 * Volc per-session speaker_id reshuffling) and renumber auto-named, unlocked
 * speakers so the visible "Speaker N" labels match insertion order. Locked
 * speakers (carried from completed segments) are never modified.
 */
function pruneAndRenumberSpeakers() {
  const referenced = new Set()
  for (const b of bubbles.value) {
    if (!b || b.type === 'segment-divider') continue
    if (b.speakerId == null) continue
    referenced.add(String(b.speakerId))
  }
  for (const key of Object.keys(speakers)) {
    const k = String(key)
    if (!referenced.has(k) && !lockedSpeakerIds.has(k)) {
      delete speakers[key]
    }
  }
  const remaining = Object.keys(speakers)
  for (let i = 0; i < remaining.length; i += 1) {
    const key = remaining[i]
    const sp = speakers[key]
    if (!sp) continue
    if (lockedSpeakerIds.has(String(key))) continue
    const sid = String(key).toLowerCase()
    if (!sid || sid.startsWith('unknown')) continue
    if (!/^Speaker \d+$/.test(String(sp.name || ''))) continue
    const newName = `Speaker ${i + 1}`
    sp.name = newName
    sp.role = newName
    sp.avatarText = String(i + 1)
    sp.color = SPEAKER_PALETTE[i % SPEAKER_PALETTE.length]
  }
}

function bubbleAlignFor(speakerId) {
  const ids = Object.keys(speakers)
  return ids.indexOf(speakerId) % 2 === 0 ? 'left' : 'right'
}

function localizedClientName(client) {
  if (!client) return ''
  return props.locale === 'zh' ? (client.nameZh || client.nameEn || '') : (client.nameEn || client.nameZh || '')
}

function buildFinalizedTranscript() {
  const speakerList = Object.keys(speakers).map((id) => ({
    id,
    displayName: String(speakers[id]?.name || speakers[id]?.role || ''),
    color: String(speakers[id]?.color || ''),
  }))
  const segments = bubbles.value
    .filter((b) => b && b.type !== 'segment-divider')
    .map((b) => ({
      speakerId: String(b.speakerId || ''),
      startMs: Math.max(0, Number(b.startMs || 0)),
      endMs: Math.max(0, Number(b.endMs || b.startMs || 0)),
      text: String(b.text || '').trim(),
    }))
    .filter((s) => s.text)
  return {
    sessionId: sessionId.value,
    locale: props.locale,
    durationMs: elapsedSeconds.value * 1000,
    speakers: speakerList,
    segments,
  }
}

function applyLinkedSpeakerNames(client) {
  const ids = Object.keys(speakers)
  if (!ids.length) return
  const counsellor = props.locale === 'zh' ? '理财顾问' : 'Counsellor'
  const linkedName = localizedClientName(client) || (props.locale === 'zh' ? '客户' : 'Client')
  for (let i = 0; i < ids.length; i += 1) {
    const id = ids[i]
    const speaker = speakers[id]
    if (!speaker) continue
    let name = i === 0 ? counsellor : linkedName
    if (i > 1) {
      name = props.locale === 'zh' ? `${linkedName}（${i}）` : `${linkedName} #${i}`
    }
    speaker.name = name
    speaker.role = name
  }
}

async function persistMeetingState(status, extra = {}) {
  const payload = {
    id: currentMeetingId.value || undefined,
    schemaVersion: 1,
    status,
    locale: props.locale,
    transcript: buildFinalizedTranscript(),
    linkedClient: linkedClient.value,
    aiOutput: aiOutput.value,
    ...extra,
  }
  const saved = await meetingRepo.save(payload)
  currentMeetingId.value = saved.id
  return saved
}

async function finalizePostStopFlow() {
  const transcript = buildFinalizedTranscript()
  try {
    const extracted = await extractEntities(transcript)
    extractedClient.value = extracted?.extractedClient || null
  } catch {
    extractedClient.value = null
  }
  flowState.value = 'reviewing'
  try {
    await persistMeetingState('reviewing')
  } catch {
    // Ignore local persistence errors in demo/dev mode.
  }
}

function continueToLink() {
  flowState.value = 'linking'
  linkerOpen.value = true
}

function onLinkCancelled() {
  linkerOpen.value = false
  flowState.value = 'reviewing'
}

async function onLinked(payload) {
  let client = payload?.client
  if (!client) return
  if (payload?.type === 'new') {
    try {
      client = await clientRepo.createLocal(
        {
          name: localizedClientName(client),
          industry: props.locale === 'zh' ? client.industryZh : client.industryEn,
        },
        props.locale,
      )
      availableClients.value = await clientRepo.list()
    } catch {
      // Keep flow moving with in-memory client when local persistence fails.
    }
  }
  linkerOpen.value = false
  linkedClient.value = client
  applyLinkedSpeakerNames(client)
  flowState.value = 'summarizing'
  showToast({
    message:
      props.locale === 'zh'
        ? payload?.type === 'new'
          ? '已创建客户并关联'
          : '客户已关联'
        : payload?.type === 'new'
          ? 'Client created and linked'
          : 'Client linked',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1300,
  })
  try {
    await persistMeetingState('linked')
  } catch {
    // Ignore local persistence errors in demo/dev mode.
  }
  try {
    const req = {
      sessionId: sessionId.value,
      locale: props.locale,
      linkedClient: client,
      transcript: buildFinalizedTranscript(),
    }
    const result = await summarizeMeeting(req)
    aiOutput.value = result?.aiOutput || null
    summaryGeneratedAt.value = Date.now()
    flowState.value = 'summarized'
    try {
      await persistMeetingState('summarized')
    } catch {
      // Ignore local persistence errors in demo/dev mode.
    }
  } catch (error) {
    flowState.value = 'reviewing'
    showToast({
      message:
        props.locale === 'zh'
          ? 'AI 总结暂时不可用，请稍后重试'
          : error?.message || 'AI summary is temporarily unavailable',
      icon: 'cross',
      className: 'save-notes-toast',
      position: 'middle',
      duration: 1800,
    })
  }
}

function hydrateFromRecord(record) {
  if (!record) return
  currentMeetingId.value = String(record.id || '')
  linkedClient.value = record.linkedClient || null
  aiOutput.value = record.aiOutput || null
  summaryGeneratedAt.value = Number(record.updatedAt || 0)
  transcriptText.value = ''
  bubbles.value = []
  Object.keys(speakers).forEach((k) => delete speakers[k])
  bubbleSerial = 0

  const transcript = record.transcript || {}
  const speakerList = Array.isArray(transcript.speakers) ? transcript.speakers : []
  for (const sp of speakerList) {
    if (!sp?.id) continue
    speakers[sp.id] = {
      id: sp.id,
      role: sp.displayName || sp.id,
      color: sp.color || SPEAKER_PALETTE[Object.keys(speakers).length % SPEAKER_PALETTE.length],
      name: sp.displayName || sp.id,
      avatarText: String(Object.keys(speakers).length + 1),
    }
  }
  const segments = Array.isArray(transcript.segments) ? transcript.segments : []
  for (const seg of segments) {
    const text = String(seg?.text || '').trim()
    const sid = String(seg?.speakerId || '')
    if (!text || !sid) continue
    if (!speakers[sid]) ensureSpeaker(sid)
    bubbles.value.push({
      id: `restored_${bubbleSerial++}`,
      speakerId: sid,
      text,
      ts: formatClockFromMs(Number(seg.endMs || 0)),
      draft: false,
      startMs: Number(seg.startMs || 0),
      endMs: Number(seg.endMs || 0),
    })
    appendTranscriptLine(text)
  }
  flowState.value = record.status === 'summarized' ? 'summarized' : 'reviewing'
}

async function restoreLatestMeetingIfAny() {
  try {
    const list = await meetingRepo.list({ limit: 1 })
    if (!list.length) return
    hydrateFromRecord(list[0])
  } catch {
    // Keep Live page operational even if local DB unavailable.
  }
}

function resetSession(preserveConversation = false) {
  warnedDiarizationUnavailable = false
  finalQueue = []
  finalInFlight = 0
  finalDrainWaiters = []
  overlapTail = new Float32Array(0)
  lastSegmentFingerprint = ''
  liveCaptionText.value = ''
  liveCaptionState.value = 'idle'
  pendingChunks.value = 0
  if (!preserveConversation) {
    transcriptText.value = ''
    bubbles.value = []
    Object.keys(speakers).forEach((k) => delete speakers[k])
    lockedSpeakerIds = new Set()
    bubbleSerial = 0
    volcSegmentStartIndex = 0
    transcriptSegmentStartLength = 0
  } else {
    // Lock prior-segment speakers so their identity (number, color, name) is
    // never shuffled when the new segment's refresh prunes/renumbers.
    lockedSpeakerIds = new Set(Object.keys(speakers).map(String))
    pushSegmentDivider()
    volcSegmentStartIndex = bubbles.value.length
    transcriptSegmentStartLength = transcriptText.value.length
  }
  sessionId.value = crypto.randomUUID ? crypto.randomUUID() : `sess_${Date.now()}`
  chunkSeq.value = 0
  previewSeq.value = 0
  previewInFlight = 0
  recordedChunks = []
  volcPreviewInFlight = 0
  volcPreviewLastSentAt = 0
  volcPreviewLastText = ''
  volcPreviewParagraphText = ''
  recordedSamplesTotal = 0
  volcPreviewLastSentSamples = 0
  volcPreviewRequests = 0
  volcCommitInFlight = 0
  volcCommitLastSentAt = 0
  volcCommitLastSentSamples = 0
  volcCommittedSamples = 0
  volcRecentFingerprints = []
  volcCommitRequests = 0
  volcCommitAccepted = 0
  volcCommitEmpty = 0
  volcRefreshInFlight = 0
  volcRefreshLastSentAt = 0
  volcRefreshLastSentSamples = 0
  volcDraftBuffer = null
  volcVadPcmQueue = []
  volcCommitPending = false
}

function startTimer() {
  elapsedSeconds.value = 0
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

function stopTimer() {
  if (!timerInterval) return
  clearInterval(timerInterval)
  timerInterval = null
}

function appendTranscriptLine(text) {
  const t = String(text || '').trim()
  if (!t) return
  transcriptText.value = transcriptText.value ? `${transcriptText.value}\n${t}` : t
}

function formatDividerClock() {
  return new Date().toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function formatClockFromMs(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return formatDividerClock()
  const d = new Date(ms)
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function pushSegmentDivider() {
  bubbleSerial += 1
  const clock = formatDividerClock()
  const id = `seg_${bubbleSerial}_${Date.now()}`
  bubbles.value.push({
    id,
    type: 'segment-divider',
    ts: clock,
    label: props.locale === 'zh' ? '新的录音' : 'New recording',
  })
  appendTranscriptLine(`── ${clock} · ${props.locale === 'zh' ? '新的录音' : 'New recording'} ──`)
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const CHUNK_RETRY_BACKOFF_MS = [300, 800]

function isRetriableChunkError(err) {
  if (!err) return false
  if (err.retriableNetwork) return true
  const s = err.httpStatus
  if (typeof s === 'number' && s >= 500 && s <= 599) return true
  if (s === 429) return true
  return false
}

async function transcribeChunkAttempt(blob, seq) {
  // Legacy non-Volc path intentionally disabled in Doubao-only mode.
  void blob
  void seq
  const e = new Error('Legacy chunk API removed; use Doubao Volc endpoints.')
  e.httpStatus = 410
  throw e
}

async function transcribeChunk(blob, seq) {
  if (!blob || blob.size < 1024) return

  pendingChunks.value += 1
  liveCaptionText.value = 'Transcribing latest chunk...'

  try {
    for (let attempt = 0; attempt <= CHUNK_RETRY_BACKOFF_MS.length; attempt++) {
      try {
        await transcribeChunkAttempt(blob, seq)
        return
      } catch (err) {
        const lastTry = attempt >= CHUNK_RETRY_BACKOFF_MS.length
        if (!isRetriableChunkError(err) || lastTry) throw err
        await sleep(CHUNK_RETRY_BACKOFF_MS[attempt])
      }
    }
  } finally {
    pendingChunks.value = Math.max(0, pendingChunks.value - 1)
  }
}

async function transcribePreviewChunk(blob, seq) {
  // Legacy non-Volc preview path intentionally disabled in Doubao-only mode.
  void blob
  void seq
}


function releaseRecorder() {
  stopRecordingMitigations()
  if (vadTimer) {
    clearInterval(vadTimer)
    vadTimer = null
  }
  if (firstChunkTimer) {
    clearTimeout(firstChunkTimer)
    firstChunkTimer = null
  }
  if (chunkTimer) {
    clearInterval(chunkTimer)
    chunkTimer = null
  }
  if (audioNode) {
    try {
      audioNode.disconnect()
    } catch {
      /* noop */
    }
    audioNode = null
  }
  if (audioSinkNode) {
    try {
      audioSinkNode.disconnect()
    } catch {
      /* noop */
    }
    audioSinkNode = null
  }
  if (audioCtx) {
    try {
      audioCtx.close()
    } catch {
      /* noop */
    }
    audioCtx = null
  }
  pcmChunks = []
  volcVadPcmQueue = []
  overlapTail = new Float32Array(0)
  if (mediaStream) {
    for (const track of mediaStream.getTracks()) track.stop()
    mediaStream = null
  }
}

function concatFloat32(chunks) {
  const total = chunks.reduce((sum, c) => sum + c.length, 0)
  const out = new Float32Array(total)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

function normalizeChunkRms(float32, targetRms, maxGain) {
  if (!float32.length) return float32
  let sum = 0
  for (let i = 0; i < float32.length; i += 1) {
    const x = float32[i]
    sum += x * x
  }
  const rms = Math.sqrt(sum / float32.length)
  if (rms < 1e-8) return float32
  let g = targetRms / rms
  if (g > maxGain) g = maxGain
  if (g <= 1.001) return float32
  const out = new Float32Array(float32.length)
  for (let i = 0; i < float32.length; i += 1) {
    out[i] = Math.max(-1, Math.min(1, float32[i] * g))
  }
  return out
}

function resampleTo16k(input, sourceSampleRate) {
  if (!input.length || sourceSampleRate === TARGET_SAMPLE_RATE) return input
  const ratio = sourceSampleRate / TARGET_SAMPLE_RATE
  const outputLength = Math.max(1, Math.floor(input.length / ratio))
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i += 1) {
    const sourceIndex = i * ratio
    const index0 = Math.floor(sourceIndex)
    const index1 = Math.min(index0 + 1, input.length - 1)
    const frac = sourceIndex - index0
    output[i] = input[index0] + (input[index1] - input[index0]) * frac
  }
  return output
}

function floatTo16BitPCM(float32) {
  const pcm = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i += 1) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return pcm
}

function toWavBlobFromMonoFloat32(float32, sampleRate) {
  const pcm16 = floatTo16BitPCM(float32)
  const dataSize = pcm16.length * 2
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  const writeString = (offset, value) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < pcm16.length; i += 1, offset += 2) {
    view.setInt16(offset, pcm16[i], true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function extractTailWindow(chunks, sourceSampleRate, windowMs) {
  const targetSamples = Math.max(1, Math.floor((windowMs / 1000) * sourceSampleRate))
  if (!chunks.length) return new Float32Array(0)
  let collected = 0
  const selected = []
  for (let i = chunks.length - 1; i >= 0; i -= 1) {
    const c = chunks[i]
    selected.push(c)
    collected += c.length
    if (collected >= targetSamples) break
  }
  selected.reverse()
  const merged = concatFloat32(selected)
  if (merged.length <= targetSamples) return merged
  return merged.slice(merged.length - targetSamples)
}

function extractAudioFromAbsolute(chunks, sourceSampleRate, startSampleAbs, totalSampleAbs, maxWindowMs) {
  let wantSamples = Math.max(0, totalSampleAbs - startSampleAbs)
  if (wantSamples <= 0 || !chunks.length) return new Float32Array(0)
  if (maxWindowMs > 0) {
    const cap = Math.floor((maxWindowMs / 1000) * sourceSampleRate)
    if (cap > 0 && wantSamples > cap) wantSamples = cap
  }
  let collected = 0
  const selected = []
  for (let i = chunks.length - 1; i >= 0; i -= 1) {
    const c = chunks[i]
    selected.push(c)
    collected += c.length
    if (collected >= wantSamples) break
  }
  selected.reverse()
  const merged = concatFloat32(selected)
  if (merged.length <= wantSamples) return merged
  return merged.slice(merged.length - wantSamples)
}

async function sendVolcPreview() {
  if (!USE_VOLC || flowState.value !== 'recording' || !audioCtx) return
  if (volcPreviewInFlight > 0) return
  if (!recordedChunks.length) return
  const now = Date.now()
  if (now - volcPreviewLastSentAt < PREVIEW_MIN_GAP_MS) return
  const minNewSamples = Math.floor((VOLC_PREVIEW_MIN_NEW_MS / 1000) * (audioCtx.sampleRate || TARGET_SAMPLE_RATE))
  if (recordedSamplesTotal - volcPreviewLastSentSamples < minNewSamples) return

  const sourceRate = audioCtx.sampleRate || TARGET_SAMPLE_RATE
  const previewSource =
    recordedChunks.length > VOLC_PREVIEW_MAX_CHUNKS
      ? recordedChunks.slice(-VOLC_PREVIEW_MAX_CHUNKS)
      : recordedChunks
  const tail = extractTailWindow(previewSource, sourceRate, VOLC_PREVIEW_WINDOW_MS)
  if (!tail.length) return

  const resampled = resampleTo16k(tail, sourceRate)
  if (resampled.length < 2400) return
  const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
  const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)

  const formData = new FormData()
  formData.append('file', wavBlob, 'preview.wav')

  volcPreviewInFlight += 1
  volcPreviewRequests += 1
  volcPreviewLastSentAt = now
  volcPreviewLastSentSamples = recordedSamplesTotal
  pendingChunks.value += 1
  try {
    const res = await fetch(`${DIARIZATION_API_BASE}/api/process-voice-volc-preview`, {
      method: 'POST',
      body: formData,
    })
    const payload = await res.json().catch(() => ({}))
    if (!res.ok) return
    const text = String(payload?.text || '').trim()
    if (
      text &&
      flowState.value === 'recording' &&
      text !== volcPreviewLastText
    ) {
      const newNorm = text.replace(/\s+/g, ' ').trim()
      const oldNorm = String(volcPreviewLastText || '').replace(/\s+/g, ' ').trim()
      // Avoid jitter where interim result becomes shorter than what user already saw.
      if (oldNorm && oldNorm.length > newNorm.length && oldNorm.includes(newNorm)) {
        return
      }
      volcPreviewLastText = text
      liveCaptionState.value = 'streaming'
      // Build a paragraph-like rolling preview instead of replacing one sentence at a time.
      const paragraphNorm = String(volcPreviewParagraphText || '').replace(/\s+/g, ' ').trim()
      if (!paragraphNorm) {
        volcPreviewParagraphText = text
      } else if (newNorm.startsWith(paragraphNorm)) {
        // Model is extending previous text.
        volcPreviewParagraphText = text
      } else if (!paragraphNorm.includes(newNorm)) {
        // New phrase appears; append it once.
        volcPreviewParagraphText = `${volcPreviewParagraphText} ${text}`.trim()
      }
      // Keep preview readable and bounded.
      const capped = volcPreviewParagraphText.split(/\s+/).filter(Boolean).slice(-220).join(' ')
      volcPreviewParagraphText = capped
      liveCaptionText.value = capped
      if (
        /[.。!！?？…⋯]\s*$/u.test(capped) &&
        flowState.value === 'recording' &&
        pendingChunks.value <= 2
      ) {
        // Text boundary hint: ask commit path to try once silence/min-gap allow it.
        volcCommitPending = true
      }
    }
  } catch {
    // Keep recording smooth even if preview request fails.
  } finally {
    volcPreviewInFlight = Math.max(0, volcPreviewInFlight - 1)
    pendingChunks.value = Math.max(0, pendingChunks.value - 1)
  }
}

function normalizeForFingerprint(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[\s\u3000]+/g, '')
    .replace(/[\p{P}\p{S}]+/gu, '')
}

function isVolcLikelyFragment(text) {
  const raw = String(text || '').trim()
  if (!raw) return true
  const normLen = normalizeForFingerprint(raw).length
  if (normLen < VOLC_DRAFT_FRAGMENT_MIN_CHARS) return true
  if (/[.。!！?？…⋯]$/.test(raw)) return false
  return true
}

function mergeVolcText(left, right) {
  const a = String(left || '').trim()
  const b = String(right || '').trim()
  if (!a) return b
  if (!b) return a
  const na = normalizeForFingerprint(a)
  const nb = normalizeForFingerprint(b)
  if (!na) return b
  if (!nb) return a
  if (na === nb || na.includes(nb)) return a
  if (nb.includes(na)) return b
  return `${a}${/[。！？!?]$/.test(a) ? '' : ' '}${b}`.trim()
}

function pushVolcBubble(entry) {
  const sid = String(entry?.speakerId ?? '0')
  const speakerName = String(entry?.speakerName || '').trim()
  const speaker = ensureSpeaker(sid, speakerName)
  const label = speaker?.name || `Speaker ${sid}`
  const text = String(entry?.text || '').trim()
  const t0 = Number(entry?.startMs || 0)
  const t1 = Number(entry?.endMs || t0)
  if (!text) return false
  const norm = normalizeForFingerprint(text)
  if (!norm) return false
  const fp = `${sid}|${norm}`
  const dup = volcRecentFingerprints.some((prev) => {
    if (prev === fp) return true
    const [prevSid, prevNorm] = prev.split('|', 2)
    if (prevSid !== sid || !prevNorm) return false
    return prevNorm.includes(norm) || norm.includes(prevNorm)
  })
  if (dup) return false
  volcRecentFingerprints.push(fp)
  if (volcRecentFingerprints.length > 80) {
    volcRecentFingerprints = volcRecentFingerprints.slice(-80)
  }
  bubbles.value.push({
    id: ++bubbleSerial,
    speakerId: sid,
    text,
    ts: `${Math.floor(t0 / 1000)}s-${Math.floor(t1 / 1000)}s`,
    draft: Boolean(entry?.draft),
  })
  appendTranscriptLine(`[${label}] ${text}`)
  return true
}

function flushVolcDraftBuffer(force = false) {
  if (!volcDraftBuffer) return false
  const age = Date.now() - Number(volcDraftBuffer.updatedAt || 0)
  if (!force && age < VOLC_DRAFT_BUFFER_HOLD_MS) return false
  const next = volcDraftBuffer
  volcDraftBuffer = null
  return pushVolcBubble(next)
}

function replaceWithVolcConfirmedUtterances(utterances) {
  const prefix = bubbles.value.slice(0, volcSegmentStartIndex)
  const keptTranscript = transcriptText.value.slice(0, transcriptSegmentStartLength)
  bubbles.value = prefix
  transcriptText.value = keptTranscript
  volcRecentFingerprints = []
  volcDraftBuffer = null
  appendVolcUtterances(utterances, false)
  pruneAndRenumberSpeakers()
}

function appendVolcUtterances(utterances, incremental = false) {
  let emitted = 0
  for (const seg of utterances) {
    const text = String(seg?.text || '').trim()
    if (!text) continue
    const confidenceRaw = Number(seg?.speaker_confidence)
    const hasConfidence = Number.isFinite(confidenceRaw) && confidenceRaw > 0
    const uncertainSpeaker =
      Boolean(incremental) &&
      hasConfidence &&
      confidenceRaw < VOLC_DRAFT_SPEAKER_CONFIDENCE_MIN
    const sid = uncertainSpeaker ? 'unknown_live' : String(seg?.speaker_id ?? '0')
    const speakerName = uncertainSpeaker ? 'Unconfirmed speaker' : String(seg?.speaker_name || '').trim()
    const t0 = Number(seg?.time?.start_ms || 0)
    const t1 = Number(seg?.time?.end_ms || t0)
    const isFrag = incremental && isVolcLikelyFragment(text)
    const entry = {
      speakerId: sid,
      speakerName,
      text,
      startMs: t0,
      endMs: t1,
      draft: Boolean(incremental),
      updatedAt: Date.now(),
    }

    if (!incremental) {
      emitted += pushVolcBubble(entry) ? 1 : 0
      continue
    }

    if (!isFrag) {
      const shouldMergeBuffer =
        volcDraftBuffer &&
        volcDraftBuffer.speakerId === sid &&
        t0 - Number(volcDraftBuffer.endMs || 0) <= VOLC_DRAFT_BUFFER_MAX_GAP_MS
      if (shouldMergeBuffer) {
        volcDraftBuffer.text = mergeVolcText(volcDraftBuffer.text, text)
        volcDraftBuffer.endMs = Math.max(Number(volcDraftBuffer.endMs || t1), t1)
        volcDraftBuffer.updatedAt = Date.now()
        emitted += flushVolcDraftBuffer(true) ? 1 : 0
      } else {
        emitted += flushVolcDraftBuffer(true) ? 1 : 0
        emitted += pushVolcBubble(entry) ? 1 : 0
      }
      continue
    }

    if (
      volcDraftBuffer &&
      volcDraftBuffer.speakerId === sid &&
      t0 - Number(volcDraftBuffer.endMs || 0) <= VOLC_DRAFT_BUFFER_MAX_GAP_MS
    ) {
      volcDraftBuffer.text = mergeVolcText(volcDraftBuffer.text, text)
      volcDraftBuffer.endMs = Math.max(Number(volcDraftBuffer.endMs || t1), t1)
      volcDraftBuffer.updatedAt = Date.now()
      continue
    }

    emitted += flushVolcDraftBuffer(true) ? 1 : 0
    volcDraftBuffer = {
      ...entry,
    }
  }
  if (!incremental) {
    emitted += flushVolcDraftBuffer(true) ? 1 : 0
  } else {
    emitted += flushVolcDraftBuffer(false) ? 1 : 0
  }
  return emitted
}

async function sendVolcRefresh() {
  if (!USE_VOLC || flowState.value !== 'recording' || !audioCtx) return
  if (volcRefreshInFlight > 0 || volcCommitInFlight > 0) return
  if (!recordedChunks.length) return
  const now = Date.now()
  if (now - volcRefreshLastSentAt < VOLC_REFRESH_MIN_GAP_MS) return
  const sourceRate = audioCtx.sampleRate || TARGET_SAMPLE_RATE
  const minNewSamples = Math.floor((VOLC_REFRESH_MIN_NEW_MS / 1000) * sourceRate)
  if (recordedSamplesTotal - volcRefreshLastSentSamples < minNewSamples) return

  const raw = concatFloat32(recordedChunks)
  const resampled = resampleTo16k(raw, sourceRate)
  if (resampled.length < 6400) return
  const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
  const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)
  const formData = new FormData()
  formData.append('file', wavBlob, 'refresh.wav')
  formData.append('sessionId', sessionId.value)
  formData.append('mode', 'refresh')

  volcRefreshInFlight += 1
  volcRefreshLastSentAt = now
  volcRefreshLastSentSamples = recordedSamplesTotal
  pendingChunks.value += 1
  try {
    const res = await fetch(`${DIARIZATION_API_BASE}/api/process-voice-volc`, {
      method: 'POST',
      body: formData,
    })
    const payload = await res.json().catch(() => ({}))
    if (!res.ok) return
    const utterances = Array.isArray(payload?.utterances) ? payload.utterances : []
    if (!utterances.length) return
    replaceWithVolcConfirmedUtterances(utterances)
    if (flowState.value === 'recording') {
      liveCaptionText.value = ''
      liveCaptionState.value = 'streaming'
    }
  } catch {
    // keep recording smooth
  } finally {
    volcRefreshInFlight = Math.max(0, volcRefreshInFlight - 1)
    pendingChunks.value = Math.max(0, pendingChunks.value - 1)
  }
}

async function sendVolcCommit() {
  if (!USE_VOLC || flowState.value !== 'recording' || !audioCtx) return
  if (volcCommitInFlight > 0) return
  if (!recordedChunks.length) return
  const now = Date.now()
  const forceByTime = now - volcCommitLastSentAt >= VOLC_COMMIT_FORCE_GAP_MS
  if (!volcCommitPending && !forceByTime) return
  if (now - volcCommitLastSentAt < VOLC_COMMIT_MIN_GAP_MS && !forceByTime) return
  const sourceRate = audioCtx.sampleRate || TARGET_SAMPLE_RATE
  const minNewSamples = Math.floor((VOLC_COMMIT_MIN_NEW_MS / 1000) * sourceRate)
  const forceMinSamples = Math.floor((Math.min(VOLC_COMMIT_MIN_NEW_MS, 900) / 1000) * sourceRate)
  const overlapSamples = Math.floor((VOLC_COMMIT_OVERLAP_MS / 1000) * sourceRate)
  const totalAbs = recordedSamplesTotal
  // New-only audio length we have since last commit.
  const newOnly = totalAbs - Math.max(0, volcCommittedSamples)
  if (newOnly < minNewSamples && !forceByTime) return
  if (newOnly < forceMinSamples && forceByTime) return
  // Send a window that includes the previous overlap so diarization has
  // continuity context between sessions.
  const startAbs = Math.max(0, volcCommittedSamples - overlapSamples)

  const tail = extractAudioFromAbsolute(
    recordedChunks,
    sourceRate,
    startAbs,
    totalAbs,
    VOLC_COMMIT_MAX_WINDOW_MS,
  )
  if (!tail.length) return

  const resampled = resampleTo16k(tail, sourceRate)
  if (resampled.length < 6400) return
  const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
  const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)
  const formData = new FormData()
  formData.append('file', wavBlob, 'commit.wav')
  formData.append('sessionId', sessionId.value)
  formData.append('mode', 'incremental')

  volcCommitInFlight += 1
  volcCommitRequests += 1
  volcCommitPending = false
  volcCommitLastSentAt = now
  volcCommitLastSentSamples = totalAbs
  pendingChunks.value += 1
  try {
    const res = await fetch(`${DIARIZATION_API_BASE}/api/process-voice-volc`, {
      method: 'POST',
      body: formData,
    })
    const payload = await res.json().catch(() => ({}))
    if (!res.ok) return
    const utterances = Array.isArray(payload?.utterances) ? payload.utterances : []
    if (!utterances.length) {
      volcCommitEmpty += 1
      return
    }
    volcCommitAccepted += 1
    const added = appendVolcUtterances(utterances, true)
    // Even if this commit only produced buffered fragments (added=0), we must
    // advance committed audio. Otherwise next commit re-sends the same window
    // and live view keeps duplicating/re-collapsing text.
    volcCommittedSamples = totalAbs
    volcPreviewParagraphText = ''
    volcPreviewLastText = ''
    volcPreviewLastSentSamples = totalAbs
    if (added > 0 && flowState.value === 'recording') {
      liveCaptionText.value = ''
      liveCaptionState.value = 'streaming'
    }
  } catch {
    // keep recording smooth
  } finally {
    volcCommitInFlight = Math.max(0, volcCommitInFlight - 1)
    pendingChunks.value = Math.max(0, pendingChunks.value - 1)
  }
}


function notifyFinalDrainIfIdle() {
  if (finalQueue.length === 0 && finalInFlight === 0) {
    const waiters = finalDrainWaiters
    finalDrainWaiters = []
    for (const resolve of waiters) resolve()
  }
}

function pumpFinalQueue() {
  while (finalInFlight < MAX_FINAL_IN_FLIGHT && finalQueue.length) {
    const item = finalQueue.shift()
    finalInFlight += 1

    transcribeChunk(item.blob, item.seq)
      .catch((err) => {
          showToast({
          message: err?.message || 'Chunk transcription failed',
            icon: 'cross',
            className: 'save-notes-toast',
            position: 'middle',
          duration: 1800,
        })
      })
      .finally(() => {
        finalInFlight -= 1
        notifyFinalDrainIfIdle()
        pumpFinalQueue()
      })
  }
}

function scheduleFinalTranscribe(blob, seq) {
  // Keep utterance processing smooth by allowing a small number in-flight requests.
  finalQueue.push({ blob, seq })
  pumpFinalQueue()
}

function waitFinalDrain() {
  if (finalQueue.length === 0 && finalInFlight === 0) return Promise.resolve()
  return new Promise((resolve) => {
    finalDrainWaiters.push(resolve)
  })
}

function flushPcmChunk(force = false) {
  if (!pcmChunks.length || !audioCtx) return
  const chunk = concatFloat32(pcmChunks)
  pcmChunks = []
  const resampled = resampleTo16k(chunk, audioCtx.sampleRate || TARGET_SAMPLE_RATE)
  // Avoid sending tiny buffers early; this reduces diarization instability.
  if (!force && resampled.length < 6000) return

  // VAD: skip chunks that are basically silence.
  let sumSq = 0
  for (let i = 0; i < resampled.length; i += 1) {
    const x = resampled[i]
    sumSq += x * x
  }
  const rms = Math.sqrt(sumSq / Math.max(1, resampled.length))
  if (!force && rms < VAD_RMS_THRESHOLD) {
    // Reset overlap so silence doesn't poison the next window.
    overlapTail = new Float32Array(0)
    return
  }

  const overlapSamples = Math.max(0, Math.floor((CHUNK_OVERLAP_MS / 1000) * TARGET_SAMPLE_RATE))
  const combined = overlapTail.length
    ? concatFloat32([overlapTail, resampled])
    : resampled
  const leveled = normalizeChunkRms(combined, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
  const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)
  overlapTail =
    overlapSamples > 0 && combined.length > overlapSamples
      ? combined.slice(combined.length - overlapSamples)
      : combined
  const seq = chunkSeq.value
  chunkSeq.value += 1
  scheduleFinalTranscribe(wavBlob, seq)
}

/** Rolling ASR snippet used to tune how much acoustic silence counts as a "chat pause". */
function volcRollingPreviewForPause() {
  const statusish = /^Listening|^Capturing/i
  const p = String(volcPreviewParagraphText || '').trim()
  if (p && !statusish.test(p)) return p
  const live = String(liveCaptionText.value || '').trim()
  if (!live || statusish.test(live)) return ''
  return live
}

/**
 * How long the mic must stay quiet before we treat this as turn-taking silence (Volc commits).
 * Preview tail hints: sentence endings → shorter pause; commas / mid-line → moderate; bare tail → longer.
 */
function volcConversationSilenceThresholdMs() {
  const raw = volcRollingPreviewForPause()
  if (!raw) return VAD_END_SILENCE_MS
  const trimmed = raw.replace(/\s+$/gu, '')
  const last = trimmed.length ? [...trimmed].pop() : ''

  // Sentence/question/ellipsis endings — conversational turn likely; commit soon after acoustics pause.
  if (/[.。!！?？…⋯]/u.test(last)) {
    return Math.min(VAD_END_SILENCE_MS, VOLC_CHAT_PAUSE_SENTENCE_MS)
  }
  // Clause boundaries — pause may be filler, not speaker change; modest wait vs sentence/incomplete extremes.
  if (/[,，、；;:：]/u.test(last)) {
    const lo = Math.min(VAD_END_SILENCE_MS, VOLC_CHAT_PAUSE_SENTENCE_MS)
    const hi = VOLC_CHAT_PAUSE_INCOMPLETE_MS
    return Math.min(hi, Math.max(lo, VOLC_CHAT_PAUSE_CLAUSE_MS))
  }
  // Open bracket/quote often means unfinished — hold longer across brief silence.
  if (/["「『（《【"'“‘]/u.test(last)) {
    return Math.max(VAD_END_SILENCE_MS, VOLC_CHAT_PAUSE_INCOMPLETE_MS)
  }
  // Alphanumeric or other — likely mid-turn; tolerate longer hesitation before commit.
  return Math.max(VAD_END_SILENCE_MS, VOLC_CHAT_PAUSE_INCOMPLETE_MS)
}

/** Volc pipeline: RMS + conversational pause to avoid mid-sentence commits; pushes `volcCommitPending`. */
function evaluateVolcVadTick() {
  if (!USE_VOLC || !audioCtx || flowState.value !== 'recording') return

  const pauseNeedMs = volcConversationSilenceThresholdMs()

  if (!volcVadPcmQueue.length) {
    if (!inUtterance) return
    silenceMs += VAD_EVAL_INTERVAL_MS
    const utteranceMs = Date.now() - utteranceStartedAt
    const shouldEndBySilence = silenceMs >= pauseNeedMs
    const shouldEndByMaxTime = utteranceMs >= VAD_MAX_UTTERANCE_MS
    if (shouldEndBySilence || shouldEndByMaxTime) {
      inUtterance = false
      silenceMs = 0
      utteranceStartedAt = 0
      volcCommitPending = true
    }
    return
  }

  const frames = volcVadPcmQueue
  volcVadPcmQueue = []

  let sumSq = 0
  let n = 0
  for (const frame of frames) {
    for (let i = 0; i < frame.length; i += 1) {
      const x = frame[i]
      sumSq += x * x
      n += 1
    }
  }
  const rms = Math.sqrt(sumSq / Math.max(1, n))
  const speakingNow = rms >= VAD_RMS_THRESHOLD

  if (speakingNow) {
    if (!inUtterance) {
      inUtterance = true
      utteranceStartedAt = Date.now()
    }
    silenceMs = 0
    const utteranceMs = Date.now() - utteranceStartedAt
    if (utteranceMs >= VAD_MAX_UTTERANCE_MS) {
      inUtterance = false
      silenceMs = 0
      utteranceStartedAt = 0
      volcCommitPending = true
    }
    return
  }

  if (!inUtterance) return

  silenceMs += VAD_EVAL_INTERVAL_MS
  const utteranceMs = Date.now() - utteranceStartedAt

  const shouldEndBySilence = silenceMs >= pauseNeedMs
  const shouldEndByMaxTime = utteranceMs >= VAD_MAX_UTTERANCE_MS

  if (!shouldEndBySilence && !shouldEndByMaxTime) return

  inUtterance = false
  silenceMs = 0
  utteranceStartedAt = 0
  volcCommitPending = true
}

function evaluateVadTick() {
  if (!audioCtx) return

  // If no new frames arrived, treat it as silence so we can still end
  // an utterance (otherwise the UI can get stuck in Capturing speech…).
  if (!pcmChunks.length) {
    if (!inUtterance) return
    silenceMs += VAD_EVAL_INTERVAL_MS
    const utteranceMs = Date.now() - utteranceStartedAt
    const shouldEndBySilence = silenceMs >= VAD_END_SILENCE_MS
    const shouldEndByMaxTime = utteranceMs >= VAD_MAX_UTTERANCE_MS
    if (shouldEndBySilence || shouldEndByMaxTime) {
      inUtterance = false
      silenceMs = 0
      utteranceStartedAt = 0
      liveCaptionState.value = 'analyzing'
      liveCaptionText.value = 'Captured. Processing...'
      flushPcmChunk(true)
    }
    return
  }

  const newFrames = pcmChunks
  pcmChunks = []

  // Accumulate into the current utterance buffer.
  utteranceChunks = utteranceChunks.concat(newFrames)

  // Compute RMS over the newly captured frames.
  let sumSq = 0
  let n = 0
  for (const frame of newFrames) {
    for (let i = 0; i < frame.length; i += 1) {
      const x = frame[i]
      sumSq += x * x
      n += 1
    }
  }
  const rms = Math.sqrt(sumSq / Math.max(1, n))
  const speakingNow = rms >= VAD_RMS_THRESHOLD

  if (speakingNow) {
    if (!inUtterance) {
      inUtterance = true
      utteranceStartedAt = Date.now()
      previewParagraphText = ''
    }
    silenceMs = 0
    liveCaptionState.value = 'streaming'
    if (!liveCaptionText.value || liveCaptionText.value === 'Listening...' || liveCaptionText.value === 'Capturing speech…') {
    liveCaptionText.value = 'Capturing speech…'
  }

    // Build preview buffer (speaker-agnostic ASR) while speaking.
    previewPcmChunks = previewPcmChunks.concat(newFrames)
    for (const frame of newFrames) previewSamples += frame.length

    const minPreviewSamples = Math.floor((PREVIEW_MIN_MS / 1000) * TARGET_SAMPLE_RATE)
    const now = Date.now()

    if (
      previewSamples >= minPreviewSamples &&
      now - previewLastSentAt >= PREVIEW_MIN_GAP_MS
    ) {
      // Flush preview buffer.
      const previewChunk = concatFloat32(previewPcmChunks)
      previewPcmChunks = []
      previewSamples = 0
      previewLastSentAt = now

      const resampled = resampleTo16k(previewChunk, audioCtx.sampleRate || TARGET_SAMPLE_RATE)
      const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
      const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)

      if (previewInFlight === 0) {
        const seq = previewSeq.value
        previewSeq.value += 1
        previewInFlight += 1
        void transcribePreviewChunk(wavBlob, seq).finally(() => {
          previewInFlight -= 1
        })
      }
    }

        return
      }

  if (!inUtterance) return

  silenceMs += VAD_EVAL_INTERVAL_MS
  const utteranceMs = Date.now() - utteranceStartedAt

  const shouldEndBySilence = silenceMs >= VAD_END_SILENCE_MS
  const shouldEndByMaxTime = utteranceMs >= VAD_MAX_UTTERANCE_MS

  if (!shouldEndBySilence && !shouldEndByMaxTime) return

  // Utterance ended (silence or max time). Force-send what we have.
  inUtterance = false
  silenceMs = 0
  utteranceStartedAt = 0

  liveCaptionState.value = 'analyzing'
  liveCaptionText.value = 'Captured. Processing...'

  pcmChunks = utteranceChunks
  utteranceChunks = []
  flushPcmChunk(true)
}

async function requestWakeLock() {
  try {
    if (typeof navigator === 'undefined' || !('wakeLock' in navigator)) return
    wakeLockSentinel = await navigator.wakeLock.request('screen')
    wakeLockSentinel.addEventListener?.('release', () => {
      wakeLockSentinel = null
    })
  } catch {
    // Wake Lock can reject (no permission, low battery, unsupported); recording still works.
    wakeLockSentinel = null
  }
}

async function releaseWakeLock() {
  try {
    await wakeLockSentinel?.release?.()
  } catch {
    /* noop */
  }
  wakeLockSentinel = null
}

function handleAudioStateChange() {
  if (flowState.value !== 'recording' || !audioCtx) return
  if (audioCtx.state === 'suspended' || audioCtx.state === 'interrupted') {
    recordingInterrupted.value = true
    // Best-effort resume; on iOS lock this only succeeds once the page is visible again.
    void audioCtx.resume().catch(() => {})
  }
}

function handleVisibilityChange() {
  if (flowState.value !== 'recording') return
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
    // The page is backgrounded: the OS will (especially on iOS) suspend audio capture.
    recordingInterrupted.value = true
    return
  }
  // Returned to foreground while still recording: try to recover capture + screen lock.
  void audioCtx?.resume?.().catch(() => {})
  void requestWakeLock()
}

function startRecordingMitigations() {
  if (mitigationsActive) return
  mitigationsActive = true
  recordingInterrupted.value = false
  if (audioCtx) audioCtx.onstatechange = handleAudioStateChange
  void requestWakeLock()
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }
}

function stopRecordingMitigations() {
  if (!mitigationsActive) return
  mitigationsActive = false
  recordingInterrupted.value = false
  if (audioCtx) audioCtx.onstatechange = null
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
  void releaseWakeLock()
}

async function startLive() {
  const preserveConversation =
    (flowState.value === 'reviewing' || flowState.value === 'summarized') &&
    Boolean(bubbles.value.length || transcriptText.value.trim().length > 0)
  if (!preserveConversation) {
    extractedClient.value = null
    linkedClient.value = null
    aiOutput.value = null
    summaryGeneratedAt.value = 0
    currentMeetingId.value = ''
  }
  resetSession(preserveConversation)
  flowState.value = 'recording'
  liveCaptionState.value = 'streaming'
  liveCaptionText.value = 'Listening...'
  startTimer()

  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: ECHO_CANCEL,
      // Heavy NR often ducks quiet speech; disabling improves perceived sensitivity (more room noise).
      noiseSuppression: MIC_NOISE_SUPPRESSION,
      autoGainControl: true,
    },
  })
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    latencyHint: 'interactive',
  })
  await audioCtx.resume()
  startRecordingMitigations()

  const source = audioCtx.createMediaStreamSource(mediaStream)
  let tap = source
  if (MIC_GAIN !== 1) {
    const gainNode = audioCtx.createGain()
    gainNode.gain.value = MIC_GAIN
    source.connect(gainNode)
    tap = gainNode
  }

  if (USE_AUDIO_WORKLET && audioCtx.audioWorklet && typeof AudioWorkletNode !== 'undefined') {
    const url = new URL('../audio/pcm-worklet-processor.js', import.meta.url)
    await audioCtx.audioWorklet.addModule(url)
    const workletNode = new AudioWorkletNode(audioCtx, 'pcm-worklet', {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    })
    workletNode.port.onmessage = (evt) => {
      const channel = evt?.data
      if (channel instanceof Float32Array && channel.length) {
        recordedChunks.push(channel)
        recordedSamplesTotal += channel.length
        if (USE_VOLC) volcVadPcmQueue.push(channel)
        else pcmChunks.push(channel)
      }
    }
    const silentSink = audioCtx.createGain()
    silentSink.gain.value = 0
    tap.connect(workletNode)
    workletNode.connect(silentSink)
    silentSink.connect(audioCtx.destination)
    audioNode = workletNode
    audioSinkNode = silentSink
  } else {
    const scriptNode = audioCtx.createScriptProcessor(4096, 1, 1)
    scriptNode.onaudioprocess = (event) => {
      const channel = event.inputBuffer.getChannelData(0)
      const chunk = new Float32Array(channel)
      recordedChunks.push(chunk)
      recordedSamplesTotal += chunk.length
      if (USE_VOLC) volcVadPcmQueue.push(chunk)
      else pcmChunks.push(chunk)
    }
    tap.connect(scriptNode)
    scriptNode.connect(audioCtx.destination)
    audioNode = scriptNode
  }

  inUtterance = false
  silenceMs = 0
  utteranceChunks = []

  if (!USE_VOLC) {
    vadTimer = setInterval(() => {
      evaluateVadTick()
    }, VAD_EVAL_INTERVAL_MS)
  } else {
    volcCommitPending = false
    vadTimer = setInterval(() => {
      evaluateVolcVadTick()
      void sendVolcPreview()
      void sendVolcCommit()
      void sendVolcRefresh()
    }, VAD_EVAL_INTERVAL_MS)
  }
}

async function stopLive() {
  if (flowState.value !== 'recording') return
  flowState.value = 'processing'
  liveCaptionState.value = 'analyzing'
  stopTimer()

  if (USE_VOLC) {
    const sourceRate = audioCtx?.sampleRate || TARGET_SAMPLE_RATE
    releaseRecorder()
    // Mute the live caption while the final pass refines speaker assignments.
    liveCaptionText.value = ''
    try {
      const raw = concatFloat32(recordedChunks)
      const resampled = resampleTo16k(raw, sourceRate)
      const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
      const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)
      const formData = new FormData()
      formData.append('file', wavBlob, 'recording.wav')
      formData.append('sessionId', sessionId.value)
      formData.append('mode', 'final')
      const res = await fetch(`${DIARIZATION_API_BASE}/api/process-voice-volc`, {
        method: 'POST',
        body: formData,
      })
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(payload?.detail || `Volc ASR failed (${res.status})`)
      }
      const utterances = Array.isArray(payload?.utterances) ? payload.utterances : []
      // Single-session full-pass diarization is authoritative — replace the
      // incremental bubbles/speakers (which used per-commit cluster IDs that
      // can drift across sessions).
      replaceWithVolcConfirmedUtterances(utterances)
      liveCaptionText.value = utterances.length
        ? String(utterances[utterances.length - 1]?.text || '')
        : 'No speech recognized.'
      liveCaptionState.value = 'idle'
      await finalizePostStopFlow()
      return
    } catch {
      showToast({
        message: 'AI Service temporarily unavailable.',
        icon: 'cross',
        className: 'save-notes-toast',
        position: 'middle',
        duration: 1800,
      })
      flowState.value = 'idle'
      liveCaptionState.value = 'idle'
      return
    }
  }

  // Legacy non-Volc finalize path removed in Doubao-only mode.
  releaseRecorder()
  liveCaptionState.value = 'idle'
  await finalizePostStopFlow()
}

async function toggleRecording() {
  if (flowState.value === 'recording') {
    await stopLive()
    return
  }
  if (['processing', 'linking', 'summarizing'].includes(flowState.value)) return

  try {
    await startLive()
  } catch (err) {
    stopTimer()
    releaseRecorder()
    flowState.value = 'idle'
    liveCaptionState.value = 'idle'
    showToast({
      message: err?.message || 'Failed to start live transcript',
      icon: 'cross',
      className: 'save-notes-toast',
      position: 'middle',
      duration: 1800,
    })
  }
}

void clientRepo
  .list()
  .then((clients) => {
    if (Array.isArray(clients) && clients.length) {
      availableClients.value = clients
    }
  })
  .catch(() => {})

void restoreLatestMeetingIfAny()

watch(
  () => props.locale,
  () => {
    scheduleHeroTitleStep()
  },
)

onMounted(() => {
  heroTitleReduceMotion.value =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true
  scheduleHeroTitleStep()
})

onBeforeUnmount(() => {
  clearHeroTitleAnimation()
  stopTimer()
  releaseRecorder()
})
</script>

<template>
  <div class="live-shell">
    <section class="hero">
      <div class="hero-top">
        <div class="hero-left">
          <div class="hero-eyebrow">
            <span class="hero-eyebrow__kicker">{{ props.locale === 'zh' ? '会谈助手' : 'Counsellor Copilot' }}</span>
          </div>
          <h1 class="hero-title">
            <span class="hero-title__a11y">{{ heroTitleFull }}</span>
            <span class="hero-title__motion" aria-hidden="true">
              <span class="hero-title__typed">{{ heroTitleTyped }}</span>
              <span v-if="heroTitleTyped.length" class="hero-title__caret" />
            </span>
          </h1>
          <p class="hero-sub">
            {{
              props.locale === 'zh'
                ? '区分说话人，整理要点与待办，让您把精力放在客户与专业判断上。'
                : 'Speaker-aware notes and structured follow-ups—stay focused on the client and your professional judgment, not the notebook.'
            }}
          </p>
        </div>
        <div class="hero-right" aria-hidden="true">
          <div class="hero-art">
            <img
              class="hero-illustration"
              src="/images/live-hero-illustration.png"
              width="400"
              height="280"
              alt=""
              loading="eager"
              decoding="async"
            />
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <div class="card-head-left">
          <SessionStatusRail
            capsule
            :state="flowState"
            :label="statusLine"
            :elapsed="formattedElapsed"
            :pending-chunks="pendingChunks"
            :locale="props.locale"
          />
        </div>
        <span class="card-hint">
          {{ transcriptHint }}
        </span>
        <span v-if="showVolcDebug" class="debug-chip">{{ volcDebugLine }}</span>
      </div>

      <div
        v-if="flowState === 'recording'"
        class="record-guard"
        :class="{ 'record-guard--alert': recordingInterrupted }"
        role="status"
        aria-live="polite"
      >
        <span class="record-guard__text">
          <template v-if="recordingInterrupted">
            {{
              props.locale === 'zh'
                ? '录音可能已中断：请保持本页面在前台并亮屏，息屏或切换应用会停止采集。'
                : 'Recording may have paused: keep this page open and the screen on—locking or switching apps stops capture.'
            }}
          </template>
          <template v-else>
            {{
              props.locale === 'zh'
                ? '录音中：请保持屏幕常亮，勿锁屏或切换到其他应用。'
                : 'Recording: keep the screen on—do not lock the phone or switch apps.'
            }}
          </template>
        </span>
      </div>

      <div
        ref="transcriptScrollerEl"
        class="scroller"
        :class="{
          'scroller--empty': !transcriptText && !bubbles.length && liveCaptionState === 'idle',
          'scroller--live-tail': liveCaptionState !== 'idle',
        }"
      >
        <template v-if="viewMode === 'speaker' && bubbles.length">
          <template v-for="b in bubbles" :key="b.id">
            <div
              v-if="b.type === 'segment-divider'"
              class="segment-divider"
              role="separator"
              :aria-label="`${b.label} at ${b.ts}`"
            >
              <span class="segment-divider__line" aria-hidden="true" />
              <span class="segment-divider__text">{{ b.label }}</span>
              <span class="segment-divider__time">{{ b.ts }}</span>
              <span class="segment-divider__line" aria-hidden="true" />
            </div>
            <SpeakerBubble
              v-else
              :speaker="speakers[b.speakerId]"
              :text="b.text"
              :timestamp="b.ts"
              :draft="Boolean(b.draft)"
              :draft-plain="flowState === 'recording' && Boolean(b.draft)"
              :align="bubbleAlignFor(b.speakerId)"
              :editable="false"
            />
          </template>
        </template>
        <template v-else-if="transcriptText">
          <pre class="simple-transcript">{{ transcriptText }}</pre>
        </template>
        <template v-else-if="liveCaptionState === 'idle'">
          <div class="empty-hint" role="note" aria-label="tap the mic to start">
            <span class="empty-hint__text">
              {{
                props.locale === 'zh'
                  ? '点击下方麦克风开始实时转写'
                  : 'Tap the mic below to start'
              }}
            </span>
            <svg
              class="empty-hint__arrow"
              aria-hidden="true"
              viewBox="0 0 14 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M7 1v12M2 9l5 6 5-6"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
        </template>

        <LiveCaption
          :text="liveCaptionText"
          :state="liveCaptionState"
          :labels="captionLabels"
          pipeline-hint=""
        />
      </div>

      <RecordButton
        :state="flowState"
        :elapsed-seconds="elapsedSeconds"
        :labels="recordLabels"
        :inline="true"
        :processing-progress="flowState === 'processing' ? 0.6 : 0"
        @toggle="toggleRecording"
      />
    </section>

    <transition name="reveal">
      <div v-if="isReviewing" class="action-bar">
        <button type="button" class="primary-btn" @click="continueToLink">
          <Icon name="link-o" size="14" />
          {{ props.locale === 'zh' ? '继续 · 关联客户' : 'Continue · Link Client' }}
        </button>
      </div>
    </transition>

    <div class="summary-stack">
      <div v-if="flowState === 'summarizing'" class="analysis-kickoff">
        <Icon name="clock-o" size="13" />
        <span>{{ summaryLabels.analysisKickoff }}</span>
      </div>
      <SummaryPanel
        :state="summaryState"
        :ai-output="aiOutput"
        :locale="props.locale"
        :labels="summaryLabels"
        :generated-at="summaryGeneratedAt"
      />
    </div>

    <ClientLinker
      v-if="linkerOpen"
      :open="linkerOpen"
      :extracted-client="extractedClient"
      :clients="availableClients"
      :locale="props.locale"
      :labels="linkerLabels"
      :speaker-count="speakerCount"
      @link="onLinked"
      @cancel="onLinkCancelled"
    />
  </div>
</template>

<style scoped>
.live-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px 32px;
}

.hero {
  margin: 0 -16px;
  padding: 24px 22px 28px;
  background: var(--color-hero-bg);
  border-bottom: 1px solid var(--color-border);
  position: relative;
  overflow: visible;
  /* Extra bottom space so the illustration can “spill” without crowding the next block */
  margin-bottom: 4px;
}

/* Editorial grid — readable mesh; still vignettes at far edges */
.hero::before {
  content: "";
  position: absolute;
  inset: 0;
  --hero-grid-line: color-mix(in srgb, var(--color-text-primary) 10%, transparent);
  background-image:
    linear-gradient(var(--hero-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--hero-grid-line) 1px, transparent 1px);
  background-size: 22px 22px;
  background-position: -0.5px -0.5px;
  mask-image: radial-gradient(ellipse 115% 82% at 50% -8%, black 0%, black 38%, transparent 76%);
  -webkit-mask-image: radial-gradient(ellipse 115% 82% at 50% -8%, black 0%, black 38%, transparent 76%);
  pointer-events: none;
  z-index: 0;
  opacity: 1;
}

[data-theme="dark"] .hero::before {
  --hero-grid-line: color-mix(in srgb, var(--color-text-primary) 13%, transparent);
  opacity: 0.78;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .hero::before {
    --hero-grid-line: color-mix(in srgb, var(--color-text-primary) 13%, transparent);
    opacity: 0.78;
  }
}

.hero::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(800px 220px at -5% 0%, var(--color-wash-warm), transparent 72%),
    radial-gradient(600px 180px at 100% 20%, var(--color-accent-soft), transparent 70%);
  pointer-events: none;
  opacity: 0.75;
  z-index: 0;
}

[data-theme="dark"] .hero::after {
  opacity: 0.22;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .hero::after {
    opacity: 0.22;
  }
}

.hero-top {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.hero-left {
  flex: 1 1 auto;
  min-width: 0;
}

.hero-right {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  align-self: flex-end;
  width: auto;
  max-width: min(46%, 380px);
  min-width: 0;
  z-index: 2;
}

.hero-art {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  width: 100%;
  overflow: visible;
  pointer-events: none;
}

.hero-art::before {
  content: "";
  position: absolute;
  inset: 18% 8% 4%;
  border-radius: 40% 45% 50% 48%;
  background: radial-gradient(
    ellipse at 50% 70%,
    color-mix(in srgb, var(--color-accent) 22%, transparent),
    transparent 68%
  );
  filter: blur(18px);
  opacity: 0.85;
  pointer-events: none;
  z-index: 0;
}

.hero-illustration {
  --hero-art-scale: 1.14;
  position: relative;
  z-index: 1;
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  /* Layout box stays small; scale draws larger art past the hero without growing row height */
  max-height: clamp(108px, 26vw, 168px);
  object-fit: contain;
  object-position: 100% 100%;
  transform-origin: 100% 100%;
  /* Bleed past the hero’s box on the right and bottom (layout uses unscaled box + margins) */
  margin: 0 -6px -18px 0;
  filter: drop-shadow(0 20px 40px rgba(13, 61, 92, 0.14));
  animation: hero-art-float 6s ease-in-out infinite;
}

@keyframes hero-art-float {
  0%,
  100% {
    transform: translateY(0) scale(var(--hero-art-scale));
  }
  50% {
    transform: translateY(-5px) scale(var(--hero-art-scale));
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-illustration {
    animation: none;
    transform: scale(var(--hero-art-scale));
  }
}

.hero-eyebrow {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  row-gap: 6px;
  width: fit-content;
  font-family: var(--font-body);
}

.hero-eyebrow__kicker {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.hero-title {
  position: relative;
  margin: 6px 0 0;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.025em;
  line-height: 1.1;
  min-height: 1.15em;
}

.hero-title__a11y {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

.hero-title__motion {
  display: inline;
}

.hero-title__caret {
  display: inline-block;
  width: 0.09em;
  min-width: 2px;
  height: 0.92em;
  margin-left: 0.04em;
  vertical-align: -0.06em;
  border-radius: 1px;
  background: color-mix(in srgb, var(--color-accent) 92%, transparent);
  will-change: opacity;
  animation: hero-caret-blink 0.92s ease-in-out infinite;
}

@keyframes hero-caret-blink {
  0%,
  45% {
    opacity: 1;
  }
  50%,
  95% {
    opacity: 0.12;
  }
  100% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-title__caret {
    animation: none;
    opacity: 0.92;
  }
}

.hero-sub {
  margin: 8px 0 0;
  font-size: 13.5px;
  font-weight: 400;
  color: var(--color-text-secondary);
  line-height: 1.55;
  max-width: 56ch;
}

.notice {
  margin-top: 10px;
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--color-warning-soft);
  border: 1px solid color-mix(in srgb, var(--color-warning) 24%, transparent);
  color: var(--color-warning-text);
  font-size: 12px;
  line-height: 1.55;
}

.card {
  border-radius: var(--radius-xl);
  background: var(--color-card-bg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: nowrap;
  text-align: right;
  row-gap: 8px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-card-head-bg);
}

.card-head-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-shrink: 0;
}

.card-head-left :deep(.status-rail) {
  max-width: min(100%, 20rem);
}

.mode-chip {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--color-surface-subtle);
  border: 1px solid var(--color-border-strong);
  gap: 2px;
}

.mode-chip__btn {
  border: none;
  background: transparent;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 750;
  letter-spacing: 0.01em;
  border-radius: 999px;
  color: var(--color-text-secondary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.2s, color 0.2s, box-shadow 0.2s, opacity 0.2s;
  white-space: nowrap;
}

.mode-chip__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mode-chip__btn--active {
  background: var(--color-text-primary);
  color: var(--color-surface);
  box-shadow: 0 6px 14px -10px rgba(28, 25, 23, 0.25);
}

[data-theme="dark"] .mode-chip__btn--active {
  box-shadow: 0 6px 14px -10px rgba(0, 0, 0, 0.45);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .mode-chip__btn--active {
    box-shadow: 0 6px 14px -10px rgba(0, 0, 0, 0.45);
  }
}

.card-hint {
  font-size: 11.5px;
  font-weight: 650;
  letter-spacing: 0.01em;
  color: var(--color-text-secondary);
  margin-left: auto;
}

.debug-chip {
  font-size: 10px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--color-text-secondary);
  background: var(--color-surface-subtle);
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  padding: 2px 8px;
  white-space: nowrap;
}

.record-guard {
  margin: 8px 14px 8px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.record-guard--alert {
  color: #b45309;
}

[data-theme="dark"] .record-guard--alert {
  color: #fbbf24;
}

.scroller {
  padding: 16px 14px 12px;
  max-height: 52vh;
  min-height: 240px;
  overflow-y: auto;
  overflow-anchor: none;
  background: var(--color-surface);
  flex: 1;
}

[data-theme="dark"] .scroller {
  background: var(--color-bg);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .scroller {
    background: var(--color-bg);
  }
}

.scroller--live-tail {
  padding-bottom: 18px;
}

.scroller--live-tail > :deep(.live-caption) {
  scroll-margin-bottom: 10px;
}

.scroller--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding-block-end: 14px;
  gap: 10px;
}

/* Ultra-minimal hint — single line, muted colour, bouncing arrow toward mic */
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-text-muted);
  cursor: default;
  user-select: none;
}

/* Tiny animated downward-chevron SVG — sits just above the mic */
.empty-hint__arrow {
  width: 14px;
  height: 20px;
  color: var(--color-text-muted);
  opacity: 0.45;
  animation: hint-arrow-bounce 2.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes hint-arrow-bounce {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  40% {
    transform: translateY(5px);
    opacity: 0.75;
  }
  70% {
    transform: translateY(1px);
    opacity: 0.5;
  }
}

@media (prefers-reduced-motion: reduce) {
  .empty-hint__arrow {
    animation: none;
    opacity: 0.4;
  }
}

.empty-hint__text {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--color-text-muted);
  letter-spacing: 0.01em;
  opacity: 0.72;
}

[data-theme="dark"] .empty-hint__text {
  opacity: 0.55;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .empty-hint__text {
    opacity: 0.55;
  }
}

.simple-transcript {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--color-text-primary);
}

.segment-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0 10px;
}

.segment-divider__line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border-strong), transparent);
}

.segment-divider__text {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}

.segment-divider__time {
  flex-shrink: 0;
  font-size: 10.5px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

.action-bar {
  display: flex;
  gap: 10px;
  padding: 0 4px;
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  border: none;
  border-radius: 999px;
  padding: 10px 18px;
  background: linear-gradient(180deg, var(--color-accent) 0%, var(--color-accent-strong) 100%);
  color: var(--color-on-accent);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.1) inset,
    0 8px 22px -8px rgba(13, 61, 92, 0.45);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: box-shadow 0.2s, transform 0.15s, filter 0.2s;
}

.primary-btn:hover {
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.12) inset,
    0 12px 28px -8px rgba(13, 61, 92, 0.5);
  filter: brightness(1.02);
}

.primary-btn:active {
  transform: translateY(0.5px);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.08) inset,
    0 4px 12px -6px rgba(13, 61, 92, 0.4);
}

.summary-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.analysis-kickoff {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--color-accent-text);
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-soft);
}

[data-theme="dark"] .analysis-kickoff {
  color: var(--color-accent-text);
}

.reveal-enter-active,
.reveal-leave-active {
  transition: all 0.22s ease;
}

.reveal-enter-from,
.reveal-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

@media (max-width: 639px) {
  .live-shell {
    padding: 0 10px 22px;
    gap: 10px;
  }
  .hero {
    margin: 0 -10px;
    padding: 18px 12px 22px;
  }
  .hero-top {
    gap: 8px;
  }
  .hero-right {
    max-width: min(42%, 200px);
  }
  .hero-illustration {
    --hero-art-scale: 1.12;
    max-height: clamp(88px, 30vw, 120px);
    margin: 0 -4px -12px 0;
  }
  .hero-title {
    font-size: 22px;
  }
  .hero-sub {
    font-size: 12.5px;
    line-height: 1.5;
  }
  .card {
    border-radius: 16px;
  }
  .card-head {
    padding: 10px 12px;
  }
  .mode-chip {
    order: 3;
    width: 100%;
    justify-content: center;
  }
  .card-hint {
    order: 4;
    width: 100%;
    margin-left: 0;
    font-size: 11px;
  }
  .debug-chip {
    order: 5;
    width: fit-content;
  }
  .scroller {
    min-height: 200px;
    max-height: 48vh;
    padding: 12px 10px 10px;
  }
  .empty-hint__arrow {
    width: 12px;
    height: 17px;
  }
  .empty-hint__text {
    font-size: 11px;
  }
  .action-bar {
    flex-direction: column;
  }
  .primary-btn {
    width: 100%;
    min-height: 44px;
  }
}

@media (min-width: 640px) and (max-width: 899px) {
  .live-shell {
    padding: 0 14px 26px;
  }
  .hero {
    padding: 26px 22px 26px;
  }
  .hero-right {
    max-width: min(44%, 300px);
  }
  .hero-illustration {
    --hero-art-scale: 1.18;
    max-height: clamp(118px, 22vw, 155px);
    margin: 0 -8px -16px 0;
  }
  .hero-title {
    font-size: 30px;
  }
  .card-head {
    column-gap: 10px;
  }
  .scroller {
    min-height: 260px;
  }
}

@media (min-width: 900px) {
  .hero {
    padding: 32px 28px 32px;
  }
  .hero-top {
    gap: 20px;
  }
  .hero-right {
    max-width: min(44%, 400px);
  }
  .hero-illustration {
    --hero-art-scale: 1.24;
    max-height: clamp(150px, 16vw, 190px);
    margin: 0 -10px -22px 0;
  }
  .hero-title {
    font-size: 34px;
  }
  .hero-sub {
    font-size: 14px;
  }
  .scroller {
    height: clamp(320px, 52vh, 560px);
    max-height: 560px;
  }
}
</style>

