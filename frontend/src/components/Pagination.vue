<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  total: number
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  pageChange: [page: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageNumbers = computed<(number | '...')[]>(() => {
  const cur = props.page
  const last = totalPages.value
  const delta = 2
  const range: (number | '...')[] = []

  const start = Math.max(1, cur - delta)
  const end = Math.min(last, cur + delta)

  if (start > 1) {
    range.push(1)
    if (start > 2) range.push('...')
  }

  for (let i = start; i <= end; i++) range.push(i)

  if (end < last) {
    if (end < last - 1) range.push('...')
    range.push(last)
  }

  return range
})
</script>

<template>
  <div class="pagination">
    <span class="total-label">
      총 <strong>{{ total.toLocaleString() }}</strong
      >건 &middot; {{ page }} / {{ totalPages }} 페이지
    </span>

    <div class="page-buttons">
      <button
        class="page-btn nav-btn"
        :disabled="page === 1"
        aria-label="이전 페이지"
        @click="emit('pageChange', page - 1)"
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="m15 18-6-6 6-6" />
        </svg>
      </button>

      <template v-for="(p, i) in pageNumbers" :key="i">
        <span v-if="p === '...'" class="ellipsis">…</span>
        <button
          v-else
          class="page-btn"
          :class="{ active: p === page }"
          :aria-label="`${p} 페이지`"
          :aria-current="p === page ? 'page' : undefined"
          @click="emit('pageChange', p as number)"
        >
          {{ p }}
        </button>
      </template>

      <button
        class="page-btn nav-btn"
        :disabled="page === totalPages"
        aria-label="다음 페이지"
        @click="emit('pageChange', page + 1)"
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="m9 18 6-6-6-6" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-4) var(--sp-6);
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-wrap: wrap;
  gap: var(--sp-3);
  border-radius: 0 0 var(--r-xl) var(--r-xl);
}

.total-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.total-label strong {
  color: var(--text);
  font-weight: 600;
}

.page-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 var(--sp-2);
  border: 1.5px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-family: var(--font);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
}

.page-btn:hover:not(:disabled):not(.active) {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  font-weight: 600;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.ellipsis {
  padding: 0 var(--sp-1);
  color: var(--text-subtle);
  font-size: var(--text-sm);
  user-select: none;
}
</style>
