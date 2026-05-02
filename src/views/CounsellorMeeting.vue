<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Icon, showToast } from 'vant'
import {
  SCRIPTS,
  MOCK_CLIENTS,
  anonymousSpeakerLabel,
} from '../data/mockDialog.js'
import SpeakerBubble from '../components/SpeakerBubble.vue'
import RecordButton from '../components/RecordButton.vue'
import SummaryPanel from '../components/SummaryPanel.vue'
import ClientLinker from '../components/ClientLinker.vue'
import LiveCaption from '../components/LiveCaption.vue'
import SessionStatusRail from '../components/SessionStatusRail.vue'

const props = defineProps({
  locale: { type: String, default: 'zh' },
})

// ───────────────────────── i18n labels ─────────────────────────

const UI = {
  zh: {
    metaEyebrow: '财务咨询会谈',
    idleTitle: '新会谈',
    idleSubtitle: '准备好后，点击麦克风开始记录会谈',
    liveLabel: '会谈进行中',
    processingLabel: '正在终稿处理',
    reviewingLabel: '识别完成，确认说话人',
    speakers: '位发言人',
    placeholderTitle: '准备开始',
    placeholderHint: '点击下方麦克风按钮，开始记录与客户的会谈。',
    transcriptHeading: '会议转写',
    transcriptHintRecording: '录音中 · 实时识别',
    transcriptHintIdle: '尚未开始录音',
    transcriptHintProcessing: '终稿分析中，请稍候…',
    transcriptHintReviewing: '可重命名说话人，或继续关联客户',
    transcriptHintSummarized: '会谈已完成',
    liveCaptionTag: '· 实时识别',
    chunkAnalyzing: '正在分析这一段…',
    pipelineSingle: '上一段分析中',
    pipelineMulti: '{n} 段分析中',
    reviewTip: '可先修改说话人名称与内容，再继续关联客户',
    record: {
      hintIdle: '点击开始录音',
      hintRecording: '点击停止并分析',
      hintProcessing: '终稿处理中…',
      hintStopped: '录音已结束',
      ariaStart: '开始录音',
      ariaStop: '停止录音',
      rec: '录音中',
      processing: '终稿处理',
    },
    summary: {
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
    },
    actions: {
      save: '保存会谈',
      saved: '已保存',
      continueLink: '继续 · 关联客户',
      newMeeting: '新建会谈',
      switchScript: '切换演示脚本',
      confirmReset: '确定开始一次新会谈？当前对话将被清空。',
    },
    notify: {
      saved: '会谈已保存',
      reset: '已开始新会谈',
      switched: '已切换脚本',
      backToReview: '已返回修改模式',
      transcriptReady: '终稿已就绪',
      linkedExisting: '客户已关联，说话人已识别',
      linkedNew: '已创建客户并识别说话人',
    },
    scriptPickerTitle: '选择演示脚本',
    linker: {
      eyebrow: '关联客户',
      title: '关联客户',
      detected: '识别结果',
      speakerNote: '已识别 {n} 位说话人',
      tabExisting: '关联现有客户',
      tabNew: '新建客户',
      suggested: '推荐',
      searchPlaceholder: '搜索客户姓名…',
      emptySearch: '没有找到匹配的客户，请尝试新建',
      newHint: '我们已根据会谈内容预填了姓名，您可以根据需要修改。',
      nameLabel: '客户姓名',
      namePlaceholder: '例如：王女士',
      industryLabel: '行业 / 关注领域',
      industryPlaceholder: '例如：财富管理',
      requiredNote: '可先取消并返回修改对话，再继续关联',
      cancel: '取消',
      confirmExisting: '关联此客户',
      confirmNew: '创建并关联',
    },
  },
  en: {
    metaEyebrow: 'Financial Consultation',
    idleTitle: 'New Meeting',
    idleSubtitle: 'When you are ready, tap the mic to start capturing the conversation.',
    liveLabel: 'Meeting in progress',
    processingLabel: 'Finalizing transcript',
    reviewingLabel: 'Diarization done — confirm speakers',
    speakers: 'speakers',
    placeholderTitle: 'Ready to start',
    placeholderHint: 'Tap the mic below to begin capturing your conversation with the client.',
    transcriptHeading: 'Live Transcript',
    transcriptHintRecording: 'Recording · live transcript',
    transcriptHintIdle: 'Recording not started',
    transcriptHintProcessing: 'Final analysis in progress…',
    transcriptHintReviewing: 'You can rename speakers or continue to link a client',
    transcriptHintSummarized: 'Meeting completed',
    liveCaptionTag: '· Live transcribing',
    chunkAnalyzing: 'Analyzing this segment…',
    pipelineSingle: 'Previous analyzing',
    pipelineMulti: '{n} segments analyzing',
    reviewTip: 'You can edit speaker names and transcript before linking.',
    record: {
      hintIdle: 'Tap to start recording',
      hintRecording: 'Tap to stop and analyze',
      hintProcessing: 'Finalizing…',
      hintStopped: 'Recording ended',
      ariaStart: 'Start recording',
      ariaStop: 'Stop recording',
      rec: 'REC',
      processing: 'Finalizing',
    },
    summary: {
      eyebrow: 'AI Meeting Notes',
      title: 'Meeting Analysis',
      emptyText: 'After you link a client, AI will generate the profile, risk, topics, and follow-ups.',
      analysisKickoff: 'Client linked. Starting AI analysis…',
      analyzingKicker: 'AI Magic · Semantic Extraction',
      analyzingTitle: 'Analyzing the conversation and extracting insights',
      analyzingSubtitle: 'Diarizing speakers · distilling content · structuring…',
      stepDiarize: 'Diarize',
      stepExtract: 'Extract',
      stepStructure: 'Structure',
      summaryHeading: 'Meeting Summary',
      topicsHeading: 'Topics',
      actionsHeading: 'Smart Action Items',
      emailHeading: 'Follow-up Email Draft',
      createTask: 'Create Task',
      added: 'Added',
      copyEmail: 'Copy Email',
      notifyTaskCreated: 'Task added',
      notifyEmailCopied: 'Email copied',
    },
    actions: {
      save: 'Save Meeting',
      saved: 'Saved',
      continueLink: 'Continue · Link Client',
      newMeeting: 'New Meeting',
      switchScript: 'Switch Demo Script',
      confirmReset: 'Start a new meeting? The current conversation will be cleared.',
    },
    notify: {
      saved: 'Meeting saved',
      reset: 'New meeting started',
      switched: 'Script switched',
      backToReview: 'Back to review mode',
      transcriptReady: 'Final transcript ready',
      linkedExisting: 'Client linked, speakers identified',
      linkedNew: 'Client created, speakers identified',
    },
    scriptPickerTitle: 'Choose Demo Script',
    linker: {
      eyebrow: 'Link Client',
      title: 'Link Client',
      detected: 'Likely client',
      speakerNote: '{n} speakers detected',
      tabExisting: 'Link Existing',
      tabNew: 'Create New',
      suggested: 'Top match',
      searchPlaceholder: 'Search clients by name…',
      emptySearch: 'No matching clients — try creating a new one',
      newHint: "We've prefilled the name from the conversation. Adjust if needed.",
      nameLabel: 'Client name',
      namePlaceholder: 'e.g. Mrs. Wang',
      industryLabel: 'Industry / Focus',
      industryPlaceholder: 'e.g. Wealth Management',
      requiredNote: 'You can cancel to revise the transcript, then continue linking.',
      cancel: 'Cancel',
      confirmExisting: 'Link this client',
      confirmNew: 'Create and link',
    },
  },
}

const ui = computed(() => UI[props.locale])

// ───────────────────────── State ─────────────────────────

// 'idle' | 'recording' | 'processing' | 'reviewing' | 'linking' | 'summarizing' | 'summarized'
const flowState = ref('idle')
const elapsedSeconds = ref(0)
const activeScriptId = ref(SCRIPTS[0].id)
const showScriptPicker = ref(false)
const summaryGeneratedAt = ref(0)
// Single source of truth for demo-only UI blocks.
const isDemoMode = true
const showDemoTools = computed(() => isDemoMode)
const lastSavedAt = ref(0)

// Linked client information, set once user completes the ClientLinker step.
const linkedClient = ref(null)

// Tail-end "wrapping up last chunk" progress (0..1) — drives the dock bar
// after the user stops recording mid-flow.
const processingProgress = ref(0)

const activeScript = computed(() => SCRIPTS.find((s) => s.id === activeScriptId.value) ?? SCRIPTS[0])

// Reactive speaker registry. During recording all entries carry anonymous
// labels (说话人 1/2/3) and a numeric `avatarText`. After linking, names flip
// to the speakers' default real-world roles.
const speakers = reactive({})
const userRenamedIds = reactive(new Set())

// Bubbles already rendered in the transcript.
// Each entry: { id, speakerId, text, ts, entranceDelay }
const segments = ref([])

// Currently in-flight live caption (the chunk that's being heard right now).
const liveCaptionText = ref('')
// 'idle' | 'streaming' | 'analyzing'
//
// 'streaming'  — the most recent chunk's audio is being transcribed; cursor blinks.
// 'analyzing'  — only used after Stop, while the tail-flush of the very last
//                in-flight chunk is being processed.
// 'idle'       — caption block is hidden.
const liveCaptionState = ref('idle')

// How many chunks have been "sent to backend" but have not yet returned with
// diarized bubbles. While this is > 0 during recording, a small chip sits on
// the right side of the live-caption header to communicate that backstage
// work is running in parallel with the still-streaming caption.
const pendingAnalysisCount = ref(0)

const STORAGE_KEY = 'counsellor-meeting-history'

const transcriptScrollerRef = ref(null)

// Timeline timers we may need to cancel.
let timerInterval = null
let pendingTimers = []
let typingInterval = null
let summarizeTimeout = null
let processingInterval = null
let processingFinishTimeout = null

// Chunked-playback state. We track the active chunk so that a Stop pressed
// mid-chunk can flush the right segments.
let activeChunkIdx = -1
// Indices of segments in the active chunk that have NOT yet been promoted
// to a bubble.
let pendingSegmentsInChunk = []
// Map of chunkIdx → setTimeout id, for the in-flight backend "round-trips".
// Lets us cancel them on Stop and immediately drop their bubbles.
const analysisTimers = new Map()
// Queue of chunks whose analysis is in flight. We keep this so that Stop
// can immediately materialise their bubbles in the original chunk order.
const pendingAnalyses = []
// Enables multi-round recording in one meeting. After each stop, we remember
// which scripted chunk should be used when recording starts again.
let nextChunkIdx = 0

// ───────────────────────── Speaker resolution ─────────────────────────

function initAnonymousSpeakers() {
  Object.keys(speakers).forEach((k) => delete speakers[k])
  for (const sp of activeScript.value.speakers) {
    speakers[sp.id] = {
      id: sp.id,
      role: sp.role,
      color: sp.color,
      name: anonymousSpeakerLabel(sp.anonNumber, props.locale),
      avatarText: String(sp.anonNumber),
    }
  }
}

function applyRealNames() {
  for (const sp of activeScript.value.speakers) {
    if (!speakers[sp.id]) continue
    if (userRenamedIds.has(sp.id)) continue
    speakers[sp.id].name = props.locale === 'zh' ? sp.defaultNameZh : sp.defaultNameEn
    speakers[sp.id].avatarText = ''
  }
}

initAnonymousSpeakers()

// Re-resolve names when locale changes (only if user hasn't renamed).
watch(
  () => props.locale,
  () => {
    const showingRealNames = isLinking.value || isSummarizing.value || isSummarized.value || hasLinkedClient.value
    if (showingRealNames) {
      for (const sp of activeScript.value.speakers) {
        if (speakers[sp.id] && !userRenamedIds.has(sp.id)) {
          speakers[sp.id].name = props.locale === 'zh' ? sp.defaultNameZh : sp.defaultNameEn
        }
      }
    } else {
      for (const sp of activeScript.value.speakers) {
        if (speakers[sp.id] && !userRenamedIds.has(sp.id)) {
          speakers[sp.id].name = anonymousSpeakerLabel(sp.anonNumber, props.locale)
        }
      }
    }
  },
)

watch(
  () => activeScriptId.value,
  () => {
    userRenamedIds.clear()
    initAnonymousSpeakers()
  },
)

function renameSpeaker(speakerId, newName) {
  if (!speakers[speakerId]) return
  speakers[speakerId].name = newName
  speakers[speakerId].avatarText = ''
  userRenamedIds.add(speakerId)
}

// ───────────────────────── Computed view helpers ─────────────────────────

const speakerCount = computed(() => activeScript.value.speakers.length)
const formattedElapsed = computed(() => {
  const m = String(Math.floor(elapsedSeconds.value / 60)).padStart(2, '0')
  const s = String(elapsedSeconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

const isIdle = computed(() => flowState.value === 'idle')
const isRecording = computed(() => flowState.value === 'recording')
const isProcessing = computed(() => flowState.value === 'processing')
const isReviewing = computed(() => flowState.value === 'reviewing')
const isLinking = computed(() => flowState.value === 'linking')
const isSummarizing = computed(() => flowState.value === 'summarizing')
const isSummarized = computed(() => flowState.value === 'summarized')
const hasContent = computed(() => segments.value.length > 0)
const hasLinkedClient = computed(() => Boolean(linkedClient.value))

const summaryState = computed(() => {
  if (isSummarizing.value) return 'analyzing'
  if (isSummarized.value) return 'ready'
  return 'collapsed'
})

const transcriptHint = computed(() => {
  if (isRecording.value) {
    return pendingAnalysisCount.value > 0
      ? `${ui.value.transcriptHintRecording} · ${pipelineHint.value}`
      : ui.value.transcriptHintRecording
  }
  if (isProcessing.value) return ui.value.transcriptHintProcessing
  if (isReviewing.value || isLinking.value) return ui.value.transcriptHintReviewing
  if (isSummarized.value || isSummarizing.value) return ui.value.transcriptHintSummarized
  return ui.value.transcriptHintIdle
})

const headerTitle = computed(() => {
  if (linkedClient.value) {
    return props.locale === 'zh' ? activeScript.value.scenario.titleZh : activeScript.value.scenario.titleEn
  }
  return ui.value.idleTitle
})

const headerSubtitle = computed(() => {
  if (linkedClient.value) {
    const c = linkedClient.value
    const name = props.locale === 'zh' ? c.nameZh : c.nameEn
    const industry = props.locale === 'zh' ? c.industryZh : c.industryEn
    return `${name} · ${industry}`
  }
  const d = new Date()
  const dateStr = props.locale === 'zh'
    ? `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
    : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  return `${dateStr} · ${ui.value.metaEyebrow}`
})

const liveBannerText = computed(() => {
  if (isRecording.value) return ui.value.liveLabel
  if (isProcessing.value) return ui.value.processingLabel
  if (isReviewing.value || isLinking.value) return ui.value.reviewingLabel
  if (isSummarizing.value || isSummarized.value) return ui.value.transcriptHintSummarized
  return ui.value.transcriptHintIdle
})

const captionLabels = computed(() => ({
  liveTag: ui.value.liveCaptionTag,
  analyzingTag: ui.value.chunkAnalyzing,
}))

// Human-readable hint for the small pipeline chip in the caption header.
// Empty string means "don't render the chip" — the chip is the user-facing
// signal that backend processing is happening in parallel with the still-
// streaming caption.
const pipelineHint = computed(() => {
  const n = pendingAnalysisCount.value
  if (n <= 0) return ''
  if (n === 1) return ui.value.pipelineSingle
  return ui.value.pipelineMulti.replace('{n}', String(n))
})

// ───────────────────────── Playback driver ─────────────────────────

function pushTimer(t) {
  pendingTimers.push(t)
}

function clearAllTimers() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  for (const t of pendingTimers) {
    clearTimeout(t)
    clearInterval(t)
  }
  pendingTimers = []
  if (typingInterval) {
    clearInterval(typingInterval)
    typingInterval = null
  }
  if (summarizeTimeout) {
    clearTimeout(summarizeTimeout)
    summarizeTimeout = null
  }
  if (processingInterval) {
    clearInterval(processingInterval)
    processingInterval = null
  }
  if (processingFinishTimeout) {
    clearTimeout(processingFinishTimeout)
    processingFinishTimeout = null
  }
  for (const t of analysisTimers.values()) clearTimeout(t)
  analysisTimers.clear()
  pendingAnalyses.length = 0
  pendingAnalysisCount.value = 0
}

function buildStreamTokens(passage, isZh) {
  if (isZh) {
    const chunks = []
    for (let i = 0; i < passage.length; i += 4) {
      chunks.push(passage.slice(i, i + 4))
    }
    return chunks
  }
  return passage.split(/(\s+)/).filter(Boolean)
}

function scrollTranscriptToEnd() {
  nextTick(() => {
    const el = transcriptScrollerRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

let segmentSerial = 0

// Stream the text of a single segment into the live caption block.
// Returns a promise that resolves when the last token is on screen.
function streamCaption(segDef, isFirstInChunk) {
  return new Promise((resolve) => {
    const localeNow = props.locale
    const isZh = localeNow === 'zh'
    const fullText = isZh ? segDef.textZh : segDef.textEn
    const tokens = buildStreamTokens(fullText, isZh)
    let pointer = 0

    // First segment of a chunk starts a fresh paragraph — clear caption.
    // Subsequent segments append, separated by a thin space so the paragraph
    // reads continuously.
    if (isFirstInChunk) {
      liveCaptionText.value = ''
    } else if (liveCaptionText.value.length > 0) {
      liveCaptionText.value += ' '
    }

    const tickMs = isZh ? 80 : 95
    const interval = setInterval(() => {
      if (!isRecording.value) {
        clearInterval(interval)
        typingInterval = null
        resolve(false)
        return
      }
      if (pointer >= tokens.length) {
        clearInterval(interval)
        typingInterval = null
        resolve(true)
        return
      }
      liveCaptionText.value += tokens[pointer]
      pointer += 1
      scrollTranscriptToEnd()
    }, tickMs)
    typingInterval = interval
  })
}

// Stream every segment of a chunk into the caption, sequentially.
// Returns a promise that resolves when the chunk's caption is fully on
// screen (used by the pipeline driver to know "audio for this paragraph
// is closed; ship it to the backend").
function streamChunkCaption(chunkDef) {
  return new Promise(async (resolve) => {
    const segs = chunkDef.segmentIndices.map((i) => activeScript.value.segments[i])
    liveCaptionState.value = 'streaming'

    for (let i = 0; i < segs.length; i += 1) {
      if (!isRecording.value) return resolve(false)
      const segDef = segs[i]
      // Inter-segment delay — the natural pause between turns inside a chunk.
      await new Promise((r) => {
        const t = setTimeout(r, segDef.delayMs ?? 400)
        pushTimer(t)
      })
      if (!isRecording.value) return resolve(false)
      const finished = await streamCaption(segDef, i === 0)
      if (!finished) return resolve(false)
    }

    // Hold the fully-typed paragraph for ~250ms (VAD silence detection
    // window) before we say "this paragraph is closed".
    const t = setTimeout(() => resolve(true), 250)
    pushTimer(t)
  })
}

// Promote all segments in the (just-analyzed) chunk to bubbles, with a
// gentle stagger so the paragraph "lands" sequentially.
function emitChunkBubbles(chunkDef) {
  const STAGGER_MS = 90
  const ts = formattedElapsed.value
  const newOnes = []
  chunkDef.segmentIndices.forEach((segIdx, i) => {
    const segDef = activeScript.value.segments[segIdx]
    const fullText = props.locale === 'zh' ? segDef.textZh : segDef.textEn
    newOnes.push({
      id: ++segmentSerial,
      speakerId: segDef.speakerId,
      text: fullText,
      ts,
      entranceDelay: i * STAGGER_MS,
    })
  })
  segments.value.push(...newOnes)
  scrollTranscriptToEnd()
}

// Schedule the async "backend round-trip" for a closed chunk. The caption
// has already moved on to streaming the NEXT chunk by the time this fires,
// so when the timer expires the new bubbles drop in ABOVE the still-
// streaming caption — that's the user-visible pipeline.
function scheduleAnalysisForChunk(chunkIdx, chunkDef) {
  pendingAnalyses.push(chunkIdx)
  pendingAnalysisCount.value = pendingAnalyses.length

  const timer = setTimeout(() => {
    analysisTimers.delete(chunkIdx)
    const queueIdx = pendingAnalyses.indexOf(chunkIdx)
    if (queueIdx >= 0) pendingAnalyses.splice(queueIdx, 1)
    pendingAnalysisCount.value = pendingAnalyses.length
    emitChunkBubbles(chunkDef)
  }, chunkDef.processingMs ?? 800)

  analysisTimers.set(chunkIdx, timer)
}

// Pipelined recorder. Streams chunk N's caption, fires its analysis async,
// and IMMEDIATELY moves on to chunk N+1's caption — no waiting for the
// backend round-trip. The audio capture never pauses.
async function recordPipelineFrom(idx) {
  if (!isRecording.value) return
  const script = activeScript.value
  if (idx >= script.chunks.length) {
    autoFinishRecording()
    return
  }

  const chunkDef = script.chunks[idx]
  activeChunkIdx = idx
  pendingSegmentsInChunk = [...chunkDef.segmentIndices]

  const captionFinished = await streamChunkCaption(chunkDef)
  if (!isRecording.value || !captionFinished) return

  // The audio chunk is now closed. Fire the backstage analysis (it will
  // resolve later, possibly while the next chunk is mid-stream) and move on.
  pendingSegmentsInChunk = []
  scheduleAnalysisForChunk(idx, chunkDef)

  // A brief 220ms bridge — visually wipes the previous caption so the next
  // paragraph starts cleanly. Audio is still being captured throughout.
  const t = setTimeout(() => {
    if (!isRecording.value) return
    liveCaptionText.value = ''
    recordPipelineFrom(idx + 1)
  }, 220)
  pushTimer(t)
}

// Reached end of script while still recording — same effect as user pressing
// stop. Lets the demo finish gracefully.
function autoFinishRecording() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  nextChunkIdx = 0
  flushAndEnterProcessing(false)
}

// ───────────────────────── State machine actions ─────────────────────────

function toggleRecording() {
  if (isRecording.value) {
    stopRecording()
  } else if (flowState.value === 'idle') {
    startRecording({ append: false })
  } else if (isReviewing.value || isSummarized.value) {
    startRecording({ append: true })
  }
}

function startRecording({ append = false } = {}) {
  clearAllTimers()
  liveCaptionText.value = ''
  liveCaptionState.value = 'idle'
  if (!append) {
    segments.value = []
    elapsedSeconds.value = 0
    linkedClient.value = null
    userRenamedIds.clear()
    initAnonymousSpeakers()
    nextChunkIdx = 0
  }
  activeChunkIdx = -1
  pendingSegmentsInChunk = []
  flowState.value = 'recording'
  timerInterval = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
  recordPipelineFrom(nextChunkIdx)
}

function stopRecording() {
  // The user pressed stop. We need to:
  // 1. Cancel any pending streams / waits.
  // 2. Make sure any segments in the in-flight chunk get rendered (the
  //    backend would be processing the partial chunk on its end).
  // 3. Transition through a brief "processing" state into reviewing.
  flushAndEnterProcessing(true)
}

function flushAndEnterProcessing(userInitiated) {
  // Snapshot pipeline state BEFORE we wipe the timers — we need to know
  // what was in flight so we can flush it correctly.
  const inFlightChunkDefs = pendingAnalyses
    .map((idx) => activeScript.value.chunks[idx])
    .filter(Boolean)
  const tailSegments = pendingSegmentsInChunk.slice()
  const captionWasStreaming = liveCaptionText.value.length > 0
  const chunkCount = activeScript.value.chunks.length || 1
  nextChunkIdx = activeChunkIdx >= 0 ? (activeChunkIdx + 1) % chunkCount : 0

  // Cancel typing + bridge timers + analysis timers. Keep elapsed.
  if (typingInterval) {
    clearInterval(typingInterval)
    typingInterval = null
  }
  for (const t of pendingTimers) {
    clearTimeout(t)
    clearInterval(t)
  }
  pendingTimers = []
  for (const t of analysisTimers.values()) clearTimeout(t)
  analysisTimers.clear()
  pendingAnalyses.length = 0
  pendingAnalysisCount.value = 0

  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }

  pendingSegmentsInChunk = []

  // Materialise any backstage analyses that were still in flight when the
  // user hit stop. These represent paragraphs whose audio has been sent
  // to the backend but hasn't returned yet — in our mock they land
  // immediately, in original chunk order.
  inFlightChunkDefs.forEach((def) => {
    if (def) emitChunkBubbles(def)
  })

  // Tail flush: if Stop interrupted a chunk that was still streaming its
  // caption, we have segments that haven't been "sent" yet. Show one last
  // "analyzing" beat so the user sees the final paragraph being processed
  // before it lands as bubbles.
  if (tailSegments.length > 0 && activeChunkIdx >= 0) {
    const tail = {
      segmentIndices: tailSegments,
      processingMs: 0,
    }
    liveCaptionState.value = captionWasStreaming ? 'analyzing' : 'idle'
    const t1 = setTimeout(() => {
      liveCaptionState.value = 'idle'
      liveCaptionText.value = ''
      const t2 = setTimeout(() => {
        emitChunkBubbles(tail)
      }, 280)
      pushTimer(t2)
    }, userInitiated ? 520 : 0)
    pushTimer(t1)
  } else {
    liveCaptionState.value = 'idle'
    liveCaptionText.value = ''
  }

  if (segments.value.length === 0 && tailSegments.length === 0 && inFlightChunkDefs.length === 0) {
    // User pressed stop before any chunk arrived AND nothing was in flight.
    // Fall back to idle.
    flowState.value = 'idle'
    return
  }

  enterProcessing()
}

function enterProcessing() {
  flowState.value = 'processing'
  processingProgress.value = 0
  // Brief tail processing — covers the moment between the last chunk
  // appearing and the "transcript ready" toast.
  const totalMs = 1100
  const tickMs = 60
  const steps = totalMs / tickMs
  let i = 0
  processingInterval = setInterval(() => {
    i += 1
    processingProgress.value = Math.min(1, i / steps)
    if (i >= steps) {
      clearInterval(processingInterval)
      processingInterval = null
    }
  }, tickMs)
  processingFinishTimeout = setTimeout(() => {
    finishProcessing()
  }, totalMs)
}

function finishProcessing() {
  showToast({
    message: ui.value.notify.transcriptReady,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1300,
  })
  flowState.value = 'reviewing'
}

function continueToLink() {
  if (!isReviewing.value) return
  flowState.value = 'linking'
}

function onLinked(payload) {
  linkedClient.value = payload.client
  // Flip anonymous speaker labels to their real-world roles. The watcher
  // inside SpeakerBubble will animate the name swap on every visible bubble.
  applyRealNames()
  showToast({
    message: payload.type === 'existing' ? ui.value.notify.linkedExisting : ui.value.notify.linkedNew,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1500,
  })
  flowState.value = 'summarizing'
  summarizeTimeout = setTimeout(() => {
    flowState.value = 'summarized'
    summaryGeneratedAt.value = Date.now()
    summarizeTimeout = null
  }, 2600)
}

function onLinkCancelled() {
  if (!isLinking.value) return
  flowState.value = 'reviewing'
  showToast({
    message: ui.value.notify.backToReview,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1000,
  })
}

function saveMeeting() {
  if (!hasContent.value) return
  const c = linkedClient.value
  const payload = {
    scriptId: activeScript.value.id,
    locale: props.locale,
    title: props.locale === 'zh' ? activeScript.value.scenario.titleZh : activeScript.value.scenario.titleEn,
    client: c
      ? {
          id: c.id,
          name: props.locale === 'zh' ? c.nameZh : c.nameEn,
          industry: props.locale === 'zh' ? c.industryZh : c.industryEn,
          isNew: !!c.isNew,
        }
      : null,
    durationSec: elapsedSeconds.value,
    speakers: Object.values(speakers).map((s) => ({ id: s.id, name: s.name, role: s.role, color: s.color })),
    segments: segments.value.map((s) => ({
      speakerId: s.speakerId,
      text: s.text,
    })),
    savedAt: Date.now(),
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const list = raw ? JSON.parse(raw) : []
    list.push(payload)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    /* quota or private mode */
  }
  lastSavedAt.value = payload.savedAt
  showToast({
    message: ui.value.notify.saved,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1300,
  })
}

function confirmAndReset() {
  if (hasContent.value || flowState.value !== 'idle') {
    const ok = window.confirm(ui.value.actions.confirmReset)
    if (!ok) return
  }
  clearAllTimers()
  segments.value = []
  liveCaptionText.value = ''
  liveCaptionState.value = 'idle'
  elapsedSeconds.value = 0
  processingProgress.value = 0
  linkedClient.value = null
  summaryGeneratedAt.value = 0
  userRenamedIds.clear()
  initAnonymousSpeakers()
  activeChunkIdx = -1
  pendingSegmentsInChunk = []
  nextChunkIdx = 0
  flowState.value = 'idle'
  showToast({
    message: ui.value.notify.reset,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1100,
  })
}

function pickScript(id) {
  if (id === activeScriptId.value) {
    showScriptPicker.value = false
    return
  }
  clearAllTimers()
  segments.value = []
  liveCaptionText.value = ''
  liveCaptionState.value = 'idle'
  elapsedSeconds.value = 0
  processingProgress.value = 0
  linkedClient.value = null
  summaryGeneratedAt.value = 0
  activeChunkIdx = -1
  pendingSegmentsInChunk = []
  nextChunkIdx = 0
  flowState.value = 'idle'
  activeScriptId.value = id
  showScriptPicker.value = false
  showToast({
    message: ui.value.notify.switched,
    icon: 'success',
    className: 'save-notes-toast',
    position: 'middle',
    duration: 1100,
  })
}

function getSpeakerOf(seg) {
  return speakers[seg.speakerId]
}

function alignFor(seg) {
  // Counsellor on the left, anyone else on the right.
  const sp = getSpeakerOf(seg)
  if (!sp) return 'left'
  return sp.role === 'counsellor' ? 'left' : 'right'
}

const linkerLabels = computed(() => {
  // Splice the speaker count into the speaker note.
  const note = ui.value.linker.speakerNote.replace('{n}', String(speakerCount.value))
  return { ...ui.value.linker, speakerNote: note }
})

onBeforeUnmount(clearAllTimers)
</script>

<template>
  <div class="meeting-shell">
    <!-- ───────── Hero / meeting metadata ───────── -->
    <section class="meeting-hero" :class="{ 'meeting-hero--linked': hasLinkedClient }">
      <div class="hero-bg" aria-hidden="true">
        <span class="blob blob-1" />
        <span class="blob blob-2" />
        <div class="hero-grid" />
        <div class="hero-fade" />
      </div>
      <div class="hero-content">
        <div class="hero-eyebrow">
          <span class="hero-eyebrow__kicker">{{ ui.metaEyebrow }}</span>
          <SessionStatusRail
            capsule
            :state="flowState"
            :label="liveBannerText"
            :elapsed="formattedElapsed"
            :pending-chunks="pendingAnalysisCount"
            :locale="locale"
          />
        </div>
        <h1 class="hero-title">{{ headerTitle }}</h1>
        <div class="hero-subtitle">{{ headerSubtitle }}</div>
      </div>
    </section>

    <div class="meeting-main">
      <!-- ───────── Transcript with embedded record dock ───────── -->
      <section class="transcript-section">
        <div class="section-head">
          <div class="section-head-left">
            <Icon name="chat-o" size="14" />
            <span>{{ ui.transcriptHeading }}</span>
          </div>
          <span class="section-hint">{{ transcriptHint }}</span>
        </div>

        <div ref="transcriptScrollerRef" class="transcript-scroller" :class="{ 'transcript-scroller--empty': !hasContent && liveCaptionState === 'idle' }">
          <div v-if="hasContent && (isReviewing || isLinking)" class="review-tip">
            <Icon name="guide-o" size="12" />
            <span>{{ ui.reviewTip }}</span>
          </div>
          <template v-if="hasContent">
            <SpeakerBubble
              v-for="seg in segments"
              :key="seg.id"
              :speaker="getSpeakerOf(seg)"
              :text="seg.text"
              :timestamp="seg.ts"
              :align="alignFor(seg)"
              :editable="!isRecording && !isProcessing"
              :entrance-delay-ms="seg.entranceDelay"
              @rename="(name) => renameSpeaker(seg.speakerId, name)"
            />
          </template>
          <template v-else-if="liveCaptionState === 'idle'">
            <div class="empty-state">
              <div class="empty-icon">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  class="empty-mic-icon"
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
              </div>
              <div class="empty-title">{{ ui.placeholderTitle }}</div>
              <p class="empty-text">{{ ui.placeholderHint }}</p>
            </div>
          </template>

          <!-- v3.5: Live caption — single floating block with the in-flight
               chunk's raw transcribed audio. The optional pipelineHint chip
               shows that backstage analyses are running in parallel with the
               still-streaming caption. -->
          <LiveCaption
            :text="liveCaptionText"
            :state="liveCaptionState"
            :labels="captionLabels"
            :pipeline-hint="pipelineHint"
          />
        </div>

        <RecordButton
          :state="flowState"
          :elapsed-seconds="elapsedSeconds"
          :labels="ui.record"
          :inline="true"
          :processing-progress="processingProgress"
          @toggle="toggleRecording"
        />
      </section>

      <!-- ───────── Action bar ───────── -->
      <transition name="reveal">
        <div v-if="isReviewing" class="action-bar">
          <button
            type="button"
            class="primary-btn"
            @click="continueToLink"
          >
            <Icon name="link-o" size="14" />
            {{ ui.actions.continueLink }}
          </button>
          <button type="button" class="ghost-btn ghost-btn--subtle" @click="confirmAndReset">
            <Icon name="replay" size="14" />
            {{ ui.actions.newMeeting }}
          </button>
        </div>
      </transition>

      <transition name="reveal">
        <div v-if="isSummarized || isSummarizing" class="action-bar">
          <button type="button" class="primary-btn" :disabled="!hasContent || isSummarizing" @click="saveMeeting">
            <Icon name="bookmark-o" size="14" />
            {{ ui.actions.save }}
          </button>
          <button type="button" class="ghost-btn ghost-btn--subtle" @click="confirmAndReset">
            <Icon name="replay" size="14" />
            {{ ui.actions.newMeeting }}
          </button>
        </div>
      </transition>

    </div>

    <div class="summary-stack">
      <div v-if="isSummarizing" class="analysis-kickoff">
        <Icon name="clock-o" size="13" />
        <span>{{ ui.summary.analysisKickoff }}</span>
      </div>
      <SummaryPanel
        :state="summaryState"
        :ai-output="activeScript.aiOutput"
        :locale="locale"
        :labels="ui.summary"
        :generated-at="summaryGeneratedAt"
      />
      <div v-if="showDemoTools" class="demo-bottom-tools">
        <button type="button" class="demo-switch-btn demo-switch-btn--temporary" @click="showScriptPicker = true">
          <Icon name="exchange" size="13" />
          <span>{{ speakerCount }} {{ ui.speakers }}</span>
          <span class="demo-switch-divider" aria-hidden="true">·</span>
          <span>{{ ui.actions.switchScript }}</span>
        </button>
      </div>
    </div>

    <ClientLinker
      v-if="isLinking"
      :open="isLinking"
      :extracted-client="activeScript.extractedClient"
      :clients="MOCK_CLIENTS"
      :locale="locale"
      :labels="linkerLabels"
      :speaker-count="speakerCount"
      @link="onLinked"
      @cancel="onLinkCancelled"
    />

    <transition name="overlay">
      <div v-if="showScriptPicker" class="picker-overlay" @click.self="showScriptPicker = false">
        <div class="picker-card">
          <div class="picker-head">
            <div class="picker-title">{{ ui.scriptPickerTitle }}</div>
            <button type="button" class="picker-close" @click="showScriptPicker = false" :aria-label="'Close'">
              <Icon name="cross" size="16" />
            </button>
          </div>
          <div class="picker-list">
            <button
              v-for="s in SCRIPTS"
              :key="s.id"
              type="button"
              class="picker-item"
              :class="{ 'picker-item--active': s.id === activeScriptId }"
              @click="pickScript(s.id)"
            >
              <div class="picker-item-title">
                {{ locale === 'zh' ? s.scenario.titleZh : s.scenario.titleEn }}
              </div>
              <div class="picker-item-meta">
                {{ s.speakers.length }} {{ ui.speakers }}
                <span>· {{ s.chunks.length }} {{ locale === 'zh' ? '段落' : 'chunks' }}</span>
              </div>
              <Icon
                v-if="s.id === activeScriptId"
                name="success"
                size="14"
                class="picker-item-check"
              />
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.meeting-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 0 16px 32px;
}

/* ───────── Hero ───────── */
.meeting-hero {
  position: relative;
  margin: 0 -16px;
  padding: 12px 20px 14px;
  overflow: hidden;
  background: var(--color-hero-bg);
  transition: background 0.6s ease;
}

.meeting-hero--linked {
  background: var(--color-hero-bg);
}

.hero-bg {
  display: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(52px);
  opacity: 0.36;
  will-change: transform;
}

.blob-1 {
  width: 240px; height: 240px;
  background: radial-gradient(circle at 30% 30%, var(--color-accent) 0%, transparent 70%);
  top: -90px; left: -70px;
  animation: drift-a 22s ease-in-out infinite;
}

.blob-2 {
  width: 220px; height: 220px;
  background: radial-gradient(circle, #c4b5fd 0%, rgba(196, 181, 253, 0) 70%);
  top: -50px; right: -60px;
  animation: drift-b 26s ease-in-out infinite;
}

@keyframes drift-a {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(25px, 18px, 0) scale(1.1); }
}
@keyframes drift-b {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(-30px, 25px, 0) scale(1.08); }
}

.hero-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(15, 36, 75, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 36, 75, 0.05) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: radial-gradient(ellipse at 50% 30%, black 20%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 30%, black 20%, transparent 75%);
  opacity: 0.42;
}

.hero-fade {
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 50px;
  background: linear-gradient(180deg, rgba(247, 249, 253, 0) 0%, #f7f9fd 100%);
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  row-gap: 6px;
}

.hero-eyebrow__kicker {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.hero-title {
  margin: 6px 0 2px;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.025em;
  line-height: 1.15;
  font-family: "Lora", Georgia, "Times New Roman", serif;
  transition: color 0.4s ease;
}

.hero-subtitle {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
}

.hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  color: var(--color-text-primary);
  font-size: 11.5px;
  font-weight: 500;
  box-shadow: 0 3px 10px -8px rgba(28, 25, 23, 0.1);
  transition: background 0.4s ease, color 0.4s ease, border-color 0.4s ease;
}

/* ───────── Transcript ───────── */
.transcript-section {
  position: relative;
  margin-top: -10px;
  border-radius: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 14px 28px -24px rgba(28, 25, 23, 0.12);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.meeting-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  row-gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-card-head-bg);
}

.section-head-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.section-hint {
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--color-text-secondary);
  margin-left: auto;
}

.transcript-scroller {
  padding: 16px 14px 12px;
  max-height: 50vh;
  min-height: 240px;
  overflow-y: auto;
  background: var(--color-surface);
  flex: 1;
}

.review-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 8px;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 650;
  color: var(--color-text-secondary);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
}

.transcript-scroller--empty {
  display: grid;
  place-items: center;
  text-align: center;
}

.empty-state {
  padding: 20px 12px;
  color: #94a3b8;
}

.empty-icon {
  width: 44px;
  height: 44px;
  border-radius: 999px;
  margin: 0 auto 10px;
  display: grid;
  place-items: center;
  background: var(--color-surface);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border-strong);
}

.empty-mic-icon {
  width: 18px;
  height: 18px;
  color: var(--color-text-muted);
}

.empty-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.empty-text {
  margin: 0 auto;
  font-size: 12px;
  color: var(--color-text-muted);
  line-height: 1.6;
  max-width: 28ch;
}

/* ───────── Action bar ───────── */
.action-bar {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 12px;
  padding: 0 4px;
}

.primary-btn,
.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.15s, box-shadow 0.2s, background 0.2s;
  flex: 1 1 auto;
  justify-content: center;
}

.primary-btn {
  background: linear-gradient(180deg, var(--color-accent) 0%, var(--color-accent-strong) 100%);
  color: var(--color-on-accent);
  box-shadow: 0 8px 18px -10px rgba(13, 61, 92, 0.4);
  flex-grow: 2;
  flex-basis: 100%;
  transition: box-shadow 0.2s, transform 0.15s;
}

.primary-btn:hover:not(:disabled) {
  box-shadow: 0 10px 22px -10px rgba(13, 61, 92, 0.5);
}

.primary-btn:disabled {
  background: #94a3b8;
  color: #f5f5f4;
  box-shadow: none;
  cursor: not-allowed;
}

.primary-btn:not(:disabled):active {
  transform: translateY(0.5px);
  box-shadow: 0 4px 10px -6px rgba(13, 61, 92, 0.4);
}

.ghost-btn {
  background: var(--color-surface);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-strong);
}

.ghost-btn:disabled {
  color: var(--color-text-muted);
  border-color: var(--color-border);
  background: var(--color-surface);
  cursor: not-allowed;
}

.ghost-btn:not(:disabled):active {
  background: rgba(148, 163, 184, 0.16);
  transform: translateY(0.5px);
}

.ghost-btn--subtle {
  color: var(--color-text-secondary);
  border-color: var(--color-border-strong);
}

.analysis-kickoff {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--color-accent-text);
  background: var(--color-accent-soft);
  border: 1px solid color-mix(in srgb, var(--color-accent) 24%, transparent);
}

/* ───────── Demo bottom utilities ───────── */
.demo-bottom-tools {
  display: flex;
  justify-content: center;
  padding: 0 4px 2px;
}

.demo-switch-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  border: 1px solid rgba(13, 61, 92, 0.2);
  background: var(--color-surface);
  color: var(--color-accent);
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.demo-switch-btn--temporary {
  background: rgba(248, 250, 252, 0.55);
  border: 1px dashed rgba(100, 116, 139, 0.28);
  color: #475569;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.015em;
  box-shadow: none;
}

.demo-switch-btn:active {
  background: rgba(13, 61, 92, 0.08);
  transform: translateY(0.5px);
}

.demo-switch-divider {
  color: rgba(37, 99, 235, 0.45);
  font-weight: 600;
}

/* ───────── Picker overlay ───────── */
.picker-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(2px);
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 20px;
}

.picker-card {
  width: 100%;
  max-width: 360px;
  background: var(--color-surface);
  border-radius: 20px;
  padding: 16px;
  box-shadow: 0 30px 60px -30px rgba(28, 25, 23, 0.3);
}

.picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.picker-title {
  font-size: 14px;
  font-weight: 700;
  color: #0b1f3a;
}

.picker-close {
  border: none;
  background: #f1f5f9;
  color: #475569;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.picker-close:active {
  background: #e2e8f0;
}

.picker-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.picker-item {
  position: relative;
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-surface);
  padding: 12px 36px 12px 14px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: border-color 0.2s, background 0.2s;
}

.picker-item:active {
  background: #f1f5fb;
}

.picker-item--active {
  border-color: rgba(13, 61, 92, 0.4);
  background: rgba(13, 61, 92, 0.06);
}

.picker-item-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.picker-item-meta {
  font-size: 11.5px;
  color: #64748b;
  margin-top: 2px;
}

.picker-item-check {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-accent);
}

/* ───────── Transitions ───────── */
.reveal-enter-active,
.reveal-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.reveal-enter-from,
.reveal-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.22s ease;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

/* Keep mobile compact; desktop gets extra breathing room */
@media (max-width: 899px) {
  .meeting-shell {
    padding-top: 0;
  }
  .action-bar {
    gap: 10px;
  }
  .primary-btn,
  .ghost-btn {
    min-height: 44px;
  }
}

@media (max-width: 639px) {
  .meeting-shell {
    padding: 0 10px 24px;
    gap: 10px;
  }
  .meeting-hero {
    margin: 0 -10px;
    padding: 10px 14px 10px;
  }
  .hero-title {
    font-size: 18px;
  }
  .hero-subtitle {
    font-size: 11px;
    line-height: 1.45;
  }
  .transcript-section {
    border-radius: 16px;
  }
  .section-head {
    padding: 10px 12px;
  }
  .section-head-left {
    font-size: 11.5px;
  }
  .section-hint {
    width: 100%;
    margin-left: 0;
    font-size: 11px;
  }
  .transcript-scroller {
    min-height: 200px;
    max-height: 48vh;
    padding: 12px 10px 10px;
  }
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .primary-btn,
  .ghost-btn {
    flex-basis: auto;
    width: 100%;
  }
  .picker-overlay {
    padding: 12px;
  }
  .picker-card {
    max-width: 100%;
    border-radius: 16px;
    padding: 12px;
  }
}

@media (min-width: 640px) and (max-width: 899px) {
  .meeting-shell {
    padding: 0 14px 28px;
  }
  .transcript-scroller {
    min-height: 260px;
  }
  .picker-card {
    max-width: 420px;
  }
}

/* ───────── Desktop two-column layout ───────── */
@media (min-width: 900px) {
  .meeting-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
    grid-template-areas:
      "hero hero"
      "main summary";
    gap: 14px 18px;
    padding-top: 16px;
  }

  .meeting-hero { grid-area: hero; margin: 0; border-radius: 24px; padding: 22px 26px 28px; }
  .meeting-main { grid-area: main; align-self: start; }
  .transcript-section { margin-top: 0; }
  .transcript-scroller {
    height: clamp(320px, 52vh, 560px);
    min-height: 320px;
    max-height: 560px;
    flex: 0 0 auto;
  }

  .meeting-shell > .summary-stack { grid-area: summary; align-self: start; }
  .picker-overlay { grid-column: 1 / -1; }
}
</style>
