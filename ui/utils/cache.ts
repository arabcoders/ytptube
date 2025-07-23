type CacheEngine = 'session' | 'local'

interface CachedItem<T = any> {
  value: T
  ttl: number | null
  time: number
}

class Cache {
  private storage: Storage
  private supportedEngines: CacheEngine[] = ['session', 'local']

  constructor(engine: CacheEngine = 'session') {
    if (!this.supportedEngines.includes(engine)) {
      throw new Error(`Engine '${engine}' not supported.`)
    }

    this.storage = 'session' === engine ? window.sessionStorage : window.localStorage
  }

  set<T = any>(key: string, value: T, ttl: number | null = null): void {
    const item: CachedItem<T> = { value, ttl, time: Date.now() }
    this.storage.setItem(key, JSON.stringify(item))
  }

  get<T = any>(key: string): T | null {
    const item = this.storage.getItem(key)
    if (null === item) {
      return null
    }

    try {
      const parsed: CachedItem<T> = JSON.parse(item)
      if (null !== parsed.ttl && Date.now() - parsed.time > parsed.ttl) {
        this.remove(key)
        return null
      }
      return parsed.value
    } catch {
      return item as unknown as T
    }
  }

  remove(key: string): void {
    this.storage.removeItem(key)
  }

  clear(filter: ((key: string) => boolean) | null = null): void {
    if (null !== filter) {
      Object.keys(this.storage).filter(filter).forEach(k => this.storage.removeItem(k))
      return
    }
    this.storage.clear()
  }

  has(key: string): boolean {
    return null !== this.get(key)
  }
}

const useLocalCache = (): Cache => new Cache('local')
const useSessionCache = (): Cache => new Cache('session')

export { useSessionCache, useLocalCache, Cache }
