<script setup lang="ts">
import { ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import ResultTable from '@/components/ResultTable.vue'
import Pagination from '@/components/Pagination.vue'
import RecentSearch from '@/components/RecentSearch.vue'
import { fetchMeals } from '@/api/meals'
import { useRecentSearch } from '@/stores/recentSearch'
import type { SearchParams, MealsResponse } from '@/types/meal'
import type { RecentSearchEntry } from '@/stores/recentSearch'

const searchFormRef = ref<InstanceType<typeof SearchForm> | null>(null)
const results = ref<MealsResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const currentParams = ref<SearchParams>({})
const pageSize = ref(30)

const PAGE_SIZE_OPTIONS = [30, 50, 100, 200]

const { entries: recentEntries, push: pushRecent, clear: clearRecent } = useRecentSearch()

async function doSearch(params: SearchParams) {
  loading.value = true
  error.value = null
  results.value = null
  currentParams.value = params
  try {
    results.value = await fetchMeals({ ...params, page_size: pageSize.value })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '알 수 없는 오류가 발생했어요'
    results.value = null
  } finally {
    loading.value = false
  }
}

function handleSearch(params: SearchParams) {
  pushRecent(params)
  doSearch({ ...params, page: 1 })
}

function handleSort(sort: string | undefined, order: 'asc' | 'desc' | 'default') {
  doSearch({ ...currentParams.value, sort, order, page: 1 })
}

function handlePageChange(page: number) {
  doSearch({ ...currentParams.value, page })
}

function handlePageSizeChange(e: Event) {
  pageSize.value = Number((e.target as HTMLSelectElement).value)
  if (results.value) {
    doSearch({ ...currentParams.value, page: 1 })
  }
}

function handleRecentSelect(entry: RecentSearchEntry) {
  searchFormRef.value?.fill({
    school: entry.school,
    school_code: entry.school_code,
    dish: entry.dish,
    month: entry.month,
    years: entry.years,
  })
  handleSearch({
    school: entry.school_code ? undefined : (entry.school || undefined),
    school_code: entry.school_code,
    dish: entry.dish || undefined,
    month: entry.month,
    years: entry.years?.length ? entry.years : undefined,
  })
}
</script>

<template>
  <div class="page">
    <!-- 상단 고정: 검색 + 최근검색 + 건수 -->
    <header class="top-fixed">
      <SearchForm ref="searchFormRef" @search="handleSearch" />
      <div class="sub-bar">
        <RecentSearch
          :entries="recentEntries"
          @select="handleRecentSelect"
          @clear="clearRecent"
        />
        <div class="sub-right">
          <select class="size-select" :value="pageSize" @change="handlePageSizeChange">
            <option v-for="s in PAGE_SIZE_OPTIONS" :key="s" :value="s">{{ s }}개</option>
          </select>
          <div v-if="results" class="result-badge">{{ results.total.toLocaleString() }}건</div>
        </div>
      </div>
    </header>

    <!-- 하단: 테이블 (남은 공간 전부, 내부 스크롤) -->
    <main class="table-area">
      <ResultTable
        :meals="results?.data"
        :loading="loading"
        :error="error"
        @sort-change="handleSort"
      />
      <Pagination
        v-if="results && results.total > 0"
        :total="results.total"
        :page="results.page"
        :page-size="results.page_size"
        @page-change="handlePageChange"
      />
    </main>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: radial-gradient(
      ellipse at 90% 0%,
      rgba(180, 165, 255, 0.22) 0%,
      rgba(200, 220, 255, 0.12) 40%,
      transparent 65%
    ),
    var(--bg);
}

/* ─── 상단 고정 ─── */
.top-fixed {
  flex-shrink: 0;
  padding: var(--sp-2) var(--sp-3) var(--sp-1);
}

.sub-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

.sub-right {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-shrink: 0;
}

.size-select {
  appearance: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 3px var(--sp-5) 3px var(--sp-2);
  font-size: var(--text-xs);
  font-family: var(--font);
  color: var(--text);
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%239ba3b5' stroke-width='2.5'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 5px center;
}

.result-badge {
  background: var(--primary-light);
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 3px var(--sp-2);
  border-radius: var(--r-full);
  white-space: nowrap;
}

/* ─── 테이블 영역: 남은 높이 전부, 가로+세로 스크롤 ─── */
.table-area {
  flex: 1;
  min-height: 0;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 var(--sp-3) var(--sp-3);
}

/* ─── 모바일 ─── */
@media (max-width: 640px) {
  .top-fixed {
    padding: var(--sp-1) var(--sp-2) var(--sp-1);
  }

  .sub-bar {
    margin-top: var(--sp-1);
    gap: var(--sp-1);
  }

  .table-area {
    padding: 0 var(--sp-2);
  }
}
</style>
