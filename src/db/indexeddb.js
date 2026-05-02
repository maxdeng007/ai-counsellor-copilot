const DB_NAME = 'ai-record'
const DB_VERSION = 1

const STORES = {
  meetings: 'meetings',
  clients: 'clients',
}

let openPromise = null

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed'))
  })
}

function withStore(storeName, mode, fn) {
  return getDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, mode)
        const store = tx.objectStore(storeName)
        let result
        try {
          result = fn(store, tx)
        } catch (error) {
          reject(error)
          return
        }
        tx.oncomplete = () => resolve(result)
        tx.onerror = () => reject(tx.error || new Error('IndexedDB transaction failed'))
        tx.onabort = () => reject(tx.error || new Error('IndexedDB transaction aborted'))
      }),
  )
}

export function getDb() {
  if (openPromise) return openPromise
  openPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORES.meetings)) {
        const meetings = db.createObjectStore(STORES.meetings, { keyPath: 'id' })
        meetings.createIndex('by_created_at', 'createdAt', { unique: false })
        meetings.createIndex('by_updated_at', 'updatedAt', { unique: false })
        meetings.createIndex('by_status', 'status', { unique: false })
      }
      if (!db.objectStoreNames.contains(STORES.clients)) {
        db.createObjectStore(STORES.clients, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('Failed to open IndexedDB'))
  })
  return openPromise
}

export async function putMeeting(record) {
  await withStore(STORES.meetings, 'readwrite', (store) => store.put(record))
  return record
}

export async function getMeeting(id) {
  return withStore(STORES.meetings, 'readonly', (store) => requestToPromise(store.get(id)))
}

export async function getAllMeetings() {
  return withStore(STORES.meetings, 'readonly', (store) => requestToPromise(store.getAll()))
}

export async function deleteMeeting(id) {
  await withStore(STORES.meetings, 'readwrite', (store) => store.delete(id))
}

export async function putClient(record) {
  await withStore(STORES.clients, 'readwrite', (store) => store.put(record))
  return record
}

export async function getAllLocalClients() {
  return withStore(STORES.clients, 'readonly', (store) => requestToPromise(store.getAll()))
}

export async function clearDb() {
  const db = await getDb()
  db.close()
  openPromise = null
  await requestToPromise(indexedDB.deleteDatabase(DB_NAME))
}

