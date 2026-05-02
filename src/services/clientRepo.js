import { MOCK_CLIENTS, searchClients } from '../data/mockDialog.js'
import { getAllLocalClients, putClient } from '../db/indexeddb.js'

function cloneClient(client) {
  return JSON.parse(JSON.stringify(client))
}

function byNameLocale(locale) {
  return locale === 'zh' ? 'nameZh' : 'nameEn'
}

function mergeClientsWithLocals(localClients) {
  const merged = [...MOCK_CLIENTS.map(cloneClient)]
  const seen = new Set(merged.map((c) => c.id))
  for (const c of localClients) {
    if (!c || !c.id || seen.has(c.id)) continue
    merged.push(cloneClient(c))
    seen.add(c.id)
  }
  return merged
}

export const clientRepo = {
  async list() {
    const localClients = await getAllLocalClients()
    return mergeClientsWithLocals(localClients)
  },

  async get(id) {
    if (!id) return null
    const all = await this.list()
    return all.find((c) => c.id === id) || null
  },

  async search(query, locale = 'zh') {
    const q = String(query || '').trim()
    const localClients = await getAllLocalClients()
    const merged = mergeClientsWithLocals(localClients)
    if (!q) return merged

    // Keep current fuzzy matcher behavior for built-in clients, then include local hits.
    const fuzzyRanked = searchClients(q, locale)
    const baseIds = new Set(fuzzyRanked.map((c) => c.id))
    const key = byNameLocale(locale)
    const qLower = q.toLowerCase()
    const localHits = merged.filter((c) => {
      if (baseIds.has(c.id)) return false
      const nm = String(c?.[key] || '').toLowerCase()
      return nm.includes(qLower)
    })
    return [...fuzzyRanked, ...localHits]
  },

  async createLocal(payload, locale = 'zh') {
    const now = Date.now()
    const suffix = Math.random().toString(36).slice(2, 8)
    const name = String(payload?.name || '').trim()
    const industry = String(payload?.industry || '').trim()
    const id = `c-local-${now}-${suffix}`
    const record = {
      id,
      nameZh: locale === 'zh' ? name : '',
      nameEn: locale === 'en' ? name : '',
      tagsZh: ['新建客户'],
      tagsEn: ['New Client'],
      lastSeenZh: '尚未见面',
      lastSeenEn: 'Not yet met',
      industryZh: locale === 'zh' ? industry : '未分类',
      industryEn: locale === 'en' ? industry : 'Uncategorized',
      createdAt: now,
      source: 'local',
    }
    await putClient(record)
    return cloneClient(record)
  },
}

