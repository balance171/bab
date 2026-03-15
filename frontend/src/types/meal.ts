export interface MealRow {
  id: number
  region: string
  school_name: string
  meal_date: string // "YYYY-MM-DD"
  meal_type: string // 조식 | 중식 | 석식
  soup: string | null
  main_dish: string | null
  side1: string | null
  dessert: string | null
  menu_full: string
  search_key: string
}

export interface MealsResponse {
  total: number
  page: number
  page_size: number
  data: MealRow[]
}

export interface SearchParams {
  school?: string
  school_code?: string   // 자동완성 선택 시 — 정확 매칭 (빠름)
  dish?: string
  month?: number
  months?: number[]
  years?: number[]
  sort?: string
  order?: 'asc' | 'desc' | 'default'
  page?: number
  page_size?: number
}

export interface SchoolItem {
  school_name: string
  school_code: string
  region: string
}
