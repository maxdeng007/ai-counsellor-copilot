<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { Icon, showConfirmDialog, showToast } from 'vant'

const props = defineProps({
  locale: { type: String, default: 'zh' },
})

const isZh = computed(() => props.locale === 'zh')

const DIARIZATION_API_BASE = import.meta.env?.VITE_DIARIZATION_API_BASE || 'http://localhost:8090'
const TARGET_SAMPLE_RATE = 16000
const CHUNK_TARGET_RMS = 0.075
const CHUNK_RMS_MAX_GAIN = 8

const t = computed(() => {
  const zh = isZh.value
  return {
    title: zh ? '声纹注册' : 'Voiceprint',
    subtitle: zh ? '录制 8–12 秒清晰语音，用于在转写中显示姓名' : 'Record 8–12s clear speech to label speakers in transcripts',
    nameLabel: zh ? '显示名称' : 'Display name',
    namePlaceholder: zh ? '例如：张三' : 'e.g. Alice',
    profileIdLabel: zh ? '已有档案 ID（可选，用于追加样本）' : 'Existing profile ID (optional)',
    record: zh ? '开始录制' : 'Record',
    stop: zh ? '停止并注册' : 'Stop & enroll',
    recording: zh ? '录制中…' : 'Recording…',
    listTitle: zh ? '已注册' : 'Registered',
    empty: zh ? '暂无档案，请先录制注册。' : 'No profiles yet.',
    samples: zh ? '样本' : 'samples',
    delete: zh ? '删除' : 'Delete',
    refresh: zh ? '刷新' : 'Refresh',
    uploadHint: zh ? '或上传 WAV 文件' : 'Or upload WAV',
    loading: zh ? '加载中…' : 'Loading…',
    needName: zh ? '请填写显示名称' : 'Enter a display name',
    tooShort: zh ? '录音太短，请至少录 2 秒' : 'Too short — record at least 2s',
    enrollOk: zh ? '注册成功' : 'Enrolled',
    enrollFail: zh ? '注册失败' : 'Enroll failed',
    deleteOk: zh ? '已删除' : 'Deleted',
    deleteFail: zh ? '删除失败' : 'Delete failed',
    confirmDelete: zh ? '确定删除该声纹？' : 'Delete this voiceprint?',
  }
})

const profiles = ref([])
const loading = ref(false)
const displayName = ref('')
const profileId = ref('')
const recordState = ref('idle') // idle | recording
const uploading = ref(false)

let mediaStream = null
let audioCtx = null
let scriptNode = null
let pcmChunks = []

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
    sum += float32[i] * float32[i]
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

function releaseMic() {
  if (scriptNode) {
    try {
      scriptNode.disconnect()
    } catch {
      /* noop */
    }
    scriptNode = null
  }
  if (audioCtx) {
    try {
      audioCtx.close()
    } catch {
      /* noop */
    }
    audioCtx = null
  }
  if (mediaStream) {
    for (const track of mediaStream.getTracks()) track.stop()
    mediaStream = null
  }
  pcmChunks = []
}

async function loadProfiles() {
  loading.value = true
  try {
    const res = await fetch(`${DIARIZATION_API_BASE}/api/voiceprint/profiles`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(String(data?.detail || res.status))
    profiles.value = Array.isArray(data?.profiles) ? data.profiles : []
  } catch (e) {
    showToast({ message: e?.message || 'Load failed', position: 'middle' })
    profiles.value = []
  } finally {
    loading.value = false
  }
}

async function postEnrollWav(wavBlob) {
  if (!displayName.value.trim() && !profileId.value.trim()) {
    showToast({ message: t.value.needName, position: 'middle' })
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', wavBlob, 'enroll.wav')
    formData.append('displayName', displayName.value.trim())
    formData.append('profileId', profileId.value.trim())
    const res = await fetch(`${DIARIZATION_API_BASE}/api/voiceprint/enroll`, {
      method: 'POST',
      body: formData,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(String(data?.detail || res.status))
    showToast({ message: t.value.enrollOk, position: 'middle' })
    await loadProfiles()
  } catch (e) {
    showToast({ message: `${t.value.enrollFail}: ${e?.message || ''}`, position: 'middle' })
  } finally {
    uploading.value = false
  }
}

async function startRecord() {
  if (!displayName.value.trim() && !profileId.value.trim()) {
    showToast({ message: t.value.needName, position: 'middle' })
    return
  }
  releaseMic()
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    const AC = window.AudioContext || window.webkitAudioContext
    audioCtx = new AC()
    const source = audioCtx.createMediaStreamSource(mediaStream)
    const bufferSize = 4096
    scriptNode = audioCtx.createScriptProcessor(bufferSize, 1, 1)
    scriptNode.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0)
      pcmChunks.push(new Float32Array(input))
    }
    source.connect(scriptNode)
    scriptNode.connect(audioCtx.destination)
    recordState.value = 'recording'
  } catch {
    releaseMic()
    showToast({ message: 'Mic permission denied', position: 'middle' })
  }
}

async function stopRecordAndEnroll() {
  if (recordState.value !== 'recording') return
  recordState.value = 'idle'
  const sourceRate = audioCtx?.sampleRate || 48000
  const raw = concatFloat32(pcmChunks)
  releaseMic()
  const minSamples = 2 * sourceRate
  if (raw.length < minSamples) {
    showToast({ message: t.value.tooShort, position: 'middle' })
    return
  }
  const resampled = resampleTo16k(raw, sourceRate)
  const leveled = normalizeChunkRms(resampled, CHUNK_TARGET_RMS, CHUNK_RMS_MAX_GAIN)
  const wavBlob = toWavBlobFromMonoFloat32(leveled, TARGET_SAMPLE_RATE)
  await postEnrollWav(wavBlob)
}

function onFileChange(ev) {
  const file = ev.target?.files?.[0]
  ev.target.value = ''
  if (!file) return
  postEnrollWav(file)
}

async function onDelete(p) {
  try {
    await showConfirmDialog({ title: t.value.confirmDelete, confirmButtonColor: '#ee0a24' })
  } catch {
    return
  }
  try {
    const id = encodeURIComponent(p.profile_id)
    const res = await fetch(`${DIARIZATION_API_BASE}/api/voiceprint/profiles/${id}`, {
      method: 'DELETE',
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(String(data?.detail || res.status))
    showToast({ message: t.value.deleteOk, position: 'middle' })
    await loadProfiles()
  } catch (e) {
    showToast({ message: `${t.value.deleteFail}: ${e?.message || ''}`, position: 'middle' })
  }
}

onBeforeUnmount(() => {
  releaseMic()
})

loadProfiles()
</script>

<template>
  <div class="vp-shell">
    <section class="hero">
      <div class="hero-eyebrow">
        <Icon name="contact" size="14" />
        <span>{{ t.title }}</span>
      </div>
      <p class="hero-desc">{{ t.subtitle }}</p>
    </section>

    <section class="card">
      <div class="card-head">
        <div class="card-head-left">
          <Icon name="edit" size="14" />
          <span>{{ isZh ? '注册 / 追加样本' : 'Enroll / add sample' }}</span>
        </div>
      </div>
      <div class="form">
        <label class="field">
          <span class="field-label">{{ t.nameLabel }}</span>
          <input v-model="displayName" class="field-input" type="text" :placeholder="t.namePlaceholder" />
        </label>
        <label class="field">
          <span class="field-label">{{ t.profileIdLabel }}</span>
          <input v-model="profileId" class="field-input" type="text" spellcheck="false" />
        </label>
        <div class="actions">
          <button
            v-if="recordState === 'idle'"
            type="button"
            class="btn btn-primary"
            :disabled="uploading"
            @click="startRecord"
          >
            {{ t.record }}
          </button>
          <button
            v-else
            type="button"
            class="btn btn-danger"
            :disabled="uploading"
            @click="stopRecordAndEnroll"
          >
            {{ t.stop }}
          </button>
          <label class="btn btn-ghost">
            {{ t.uploadHint }}
            <input type="file" accept="audio/wav,audio/*" class="file-input" @change="onFileChange" />
          </label>
        </div>
        <p v-if="recordState === 'recording'" class="hint pulse">{{ t.recording }}</p>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <div class="card-head-left">
          <Icon name="friends-o" size="14" />
          <span>{{ t.listTitle }}</span>
        </div>
        <button type="button" class="link-btn" @click="loadProfiles">{{ t.refresh }}</button>
      </div>
      <div v-if="loading" class="muted">{{ t.loading }}</div>
      <div v-else-if="!profiles.length" class="empty">{{ t.empty }}</div>
      <ul v-else class="profile-list">
        <li v-for="p in profiles" :key="p.profile_id" class="profile-row">
          <div class="profile-main">
            <span class="profile-name">{{ p.display_name }}</span>
            <span class="profile-meta">{{ p.profile_id }} · {{ p.sample_count }} {{ t.samples }}</span>
          </div>
          <button type="button" class="btn-text danger" @click="onDelete(p)">{{ t.delete }}</button>
        </li>
      </ul>
    </section>

  </div>
</template>

<style scoped>
.vp-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px 32px;
}

.hero {
  margin: 0 -16px;
  padding: 12px 20px 10px;
  background: var(--color-hero-bg);
  border-bottom: 1px solid var(--color-border);
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.hero-desc {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.card {
  background: var(--color-surface);
  border-radius: 16px;
  border: 1px solid var(--color-border);
  box-shadow: 0 12px 32px -24px rgba(28, 25, 23, 0.18);
  overflow: hidden;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(15, 36, 75, 0.06);
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.card-head-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.form {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 11px;
  font-weight: 650;
  color: #64748b;
}

.field-input {
  border: 1px solid rgba(15, 36, 75, 0.1);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  background: #f8fafc;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.btn-primary {
  background: var(--color-accent);
  color: #fff;
  box-shadow: 0 6px 16px -8px rgba(13, 61, 92, 0.4);
}

.btn-danger {
  background: #ef4444;
  color: #fff;
}

.btn-ghost {
  position: relative;
  background: rgba(15, 23, 42, 0.06);
  color: #334155;
  overflow: hidden;
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.hint {
  font-size: 12px;
  color: #ef4444;
  margin: 0;
}

.pulse {
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.55;
  }
}

.muted {
  color: #64748b;
  font-size: 12px;
}

.small {
  padding: 10px 14px;
}

.empty {
  padding: 20px 14px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.profile-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.profile-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-top: 1px solid rgba(15, 36, 75, 0.05);
}

.profile-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.profile-name {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
}

.profile-meta {
  font-size: 11px;
  color: #94a3b8;
  word-break: break-all;
}

.btn-text {
  border: none;
  background: none;
  color: #ef4444;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  flex-shrink: 0;
}

.link-btn {
  border: none;
  background: none;
  color: var(--color-accent);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

@media (max-width: 639px) {
  .vp-shell {
    padding: 0 10px 22px;
    gap: 10px;
  }
  .hero {
    margin: 0 -10px;
    padding: 10px 14px 8px;
  }
  .hero-desc {
    font-size: 12px;
    line-height: 1.45;
    margin-top: 8px;
  }
  .card {
    border-radius: 14px;
  }
  .card-head {
    padding: 10px 12px;
    flex-wrap: wrap;
    row-gap: 8px;
  }
  .form {
    padding: 12px;
  }
  .actions {
    flex-direction: column;
    align-items: stretch;
  }
  .btn {
    width: 100%;
    min-height: 44px;
  }
  .profile-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
  .btn-text {
    padding-left: 0;
  }
}

@media (min-width: 640px) and (max-width: 899px) {
  .vp-shell {
    padding: 0 14px 26px;
  }
}

@media (min-width: 900px) {
  .vp-shell {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-areas:
      "hero hero"
      "enroll list";
    gap: 14px 18px;
    padding-top: 16px;
  }
  .hero {
    grid-area: hero;
    margin: 0;
    border-radius: 20px;
    padding: 14px 18px 12px;
  }
  .vp-shell > .card:first-of-type {
    grid-area: enroll;
  }
  .vp-shell > .card:nth-of-type(2) {
    grid-area: list;
  }
}

</style>
