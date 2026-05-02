import { deleteMeeting, getAllMeetings, getMeeting, putMeeting } from '../db/indexeddb.js'

const SCHEMA_VERSION = 1

function deepClone(value) {
  return JSON.parse(JSON.stringify(value))
}

function sortDescByUpdatedAt(list) {
  return [...list].sort((a, b) => {
    const av = Number(a?.updatedAt || 0)
    const bv = Number(b?.updatedAt || 0)
    return bv - av
  })
}

function withDefaults(record) {
  const now = Date.now()
  return {
    schemaVersion: SCHEMA_VERSION,
    id: record?.id || (crypto?.randomUUID ? crypto.randomUUID() : `meeting_${now}`),
    createdAt: Number(record?.createdAt || now),
    updatedAt: Number(record?.updatedAt || now),
    status: record?.status || 'reviewing',
    locale: record?.locale || 'zh',
    durationMs: Number(record?.durationMs || 0),
    linkedClient: record?.linkedClient || null,
    transcript: record?.transcript || { speakers: [], segments: [] },
    aiOutput: record?.aiOutput || null,
    ...record,
  }
}

export const meetingRepo = {
  async save(input) {
    const existing = input?.id ? await getMeeting(input.id) : null
    const merged = withDefaults({
      ...(existing || {}),
      ...(input || {}),
      updatedAt: Date.now(),
      createdAt: existing?.createdAt || input?.createdAt || Date.now(),
    })
    await putMeeting(merged)
    return deepClone(merged)
  },

  async get(id) {
    if (!id) return null
    const item = await getMeeting(id)
    return item ? deepClone(item) : null
  },

  async list(options = {}) {
    const { limit = 50, status = '', since = 0 } = options
    const all = await getAllMeetings()
    const filtered = all.filter((item) => {
      if (!item) return false
      if (status && item.status !== status) return false
      if (since && Number(item.updatedAt || 0) < Number(since)) return false
      return true
    })
    return sortDescByUpdatedAt(filtered)
      .slice(0, Math.max(1, Number(limit || 50)))
      .map(deepClone)
  },

  async remove(id) {
    if (!id) return false
    await deleteMeeting(id)
    return true
  },
}

export { SCHEMA_VERSION }

