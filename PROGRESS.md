# NEIS 급식 검색 웹 전환 — 진행 현황

> 작성일: 2026-03-14
> 프로젝트 루트: `/Users/jameskim_mini/trybab/20260314_bab/`

---

## 환경 정보

| 항목 | 값 |
|------|-----|
| Python | 3.11.11 (uv 관리) |
| Node.js | 20.19.4 |
| Backend 패키지 관리 | uv |
| Supabase pooler URL | `postgresql://postgres.jiadieaggtldngaunivn:...@aws-1-ap-south-1.pooler.supabase.com:5432/postgres` |
| NEIS API KEY | `fcf0d92556374190a6655f466c1b857e` |
| 수집 기간 | 20230101 ~ 20260313 |

---

## 완료된 단계

### ✅ STEP 1 — 프로젝트 초기 구조

- `backend/` : uv 프로젝트, FastAPI + uvicorn + structlog + asyncpg + httpx
- `frontend/` : Vue 3 + Vite + TypeScript + Tailwind CSS v4
- `scripts/` : 01~04 쉘 스크립트 뼈대
- `backend/.env` / `frontend/.env.local` 분리 생성
- 구조화 JSON 로그 (`backend/logs/api.log` 등)
- **테스트**: `/health` 200, vue-tsc + vite build 통과, api.log 생성 확인

---

### ✅ STEP 2 — DB 마이그레이션

파일: `backend/migrations/001_create_meals.sql`, `backend/migrate.py`

**meals 테이블 스키마**
```sql
id            bigint GENERATED ALWAYS AS IDENTITY PK
acquired_at   timestamptz DEFAULT now()
region        text NOT NULL
region_code   text NOT NULL
school_name   text NOT NULL
school_code   text NOT NULL
meal_date     date NOT NULL
meal_type     text NOT NULL   -- 조식/중식/석식
menu_full     text NOT NULL
search_key    text NOT NULL
soup          text
main_dish     text
side1         text
dessert       text
UNIQUE (school_code, meal_date, meal_type, menu_full)
```

**인덱스**
- `idx_meals_meal_date` (btree)
- `idx_meals_region` (btree)
- `idx_meals_school_code` (btree)
- `idx_meals_school_name_trgm` (gin, pg_trgm)
- `idx_meals_search_key_trgm` (gin, pg_trgm)

**RLS**: enabled, public SELECT 허용

**실행**: `cd backend && uv run python migrate.py`
**롤백**: `uv run python migrate.py --rollback`

---

### ✅ STEP 3 — 데이터 수집 (ingest)

파일: `backend/app/ingest.py`, `backend/app/normalize.py`, `scripts/01_ingest.sh`

**수집 흐름**
1. `schoolInfo` API → 지역별 고등학교 코드 목록
2. 학교별 `mealServiceDietInfo` API → 급식 데이터
3. `ON CONFLICT DO NOTHING` upsert

**실행**
```bash
bash scripts/01_ingest.sh                          # 전체 5개 지역
bash scripts/01_ingest.sh --region B10             # 서울만
bash scripts/01_ingest.sh --region B10 --limit 1  # 테스트 (1개교)
```

**지역 코드**: B10=서울, C10=부산, D10=대구, E10=인천, J10=경기

**현재 DB 상태**: 가락고등학교(서울) 514건 수집됨 (테스트용)
→ 전체 수집 필요 시 `bash scripts/01_ingest.sh` 실행

---

### ✅ STEP 4 — 전처리 (preprocess)

파일: `backend/app/preprocess.py`, `scripts/02_preprocess.sh`

**VBA `CleanDishNameKeepInnerSymbols` 동일 로직 적용**
- `" ("` 또는 `"("` 위치에서 절단 (알레르기 코드 제거)
- `*`, `k` 등 내부 마크는 유지

**메뉴 분해 규칙**
```
body = items[1:]  # 밥류 제외
soup      = body[0] if len >= 1
main_dish = body[1] if len >= 2
side1     = body[2] if len >= 3
dessert   = body[-1] if len >= 4  # 4개 이상일 때만
```

**실행**
```bash
bash scripts/02_preprocess.sh             # 기본 배치 500
bash scripts/02_preprocess.sh --batch 1000
```

---

### ✅ STEP 5 — API 계층

파일: `backend/app/db.py`, `backend/app/meals_router.py`, `backend/tests/test_api.py`

**엔드포인트**
```
GET /api/meals
  ?school=가락        학교명 부분일치 (ILIKE)
  &dish=된장국        요리명 (search_key LIKE, 자동 정규화)
  &month=3           월 필터 (1~12)
  &sort=meal_date    정렬 컬럼
  &order=desc        asc | desc | default
  &page=2            페이지 (50건/페이지)

→ { total, page, page_size, data: [MealRow...] }
```

**MealRow 필드**: id, region, school_name, meal_date, meal_type, soup, main_dish, side1, dessert, menu_full

**에러 처리**
- 조건 없음 → 400
- 잘못된 정렬 컬럼 → 400
- month 범위 오류 → 422
- DB 오류 → 500

**테스트**: `cd backend && uv run pytest tests/ -v` → 11/11 통과

---

## 남은 단계

### ✅ STEP 6 — Vue 화면

**구현 목록**
- [x] `src/api/meals.ts` — API 클라이언트 (`VITE_API_BASE_URL` 사용)
- [x] `src/types/meal.ts` — MealRow, MealsResponse 타입
- [x] `src/stores/recentSearch.ts` — localStorage 최근 검색 10개 관리
- [x] `src/components/SearchForm.vue` — 학교명/요리명/월 입력 폼
- [x] `src/components/ResultTable.vue` — 결과 테이블 + 헤더 클릭 정렬 토글
- [x] `src/components/Pagination.vue` — 페이지네이션 (총 건수 표시)
- [x] `src/components/RecentSearch.vue` — 최근 검색 10개 (사이드패널)
- [x] `src/views/HomeView.vue` — 전체 레이아웃 조합
- [x] `src/assets/tokens.css` — 디자인 토큰 (Pretendard + purple 팔레트)

**디자인**
- 폰트: Pretendard Variable (한/영 혼용 최적화)
- 색상: primary #7b72f7 (purple), sidebar #14162a (dark navy)
- 배경: radial-gradient 라벤더 메시
- 레이아웃: 좌측 64px 다크 사이드바 + 메인(SearchForm/RecentSearch | ResultTable/Pagination)
- 반응형: 1024px 이상 2컬럼, 640px 이하 사이드바 숨김

**테스트**: `cd frontend && npm run build` → 42 modules, type-check ✅

---

### ✅ STEP 7 — 통합 점검

**구현 목록**
- [x] `scripts/04_test_all.sh` — pytest + frontend build + API 스모크 + 로그 확인
- [x] `OPERATIONS.md` — 최초 실행, 전체 수집, 장애 대응, 환경변수 정리

---

## 현재 디렉토리 구조

```
20260314_bab/
├── backend/
│   ├── pyproject.toml          (uv 프로젝트)
│   ├── .env                    (NEIS_API_KEY, DATABASE_URL 등)
│   ├── .env.example
│   ├── migrate.py              (DB 마이그레이션 실행기)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             (FastAPI 앱, lifespan, CORS)
│   │   ├── db.py               (asyncpg 풀)
│   │   ├── logging_config.py   (structlog JSON)
│   │   ├── normalize.py        (메뉴 파싱, VBA 로직)
│   │   ├── ingest.py           (NEIS 수집 + upsert)
│   │   ├── preprocess.py       (NULL 행 전처리)
│   │   └── meals_router.py     (GET /api/meals)
│   ├── migrations/
│   │   └── 001_create_meals.sql
│   ├── tests/
│   │   └── test_api.py         (11개 통합 테스트)
│   └── logs/
│       └── api.log
├── frontend/
│   ├── .env.local              (VITE_API_BASE_URL=http://localhost:8000)
│   ├── .env.example
│   ├── vite.config.ts          (Tailwind CSS v4 플러그인)
│   ├── src/
│   │   ├── main.ts
│   │   ├── assets/main.css     (@import 'tailwindcss')
│   │   └── ...                 (Vue 기본 스캐폴드)
│   └── ...
├── scripts/
│   ├── 01_ingest.sh            ✅ 완성
│   ├── 02_preprocess.sh        ✅ 완성
│   ├── 03_run_api.sh           ✅ 완성
│   └── 04_test_all.sh          🔲 STEP 7에서 완성
└── PROGRESS.md                 (이 파일)
```

---

## 주요 기술 결정 기록

| 결정 | 내용 |
|------|------|
| `ingest_index` 컬럼 | 제거 — `id` PK로 충분 |
| 메뉴 분해 엣지케이스 | len(body)≥4 일 때만 dessert 할당 |
| `_clean_item` 로직 | VBA `CleanDishNameKeepInnerSymbols` 동일: `" ("` → `"("` 순으로 절단 |
| search_key 정규화 | API 입력도 동일 정규화 후 `LIKE %normalized%` |
| 테스트 이벤트 루프 | `asyncio_default_test_loop_scope = "session"` |
| Python 패키지 관리 | uv |
| Tailwind | v4 (`@tailwindcss/vite` 플러그인) |
