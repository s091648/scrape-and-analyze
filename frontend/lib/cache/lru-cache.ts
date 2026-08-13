/** Minimal LRU cache. Relies on Map's spec-guaranteed insertion-order iteration instead of
 * hand-rolling a doubly linked list: delete+re-set moves a key to the "most recent" end,
 * and `.keys().next().value` reads the "least recent" end — both O(1). */
export class LRUCache<K, V> {
  private map = new Map<K, V>()

  constructor(private capacity: number) {}

  get(key: K): V | undefined {
    if (!this.map.has(key)) return undefined
    const value = this.map.get(key)!
    this.map.delete(key)
    this.map.set(key, value)
    return value
  }

  set(key: K, value: V): void {
    if (this.map.has(key)) {
      this.map.delete(key)
    } else if (this.map.size >= this.capacity) {
      const oldestKey = this.map.keys().next().value
      if (oldestKey !== undefined) this.map.delete(oldestKey)
    }
    this.map.set(key, value)
  }

  clear(): void {
    this.map.clear()
  }
}
