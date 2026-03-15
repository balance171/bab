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

function handleSubmit() {
  if (isDisabled.value) return
  const schoolText = school.value.trim()
  // 학교명 필드가 비어있으면 school_code도 무시
  const code = schoolText ? schoolCode.value : undefined
  emit('search', {
    school: code ? schoolText : (schoolText || undefined),
    school_code: code,
    dish: dish.value.trim() || undefined,
    month: months.value.length === 1 ? months.value[0] : undefined,
    months: months.value.length > 1 ? [...months.value] : undefined,
    years: years.value.length ? [...years.value] : undefined,
    page: 1,
  })
}

function fill(params: { school: string; dish: string; month?: number; months?: number[]; years?: number[]; school_code?: string }) {
  school.value = params.school
  schoolCode.value = params.school_code
  dish.value = params.dish
  months.value = params.months ? [...params.months] : (params.month ? [params.month] : [])
  years.value = params.years ? [...params.years] : []
}

defineExpose({ fill })
</script>

<template>
  <form class="form-bar" @submit.prevent="handleSubmit">
      <div class="field" style="position: relative">
        <label class="field-label" for="school-input">
          학교명
          <span v-if="schoolCode && school.trim()" class="code-badge">선택됨</span>
        </label>
        <div class="school-input-group">
          <select
            class="field-input field-select school-preset"
            :value="schoolCode ?? ''"
            @change="onPresetChange"
          >
            <option value="">직접 입력</option>
            <option
              v-for="ps in PRESET_SCHOOLS"
              :key="ps.school_code"
              :value="ps.school_code"
            >{{ ps.school_name }}</option>
          </select>
          <input
            id="school-input"
            v-model="school"
            type="text"
            class="field-input school-text"
            :class="{ 'input-selected': schoolCode }"
            placeholder="또는 학교명 검색"
            autocomplete="off"
            @input="onSchoolInput"
            @blur="closeSuggestions"
          />
        </div>
        <ul v-if="showSuggestions" class="suggestions" role="listbox">
          <li
            v-for="item in suggestions"
            :key="item.school_code"
            class="suggestion-item"
            role="option"
            @mousedown.prevent="selectSchool(item)"
          >
            <span class="suggestion-name">{{ item.school_name }}</span>
            <span class="suggestion-region">{{ item.region }}</span>
          </li>
        </ul>
      </div>

      <div class="field">
        <label class="field-label" for="dish-input">요리명</label>
        <input
          id="dish-input"
          v-model="dish"
          type="text"
          class="field-input"
          placeholder="예) 된장국"
        />
      </div>

      <div class="field field-month">
        <div class="month-group" role="group" aria-label="월 선택">
          <div class="month-row">
            <button v-for="m in MONTH_ROW1" :key="m" type="button"
              class="month-chip" :class="{ active: months.includes(m) }"
              @click="toggleMonth(m)">{{ m }}월</button>
          </div>
          <div class="month-row">
            <button v-for="m in MONTH_ROW2" :key="m" type="button"
              class="month-chip" :class="{ active: months.includes(m) }"
              @click="toggleMonth(m)">{{ m }}월</button>
          </div>
        </div>
      </div>

      <div class="field">
        <label class="field-label">연도</label>
        <div class="year-group" role="group" aria-label="연도 선택">
          <button
            v-for="y in YEAR_OPTIONS"
            :key="y"
            type="button"
            class="year-chip"
            :class="{ active: years.includes(y) }"
            :aria-pressed="years.includes(y)"
            @click="toggleYear(y)"
          >
            {{ y }}
          </button>
        </div>
      </div>

      <button type="submit" class="btn-search" :disabled="isDisabled">
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        검색
      </button>
  </form>
</template>

<style scoped>
.form-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
  align-items: flex-end;
  background: var(--surface);
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-md);
  padding: var(--sp-4) var(--sp-5);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  flex: 1;
  min-width: 140px;
}

.field-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}

.field-input {
  background: var(--surface-raised);
  border: 1.5px solid transparent;
  border-radius: var(--r-md);
  padding: 10px var(--sp-4);
  font-size: var(--text-sm);
  font-family: var(--font);
  color: var(--text);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    background var(--transition);
  outline: none;
  width: 100%;
}

.field-input::placeholder {
  color: var(--text-subtle);
}

.field-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--primary-muted);
  background: var(--surface);
}

.field-select {
  appearance: none;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239ba3b5' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.btn-search {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  background: var(--primary);
  color: var(--text-invert);
  border: none;
  border-radius: var(--r-md);
  padding: 11px var(--sp-6);
  font-size: var(--text-sm);
  font-weight: 600;
  font-family: var(--font);
  letter-spacing: -0.01em;
  cursor: pointer;
  transition:
    background var(--transition),
    transform var(--transition),
    box-shadow var(--transition);
  margin-top: 0;
  align-self: flex-end;
  min-width: 100px;
  flex-shrink: 0;
}

.btn-search:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(123, 114, 247, 0.4);
}

.btn-search:active:not(:disabled) {
  transform: translateY(0);
}

.btn-search:disabled {
  background: var(--border);
  color: var(--text-subtle);
  cursor: not-allowed;
}

.year-group {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.year-chip {
  flex: 1;
  min-width: 56px;
  padding: 7px 0;
  background: var(--surface-raised);
  border: 1.5px solid var(--border);
  border-radius: var(--r-md);
  font-size: var(--text-sm);
  font-family: var(--font);
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    background var(--transition),
    border-color var(--transition),
    color var(--transition);
  letter-spacing: -0.01em;
}

.year-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.year-chip.active {
  background: var(--primary-muted);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

/* ── 월 칩 ── */
.field-month {
  min-width: 200px;
}

.month-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.month-row {
  display: flex;
  gap: 3px;
}

.month-chip {
  padding: 4px 0;
  min-width: 32px;
  flex: 1;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  font-size: 11px;
  font-family: var(--font);
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    background var(--transition),
    border-color var(--transition),
    color var(--transition);
}

.month-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.month-chip.active {
  background: var(--primary-muted);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

/* ── 학교 입력 그룹 ── */
.school-input-group {
  display: flex;
  gap: var(--sp-2);
}

.school-preset {
  flex: 0 0 auto;
  width: 170px;
  font-size: var(--text-xs);
  padding-right: 28px;
}

.school-text {
  flex: 1;
  min-width: 0;
}

/* ── 자동완성 ── */
.code-badge {
  display: inline-block;
  background: var(--primary-muted);
  color: var(--primary);
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--r-full);
  margin-left: var(--sp-2);
  vertical-align: middle;
}

.input-selected {
  border-color: var(--primary) !important;
  background: var(--surface) !important;
}

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
</style>
