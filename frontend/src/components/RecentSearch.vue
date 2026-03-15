<script setup lang="ts">
import type { RecentSearchEntry } from '@/stores/recentSearch'

defineProps<{
  entries: RecentSearchEntry[]
}>()

const emit = defineEmits<{
  select: [entry: RecentSearchEntry]
  clear: []
}>()

function formatLabel(entry: RecentSearchEntry): string {
  const parts: string[] = []
  if (entry.school) parts.push(entry.school)
  if (entry.dish) parts.push(entry.dish)
  if (entry.month) parts.push(`${entry.month}월`)
  if (entry.years?.length) parts.push(entry.years.join('/') + '년')
  return parts.join(' · ')
}
</script>

<template>
  <div v-if="entries.length" class="recent-bar">
    <button
      v-for="entry in entries"
      :key="entry.timestamp"
      class="recent-chip"
      @click="emit('select', entry)"
    >
      {{ formatLabel(entry) }}
    </button>
    <button class="btn-clear" @click="emit('clear')">초기화</button>
  </div>
</template>

<style scoped>
.recent-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
}

.recent-chip {
  display: inline-flex;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-full);
  padding: 5px var(--sp-3);
  font-size: var(--text-xs);
  font-family: var(--font);
  font-weight: 500;
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  transition:
    background var(--transition),
    border-color var(--transition),
    color var(--transition);
}

.recent-chip:hover {
  background: var(--primary-muted);
  border-color: var(--primary);
  color: var(--primary);
}

.btn-clear {
  font-size: var(--text-xs);
  color: var(--text-subtle);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px var(--sp-2);
  font-family: var(--font);
  transition: color var(--transition);
}

.btn-clear:hover {
  color: var(--error);
}

@media (max-width: 640px) {
  .recent-bar {
    gap: 3px;
  }

  .recent-chip {
    padding: 3px 8px;
    font-size: 10px;
  }

  .btn-clear {
    font-size: 10px;
    padding: 2px 4px;
  }
}
</style>
