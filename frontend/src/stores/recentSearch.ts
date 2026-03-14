import { ref } from 'vue'
import type { SearchParams } from '@/types/meal'

export interface RecentSearchEntry {
  school: string
  school_code?: string
  dish: string
  month: number | undefined
  years: number[]
  timestamp: number
}

const STORAGE_KEY = 'neis_recent_searches'
const MAX_ENTRIES = 10

function load(): RecentSearchEntry[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as RecentSearchEntry[]
  } catch {
    return []
  }
}

// Module-level singleton so all components share the same state
const entries = ref<RecentSearchEntry[]>(load())

export function useRecentSearch() {
  function push(params: SearchParams) {
    const entry: RecentSearchEntry = {
      school: params.school ?? '',
      school_code: params.school_code,
      dish: params.dish ?? '',
      month: params.month,
      years: params.years ? [...params.years] : [],
      timestamp: Date.now(),
    }

    // Remove duplicate
    entries.value = entries.value.filter(
      (e) =>
        !(
          e.school === entry.school &&
          e.dish === entry.dish &&
          e.month === entry.month &&
          JSON.stringify(e.years ?? []) === JSON.stringify(entry.years)
        ),
    )

    entries.value.unshift(entry)

    if (entries.value.length > MAX_ENTRIES) {
      entries.value = entries.value.slice(0, MAX_ENTRIES)
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.value))
  }

  function clear() {
    entries.value = []
    localStorage.removeItem(STORAGE_KEY)
  }

  return { entries, push, clear }
}
