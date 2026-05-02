const SUMMARY_API_BASE = import.meta.env?.VITE_SUMMARY_API_BASE || import.meta.env?.VITE_DIARIZATION_API_BASE || 'http://localhost:8090'
const DEFAULT_TIMEOUT_MS = Number(import.meta.env?.VITE_SUMMARY_TIMEOUT_MS || 30000)

function withTimeout(ms) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new Error(`request_timeout_${ms}ms`)), ms)
  return { controller, cancel: () => clearTimeout(timer) }
}

async function postJson(path, payload, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const { controller, cancel } = withTimeout(timeoutMs)
  try {
    const response = await fetch(`${SUMMARY_API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
      signal: controller.signal,
    })
    if (!response.ok) {
      let details = ''
      try {
        const body = await response.json()
        details = body?.detail ? `: ${body.detail}` : ''
      } catch {
        // keep default message
      }
      throw new Error(`HTTP ${response.status}${details}`)
    }
    return response.json()
  } finally {
    cancel()
  }
}

async function retryOnce(fn) {
  try {
    return await fn()
  } catch (error) {
    const msg = String(error?.message || '')
    const retryable =
      msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('request_timeout_')
    if (!retryable) throw error
    return fn()
  }
}

export async function extractEntities(transcriptPayload) {
  return retryOnce(() => postJson('/api/extract-entities', transcriptPayload))
}

export async function summarizeMeeting(meetingPayload) {
  return retryOnce(() => postJson('/api/summarize-meeting', meetingPayload))
}

