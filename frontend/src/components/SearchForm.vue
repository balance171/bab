<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { SchoolItem, SearchParams } from '@/types/meal'
import { fetchSchools } from '@/api/meals'

const emit = defineEmits<{
  search: [params: SearchParams]
}>()

const school = ref('')
const schoolCode = ref<string | undefined>(undefined)
const dish = ref('')
const months = ref<number[]>([])
const years = ref<number[]>([])
const schoolTypes = ref<string[]>([])

const SCHOOL_TYPE_OPTIONS = ['초등학교', '중학교', '고등학교']

function toggleSchoolType(t: string) {
  const idx = schoolTypes.value.indexOf(t)
  if (idx >= 0) {
    schoolTypes.value = schoolTypes.value.filter((v) => v !== t)
  } else {
    schoolTypes.value = [...schoolTypes.value, t]
  }
}

// ── 학교 자동완성 ─────────────────────────────────────────────
const suggestions = ref<SchoolItem[]>([])
const showSuggestions = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | undefined

watch(school, (val) => {
  // 코드가 이미 세팅된 경우(선택 직후) 무시
  if (schoolCode.value) return
  clearTimeout(debounceTimer)
  if (!val.trim()) {
    suggestions.value = []
    showSuggestions.value = false
    return
  }
  debounceTimer = setTimeout(async () => {
    suggestions.value = await fetchSchools(val.trim())
    showSuggestions.value = suggestions.value.length > 0
  }, 300)
})

function selectSchool(item: SchoolItem) {
  school.value = item.school_name
  schoolCode.value = item.school_code
  suggestions.value = []
  showSuggestions.value = false
  autoSelectSchoolType(item.school_name)
}

function onSchoolInput() {
  // 직접 타이핑하면 school_code 초기화
  schoolCode.value = undefined
}

function closeSuggestions() {
  setTimeout(() => {
    showSuggestions.value = false
  }, 150)
}

// ── 즐겨찾기 학교 ─────────────────────────────────────────────
const PRESET_SCHOOLS: SchoolItem[] = [
  { school_name: '수원정보과학고등학교', school_code: '7530899', region: '경기' },
  { school_name: '수원하이텍고등학교', school_code: '7530900', region: '경기' },
  { school_name: '광교고등학교', school_code: '7531040', region: '경기' },
  { school_name: '수지고등학교', school_code: '7530093', region: '경기' },
  { school_name: '서울대학교사범대학부설고등학교', school_code: '7011109', region: '서울' },
]

function detectSchoolType(name: string) {
  if (name.includes('초등학교')) return '초등학교'
  if (name.includes('중학교')) return '중학교'
  if (name.includes('고등학교')) return '고등학교'
  return null
}

function autoSelectSchoolType(name: string) {
  const type = detectSchoolType(name)
  if (type && !schoolTypes.value.includes(type)) {
    schoolTypes.value = [type]
  }
}

function onPresetChange(e: Event) {
  const code = (e.target as HTMLSelectElement).value
  if (!code) {
    school.value = ''
    schoolCode.value = undefined
    return
  }
  const found = PRESET_SCHOOLS.find((s) => s.school_code === code)
  if (found) {
    school.value = found.school_name
    schoolCode.value = found.school_code
    autoSelectSchoolType(found.school_name)
  }
}

// ── 연도 ──────────────────────────────────────────────────────
const YEAR_OPTIONS = [2023, 2024, 2025, 2026]

const isDisabled = computed(() => !school.value.trim() && !dish.value.trim() && !months.value.length)

const MONTH_ROW1 = [3, 4, 5, 6, 7, 8]
const MONTH_ROW2 = [9, 10, 11, 12, 1, 2]

function toggleMonth(m: number) {
  const idx = months.value.indexOf(m)
  if (idx >= 0) {
    months.value = months.value.filter((v) => v !== m)
  } else {
    months.value = [...months.value, m]
  }
}

function toggleYear(y: number) {
  const idx = years.value.indexOf(y)
  if (idx >= 0) {
    years.value = years.value.filter((v) => v !== y)
  } else {
    years.value = [...years.value, y].sort()
  }
}

function resetForm() {
  school.value = ''
  schoolCode.value = undefined
  dish.value = ''
  months.value = []
  years.value = []
  schoolTypes.value = []
  suggestions.value = []
  showSuggestions.value = false
}

async function handleSubmit() {
  if (isDisabled.value) return
  const schoolText = school.value.trim()
  let code = schoolText ? schoolCode.value : undefined

  // school_code가 없고 학교명 텍스트가 있으면 → API에서 자동 매칭
  if (schoolText && !code) {
    const matched = await fetchSchools(schoolText)
    if (matched.length > 0) {
      // 첫 번째 매칭 학교 자동 선택
      const best = matched[0]!
      school.value = best.school_name
      schoolCode.value = best.school_code
      code = best.school_code
    }
  }

  emit('search', {
    school: code ? school.value.trim() : (schoolText || undefined),
    school_code: code,
    dish: dish.value.trim() || undefined,
    month: months.value.length === 1 ? months.value[0] : undefined,
    months: months.value.length > 1 ? [...months.value] : undefined,
    years: years.value.length ? [...years.value] : undefined,
    school_types: schoolTypes.value.length ? [...schoolTypes.value] : undefined,
    page: 1,
  })
}

function fill(params: { school: string; dish: string; month?: number; months?: number[]; years?: number[]; school_code?: string; school_types?: string[] }) {
  school.value = params.school
  schoolCode.value = params.school_code
  dish.value = params.dish
  months.value = params.months ? [...params.months] : (params.month ? [params.month] : [])
  years.value = params.years ? [...params.years] : []
  schoolTypes.value = params.school_types ? [...params.school_types] : []
}

defineExpose({ fill })
</script>

<template>
  <form class="form-bar" @submit.prevent="handleSubmit">
    <!-- 한 줄로 모든 조건 나열 -->
    <div class="row row-chips">
      <div class="cell cell-school" style="position:relative">
        <select class="inp inp-sel" :value="schoolCode ?? ''" @change="onPresetChange">
          <option value="">학교선택</option>
          <option v-for="ps in PRESET_SCHOOLS" :key="ps.school_code" :value="ps.school_code">{{ ps.school_name }}</option>
        </select>
        <input v-model="school" type="text" class="inp" :class="{'inp-active':schoolCode}" placeholder="학교검색" autocomplete="off" @input="onSchoolInput" @blur="closeSuggestions" />
        <ul v-if="showSuggestions" class="suggestions" role="listbox">
          <li v-for="item in suggestions" :key="item.school_code" class="suggestion-item" role="option" @mousedown.prevent="selectSchool(item)">
            <span class="suggestion-name">{{ item.school_name }}</span>
            <span class="suggestion-region">{{ item.region }}</span>
          </li>
        </ul>
      </div>
      <input v-model="dish" type="text" class="inp inp-dish" placeholder="요리검색" />
      <span class="sep">|</span>
      <div class="chip-group">
        <button v-for="t in SCHOOL_TYPE_OPTIONS" :key="t" type="button" class="chip chip-sm" :class="{on:schoolTypes.includes(t)}" @click="toggleSchoolType(t)">{{ t }}</button>
      </div>
      <span class="sep">|</span>
      <div class="chip-group">
        <button v-for="m in MONTH_ROW1" :key="m" type="button" class="chip chip-xs" :class="{on:months.includes(m)}" @click="toggleMonth(m)">{{ m }}월</button>
        <button v-for="m in MONTH_ROW2" :key="m" type="button" class="chip chip-xs" :class="{on:months.includes(m)}" @click="toggleMonth(m)">{{ m }}월</button>
      </div>
      <span class="sep">|</span>
      <div class="chip-group">
        <button v-for="y in YEAR_OPTIONS" :key="y" type="button" class="chip" :class="{on:years.includes(y)}" @click="toggleYear(y)">{{ y }}</button>
      </div>
      <span class="sep">|</span>
      <button type="submit" class="btn-search" :disabled="isDisabled">검색</button>
      <button type="button" class="btn-reset" @click="resetForm">초기화</button>
    </div>
  </form>
</template>

<style scoped>
.form-bar {
  background: var(--surface);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-md);
  padding: 6px 8px;
}

.row-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

/* ── 입력 ── */
.inp {
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 6px 10px;
  font-size: 13px;
  font-family: var(--font);
  color: var(--text);
  outline: none;
  transition: border-color var(--transition);
  min-width: 0;
}

.inp:focus { border-color: var(--primary); }
.inp::placeholder { color: var(--text-subtle); }
.inp-active { border-color: var(--primary); }

.inp-sel {
  appearance: none;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239ba3b5' stroke-width='2.5'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
  padding-right: 22px;
}

.cell-school {
  display: flex;
  gap: 4px;
}

.cell-school .inp-sel { flex: 1; font-size: 11px; padding: 5px 20px 5px 6px; }
.cell-school .inp { flex: 1; }
.cell-school { flex: 2; }
.inp-dish { flex: 1; }

/* ── 칩 공통 ── */
.chip {
  padding: 3px 12px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: 12px;
  font-family: var(--font);
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition);
}

.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.on {
  background: var(--primary-muted);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.chip-sm { font-size: 11px; padding: 3px 8px; }
.chip-xs { font-size: 11px; padding: 2px 6px; }

.chip-group {
  display: flex;
  gap: 3px;
  align-items: center;
  flex-wrap: wrap;
}

.sep {
  color: var(--border);
  font-size: 14px;
  user-select: none;
  margin: 0 2px;
}

/* ── 버튼 ── */
.btn-search {
  padding: 5px 14px;
  background: var(--primary);
  color: var(--text-invert);
  border: none;
  border-radius: var(--r-sm);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition);
}

.btn-search:hover:not(:disabled) { background: var(--primary-hover); }
.btn-search:disabled { background: var(--border); color: var(--text-subtle); cursor: not-allowed; }

.btn-reset {
  padding: 5px 10px;
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: 12px;
  font-family: var(--font);
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition);
}

.btn-reset:hover { border-color: var(--error); color: var(--error); }

/* ── 자동완성 드롭다운 ── */
.suggestions {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-lg);
  list-style: none;
  margin: 0;
  padding: var(--sp-1) 0;
  z-index: 100;
  max-height: 220px;
  overflow-y: auto;
}

.suggestion-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px var(--sp-4);
  cursor: pointer;
  transition: background var(--transition);
  gap: var(--sp-3);
}

.suggestion-item:hover {
  background: var(--primary-muted);
}

.suggestion-name {
  font-size: var(--text-sm);
  color: var(--text);
  font-weight: 500;
}

.suggestion-region {
  font-size: var(--text-xs);
  color: var(--text-subtle);
  flex-shrink: 0;
}

/* ── 모바일 ── */
@media (max-width: 640px) {
  .form-bar { padding: 6px 8px; gap: 4px; }
  .row { gap: 4px; flex-wrap: wrap; }
  .row-chips { gap: 3px; }
  .inp { padding: 5px 6px; font-size: 11px; }
  .cell-school .inp-sel { flex: 0 0 110px; font-size: 10px; }
  .cell-dish { flex: 1 1 100px; }
  .chip { padding: 2px 6px; font-size: 10px; }
  .chip-sm { font-size: 9px; padding: 2px 5px; }
  .chip-xs { font-size: 9px; padding: 1px 4px; }
  .sep { font-size: 10px; margin: 0 1px; }
  .btn-search { padding: 4px 10px; font-size: 11px; }
  .btn-reset { padding: 4px 8px; font-size: 10px; }
}
</style>
