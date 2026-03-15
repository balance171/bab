import type { MealsResponse, SchoolItem, SearchParams } from '@/types/meal'

// 로컬 개발: VITE_API_BASE_URL 미설정 → 빈 문자열 → 상대경로 → Vite 프록시 경유
// 프로덕션: VITE_API_BASE_URL=https://api.example.com 설정
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export async function fetchMeals(params: SearchParams): Promise<MealsResponse> {
  const url = new URL(`${BASE_URL}/api/meals`, window.location.origin)

  if (params.school_code) url.searchParams.set('school_code', params.school_code)
  else if (params.school) url.searchParams.set('school', params.school)
  if (params.dish) url.searchParams.set('dish', params.dish)
  if (params.month) url.searchParams.set('month', String(params.month))
  if (params.years?.length) {
    for (const y of params.years) url.searchParams.append('years', String(y))
  }
  if (params.sort) url.searchParams.set('sort', params.sort)
  if (params.order && params.order !== 'default') url.searchParams.set('order', params.order)
  if (params.page && params.page > 1) url.searchParams.set('page', String(params.page))
  if (params.page_size) url.searchParams.set('page_size', String(params.page_size))

  const res = await fetch(url.toString())

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `오류 ${res.status}`)
  }

  return res.json() as Promise<MealsResponse>
}

export async function fetchSchools(q: string): Promise<SchoolItem[]> {
  const url = new URL(`${BASE_URL}/api/schools`, window.location.origin)
  if (q) url.searchParams.set('q', q)
  url.searchParams.set('limit', '30')
  const res = await fetch(url.toString())
  if (!res.ok) return []
  return res.json() as Promise<SchoolItem[]>
}
