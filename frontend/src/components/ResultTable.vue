<script setup lang="ts">
import { ref } from 'vue'
import type { MealRow } from '@/types/meal'

defineProps<{
  meals: MealRow[] | undefined
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  sortChange: [sort: string | undefined, order: 'asc' | 'desc' | 'default']
}>()

type SortOrder = 'asc' | 'desc' | 'default'

const sortCol = ref<string | undefined>(undefined)
const sortOrder = ref<SortOrder>('default')

const SORTABLE = ['meal_year', 'meal_date', 'school_name', 'meal_type', 'soup', 'main_dish', 'side1', 'dessert', 'search_key']

const COLUMNS = [
  { key: 'meal_year', label: '연도' },
  { key: 'meal_date', label: '날짜' },
  { key: 'school_name', label: '학교' },
  { key: 'meal_type', label: '구분' },
  { key: 'soup', label: '국' },
  { key: 'main_dish', label: '주요리' },
  { key: 'side1', label: '부요리' },
  { key: 'dessert', label: '디저트' },
  { key: 'search_key', label: '검색키' },
]

function toggleSort(col: string) {
  if (!SORTABLE.includes(col)) return

  if (sortCol.value !== col) {
    sortCol.value = col
    sortOrder.value = 'asc'
  } else if (sortOrder.value === 'default' || sortOrder.value === undefined) {
    sortOrder.value = 'asc'
  } else if (sortOrder.value === 'asc') {
    sortOrder.value = 'desc'
  } else {
    sortCol.value = undefined
    sortOrder.value = 'default'
  }

  emit('sortChange', sortCol.value, sortOrder.value)
}

function sortState(col: string): 'asc' | 'desc' | 'neutral' {
  if (sortCol.value !== col) return 'neutral'
  if (sortOrder.value === 'asc') return 'asc'
  if (sortOrder.value === 'desc') return 'desc'
  return 'neutral'
}

const KO_DAYS = ['일', '월', '화', '수', '목', '금', '토']

function formatDate(d: string): string {
  if (!d) return '—'
  const parts = d.split('-')
  const year = Number(parts[0] ?? 2024)
  const month = Number(parts[1] ?? 1)
  const day = Number(parts[2] ?? 1)
  const date = new Date(year, month - 1, day)
  const mm = String(month).padStart(2, '0')
  const dd = String(day).padStart(2, '0')
  return `${mm}/${dd}(${KO_DAYS[date.getDay()] ?? '?'})`
}

function mealTypeClass(type: string): string {
  if (type === '조식') return 'badge-breakfast'
  if (type === '석식') return 'badge-dinner'
  return 'badge-lunch'
}

function cellVal(v: string | null): string {
  return v ?? '—'
}
</script>

<template>
  <div class="table-card">
    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="skeleton-wrap">
        <div class="skeleton-header"></div>
        <div
          v-for="i in 8"
          :key="i"
          class="skeleton-row"
          :style="{ animationDelay: `${i * 0.04}s` }"
        ></div>
      </div>
    </template>

    <!-- Error -->
    <div v-else-if="error" class="state centered">
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="state-icon error-color"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" x2="12" y1="8" y2="12" />
        <line x1="12" x2="12.01" y1="16" y2="16" />
      </svg>
      <p class="state-title">오류가 발생했어요</p>
      <p class="state-desc">{{ error }}</p>
    </div>

    <!-- Initial (no search yet) -->
    <div v-else-if="meals === undefined" class="state centered">
      <span class="state-emoji" aria-hidden="true">🍱</span>
      <p class="state-title">급식을 검색해보세요</p>
      <p class="state-desc">학교명, 요리명, 월 중 하나를 입력하고 검색하세요</p>
    </div>

    <!-- No results -->
    <div v-else-if="meals.length === 0" class="state centered">
      <span class="state-emoji" aria-hidden="true">🔍</span>
      <p class="state-title">검색 결과가 없어요</p>
      <p class="state-desc">다른 조건으로 검색해보세요</p>
    </div>

    <!-- Data table -->
    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th
              v-for="col in COLUMNS"
              :key="col.key"
              class="th"
              :class="[`th-${col.key}`, { sortable: SORTABLE.includes(col.key) }]"
              @click="toggleSort(col.key)"
            >
              <span class="th-inner">
                {{ col.label }}
                <span v-if="SORTABLE.includes(col.key)" class="sort-icon" aria-hidden="true">
                  <!-- Neutral -->
                  <svg
                    v-if="sortState(col.key) === 'neutral'"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path d="m7 15 5 5 5-5" />
                    <path d="m7 9 5-5 5 5" />
                  </svg>
                  <!-- Asc -->
                  <svg
                    v-else-if="sortState(col.key) === 'asc'"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path d="m18 15-6-6-6 6" />
                  </svg>
                  <!-- Desc -->
                  <svg
                    v-else
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in meals" :key="row.id" class="data-row">
            <td class="td td-year">{{ row.meal_date.split('-')[0] }}</td>
            <td class="td td-date">{{ formatDate(row.meal_date) }}</td>
            <td class="td td-school">{{ row.school_name }}</td>
            <td class="td td-type">
              <span class="badge" :class="mealTypeClass(row.meal_type)">{{ row.meal_type }}</span>
            </td>
            <td class="td">{{ cellVal(row.soup) }}</td>
            <td class="td">{{ cellVal(row.main_dish) }}</td>
            <td class="td">{{ cellVal(row.side1) }}</td>
            <td class="td">{{ cellVal(row.dessert) }}</td>
            <td class="td td-search-key">{{ row.search_key }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.table-card {
  background: var(--surface);
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  min-height: 200px;
}

/* State areas */
.state {
  padding: var(--sp-8);
}

.state.centered {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  text-align: center;
  gap: var(--sp-3);
}

.state-emoji {
  font-size: 3rem;
  line-height: 1;
}

.state-icon {
  opacity: 0.45;
}

.error-color {
  color: var(--error);
  opacity: 0.8;
}

.state-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text);
  margin: 0;
}

.state-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

/* Skeleton */
.skeleton-wrap {
  padding: var(--sp-4) var(--sp-6);
}

.skeleton-header {
  height: 40px;
  border-radius: var(--r-md);
  margin-bottom: var(--sp-3);
  background: linear-gradient(90deg, var(--surface-raised) 25%, #eaeaf5 50%, var(--surface-raised) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease infinite;
}

.skeleton-row {
  height: 48px;
  border-radius: var(--r-sm);
  margin-bottom: var(--sp-2);
  opacity: 0;
  background: linear-gradient(90deg, var(--surface-raised) 25%, #eaeaf5 50%, var(--surface-raised) 75%);
  background-size: 200% 100%;
  animation:
    shimmer 1.4s ease infinite,
    fadeIn 0.15s ease forwards;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@keyframes fadeIn {
  to {
    opacity: 1;
  }
}

/* Table */
.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
  font-size: var(--text-sm);
  table-layout: fixed;
}

.th {
  padding: var(--sp-3) var(--sp-4);
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
  border-bottom: 1.5px solid var(--border);
  background: var(--surface-raised);
  user-select: none;
}

.th.sortable {
  cursor: pointer;
  transition: color var(--transition);
}

.th.sortable:hover {
  color: var(--primary);
}

.th-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sort-icon {
  display: inline-flex;
  align-items: center;
  opacity: 0.5;
  transition: opacity var(--transition);
}

.th.sortable:hover .sort-icon {
  opacity: 1;
  color: var(--primary);
}

/* 컬럼 너비 비율 (table-layout: fixed) */
.th-meal_year   { width: 4%; }
.th-meal_date   { width: 6%; }
.th-school_name { width: 13%; }
.th-meal_type   { width: 4%; }
.th-soup        { width: 9%; }
.th-main_dish   { width: 9%; }
.th-side1       { width: 9%; }
.th-dessert     { width: 9%; }
.th-search_key  { width: 37%; }

/* Rows */
.td {
  padding: 11px var(--sp-4);
  color: var(--text);
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  white-space: normal;
  word-break: keep-all;
  line-height: 1.5;
}

.td-year {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.td-date {
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.01em;
}

.td-school {
  font-weight: 500;
}

.td-search-key {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: normal;
  word-break: break-all;
  line-height: 1.5;
}

.data-row {
  transition: background var(--transition);
}

.data-row:hover {
  background: var(--primary-muted);
}

.data-row:last-child .td {
  border-bottom: none;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: var(--r-full);
  font-size: 11px;
  font-weight: 600;
}

.badge-breakfast {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
}

.badge-lunch {
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
}

.badge-dinner {
  background: rgba(123, 114, 247, 0.1);
  color: #5b53d0;
}
</style>
