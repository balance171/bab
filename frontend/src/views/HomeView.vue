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

const { entries: recentEntries, push: pushRecent, clear: clearRecent } = useRecentSearch()

async function doSearch(params: SearchParams) {
  loading.value = true
  error.value = null
  results.value = null  // 이전 결과 초기화 (skeleton + 이전 pagination 동시 표시 방지)
  currentParams.value = params
  try {
    results.value = await fetchMeals(params)
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
  // Scroll to top of right panel on mobile
  window.scrollTo({ top: 0, behavior: 'smooth' })
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
  <div class="app-layout">
    <!-- Main content -->
    <main class="main">
      <!-- Search bar -->
      <SearchForm ref="searchFormRef" @search="handleSearch" />

      <!-- Recent searches (horizontal chips) + result count -->
      <div class="sub-bar">
        <RecentSearch
          :entries="recentEntries"
          @select="handleRecentSelect"
          @clear="clearRecent"
        />
        <div v-if="results" class="result-badge" aria-live="polite">
          {{ results.total.toLocaleString() }}건
        </div>
      </div>

      <!-- Table full width -->
      <div class="table-section">
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
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
}

/* ─── Main ─── */
.main {
  flex: 1;
  min-width: 0;
  padding: var(--sp-5) var(--sp-6) var(--sp-10);
  background: radial-gradient(
      ellipse at 90% 0%,
      rgba(180, 165, 255, 0.22) 0%,
      rgba(200, 220, 255, 0.12) 40%,
      transparent 65%
    ),
    var(--bg);
  overflow-y: auto;
}

/* ─── Sub bar (recent chips + result badge) ─── */
.sub-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin: var(--sp-3) 0 var(--sp-4);
  min-height: 28px;
}

.result-badge {
  flex-shrink: 0;
  background: var(--primary-light);
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 4px var(--sp-3);
  border-radius: var(--r-full);
  letter-spacing: -0.01em;
  white-space: nowrap;
}

/* ─── Table section (full width) ─── */
.table-section {
  display: flex;
  flex-direction: column;
}

@media (max-width: 640px) {
  .main {
    padding: var(--sp-4) var(--sp-3) var(--sp-8);
  }
}
</style>
