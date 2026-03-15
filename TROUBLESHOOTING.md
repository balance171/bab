# Troubleshooting Log

NEIS 급식 검색 웹앱 개발 과정에서 발생한 에러와 해결 방법 기록.

---

## 1. CSS @import 순서 경고 (Tailwind v4)

**에러**: Tailwind v4에서 `@import url(...)` (Pretendard CDN)이 `@import 'tailwindcss'` 뒤에 있으면 경고 발생

**원인**: Tailwind v4는 모든 `@import`가 파일 최상단에 있어야 함

**해결**: Pretendard CDN import를 `main.css` 최상단으로 이동, `tokens.css`에서 제거
```css
/* main.css — 반드시 이 순서 */
@import url('https://cdn.jsdelivr.net/.../pretendard.css');
@import 'tailwindcss';
@import './tokens.css';
```

---

## 2. TypeScript noUncheckedIndexedAccess 에러 (TS2345)

**에러**: `ResultTable.vue`에서 `const [y, m, day] = d.split('-').map(Number)` 사용 시 `number | undefined` 타입 에러

**원인**: `tsconfig.app.json`에 `noUncheckedIndexedAccess: true` 설정으로 배열 인덱스 접근이 `T | undefined` 반환

**해결**: 배열 destructuring 대신 개별 접근 + fallback 값 사용
```typescript
const parts = d.split('-')
const year = Number(parts[0] ?? 2024)
const month = Number(parts[1] ?? 1)
const day = Number(parts[2] ?? 1)
```

---

## 3. 포트 충돌 (5173, 5174, 8000)

**에러**: Vite dev server와 uvicorn이 이미 사용 중인 포트에서 시작 실패. `ERR_CONNECTION_REFUSED`

**원인**: 다른 프로젝트(`recommend_system` 등)가 5173, 5174, 8000 포트를 점유 중

**해결**:
- 프론트엔드: `vite.config.ts`에서 `port: 5177`, `strictPort: false` 설정
- 백엔드: `scripts/03_run_api.sh`에서 8007부터 빈 포트 자동 탐색
```bash
PORT=8007
while lsof -i ":$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done
```

---

## 4. NEIS 마커 미제거 (`*`, `k`, `s`, `☆`, `△`)

**에러**: DB의 `soup`, `main_dish`, `side1`, `dessert` 컬럼에 `*바지락살미역국`, `동태찌개k` 같은 NEIS 마커가 남아있음

**원인 1 — 앞쪽 마커**: `_clean_item()`이 뒤쪽 마커만 제거 (`[a-zA-Z*☆△★]+$`), 앞쪽 `*` 미처리

**원인 2 — 뒤쪽 마커 미작동**: NEIS 원본 데이터가 `동태찌개k  (5.6.9.13.)` 형식 — `k`와 `(` 사이에 공백 2개가 있어서 `" ("` 기준 절단 후 `"동태찌개k "` (뒤에 공백)이 남고, `[a-zA-Z*]+$` regex가 공백 때문에 `k`를 잡지 못함

**해결**: `_clean_item()`에 `.strip()` 호출을 마커 제거 전에 추가, 앞쪽 마커 제거 단계 추가
```python
def _clean_item(item: str) -> str:
    s = item.strip()
    idx = s.find(" (")           # 1단계: " (" 기준 절단
    if idx >= 0: s = s[:idx]
    idx = s.find("(")            # 2단계: "(" 기준 절단
    if idx >= 0: s = s[:idx]
    s = s.strip()                # ★ 핵심: 공백 먼저 제거
    s = re.sub(r"[a-zA-Z*☆△★]+$", "", s)   # 3단계: 뒤 마커
    s = re.sub(r"^[*☆△★]+", "", s)          # 4단계: 앞 마커
    return s.strip()
```

**후속 조치**: TRUNCATE TABLE meals → 인제스트 전체 재실행

---

## 5. 검색 결과 0건 (데이터 부족)

**에러**: `학교=가락, 요리=된장, 월=1` 검색 시 0건 반환

**원인 1**: DB에 테스트 데이터 514행(가락고등학교 1개교)만 존재
**원인 2**: 가락고등학교에 1월(방학) 급식 데이터 없음

**해결**: 5개 지역(서울/부산/대구/인천/경기) 전체 인제스트 실행, 연도 필터 추가

---

## 6. GIN 트리그램 인덱스 극도로 느림 (20초+)

**에러**: `school_name ILIKE '%가락%'` 또는 `search_key LIKE '%된장%'` 쿼리가 20초 이상 소요, 프론트엔드 무한 로딩

**원인**: Supabase 프리 티어(0.25 vCPU, 제한된 IOPS)에서 830K행 GIN 트리그램 인덱스 스캔이 극도로 느림. 한국어 2글자(`가락`)는 트리그램 선택성이 낮아 인덱스가 오히려 역효과

**분석 (EXPLAIN 결과)**:
```
Bitmap Index Scan on idx_meals_school_name_trgm  (cost=14035.15)
→ GIN 인덱스 스캔 비용이 14,035 (전체 쿼리의 99%)
```

**해결 — 다단계 최적화**:

### 6-1. meal_month / meal_year 컬럼 추가
`EXTRACT(MONTH FROM meal_date)` 대신 사전 계산된 INTEGER 컬럼 + btree 인덱스:
```sql
ALTER TABLE meals ADD COLUMN meal_month SMALLINT;
ALTER TABLE meals ADD COLUMN meal_year SMALLINT;
CREATE INDEX idx_meals_year_month ON meals (meal_year, meal_month);
```

### 6-2. CTE MATERIALIZED 쿼리 전략
btree 인덱스 조건(month/year/school_code)을 CTE로 먼저 적용 → 작은 결과셋에서 텍스트 검색:
```sql
-- 이전 (20초+): GIN 스캔 830K행
SELECT COUNT(*) FROM meals
WHERE search_key LIKE '%된장%' AND meal_month = 4 AND meal_year = 2025;

-- 이후 (0.95초): btree로 31K행 먼저 필터 → LIKE는 31K행에서만
WITH base AS MATERIALIZED (
    SELECT * FROM meals WHERE meal_year = 2025 AND meal_month = 4
)
SELECT COUNT(*) FROM base WHERE search_key LIKE '%된장%';
```

### 6-3. 학교 자동완성 + school_code 정확 매칭
`school_name ILIKE '%가락%'` (GIN, 20초) → `school_code = '7010057'` (btree, 0.7초):
- 백엔드: `GET /api/schools?q=가락` 엔드포인트 추가 (메모리 캐싱)
- 프론트엔드: SearchForm에 자동완성 드롭다운

### 6-4. 캐시 예열
서버 시작 시 학교 목록 로드 → PostgreSQL shared buffer 예열 → 첫 검색도 1초 이내

**성능 개선 결과**:

| 쿼리 유형 | 이전 | 이후 |
|-----------|------|------|
| school_code + month + year | 20초+ | **0.7초** |
| dish + month + year | 20초+ (타임아웃) | **0.95초** |
| 학교 자동완성 | N/A | **0.02초** |

---

## 7. 프론트엔드 skeleton + 이전 pagination 동시 표시

**에러**: 새 검색 실행 중 로딩 skeleton이 표시되면서 동시에 이전 검색의 pagination("2건")이 보임

**원인**: `doSearch()`에서 `loading = true` 설정 시 `results`를 초기화하지 않아 이전 결과가 남아있음

**해결**: 검색 시작 시 `results.value = null` 추가
```typescript
async function doSearch(params: SearchParams) {
  loading.value = true
  error.value = null
  results.value = null  // ★ 이전 결과 초기화
  // ...
}
```

---

## 8. Supabase statement_timeout (2분)

**에러**: 830K행 UPDATE(meal_month/meal_year 백필) 시 `QueryCanceledError: canceling statement due to statement timeout`

**원인**: Supabase 기본 `statement_timeout = 2min`, UPDATE가 2분 초과

**해결**: 연결별로 타임아웃 해제 후 실행
```python
conn = await asyncpg.connect(dsn)
await conn.execute("SET statement_timeout = 0")
await conn.execute("UPDATE meals SET meal_month = ...")
```

---

## 9. Vercel 배포 — "Failed to fetch"

**에러**: Vercel에 프론트엔드만 배포 후 API 호출 시 `Failed to fetch`

**원인**: 프론트엔드만 Vercel에 배포되고, 백엔드 API(`/api/meals`)를 처리할 서버가 없음

**해결**: Vercel Python Serverless Function으로 API도 함께 배포
```
api/index.py  → /api/meals, /api/schools, /api/health 처리
vercel.json   → rewrites로 /api/* → api/index.py 라우팅
```

---

## 10. Vercel — pydantic-core Rust 컴파일 실패

**에러**: Vercel 빌드 시 `pydantic-core` 설치 실패 — `Cargo build finished with exit status: 101`

**원인**: Vercel Python 런타임이 Python 3.14 사용, pydantic-core에 Python 3.14용 pre-built wheel이 없어 Rust 소스 빌드 시도 → 실패

**해결**: FastAPI/pydantic 대신 순수 Python(`BaseHTTPRequestHandler`) + `psycopg2-binary`로 재작성
```python
# requirements.txt — 최소 의존성
psycopg2-binary>=2.9.0
```

---

## 11. Vercel — DATABASE_URL 줄바꿈 문자

**에러**: API 응답 `database "postgres\n" does not exist`

**원인**: `echo "$DATABASE_URL" | vercel env add` 사용 시 `echo`가 자동 추가하는 `\n`이 환경변수에 포함됨

**해결**: `printf`로 줄바꿈 없이 전달
```bash
printf "%s" "$DATABASE_URL" | vercel env add DATABASE_URL production --yes
```

---

## 12. Vercel — 프론트엔드 FUNCTION_INVOCATION_FAILED

**에러**: `https://20260314bab.vercel.app/` 접속 시 `FUNCTION_INVOCATION_FAILED`

**원인**: Vercel이 프로젝트를 FastAPI로 자동 감지하여 모든 요청을 Python 함수로 라우팅

**해결**: `vercel.json`에 `"framework": null` 추가하여 자동 감지 비활성화
```json
{
  "framework": null,
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/index.py" }
  ]
}
```

---

## 13. CTE MATERIALIZED + school_code 조합 타임아웃

**에러**: `school_code + dish` 검색 시 `canceling statement due to statement timeout`

**원인**: school_code가 fast_clauses에 포함되어 CTE MATERIALIZED 경로로 빠짐. school_code로 필터된 ~1000행에 CTE를 쓸 필요 없는데 오버헤드 발생

**해결**: school_code가 있으면 CTE를 사용하지 않고 직접 WHERE 사용
```python
has_school_code = any("school_code" in c for c in fast_clauses)
use_cte = fast_clauses and slow_clauses and not has_school_code
```

---

## 14. Vercel 서버리스 함수 statement_timeout

**에러**: Vercel에서 `canceling statement due to statement timeout` (Supabase 기본 2분)

**원인**: Vercel 서버리스 함수의 psycopg2 연결에 statement_timeout 미설정

**해결**: 연결 시 statement_timeout 명시 설정
```python
def _get_conn():
    conn = psycopg2.connect(dsn)
    conn.cursor().execute("SET statement_timeout = '25000'")
    return conn
```

---

## 15. 학교명 텍스트 입력 시 ILIKE 풀스캔 타임아웃

**에러**: 자동완성 미사용 + 텍스트 입력 → `school_name ILIKE '%원일중%'` → 150만 행 풀스캔 → 타임아웃

**해결**: `handleSubmit`에서 school_code 없으면 `/api/schools?q=X`로 자동 매칭 후 school_code 정확 검색 전환

---

## 16. Supabase MaxClientsInSessionMode 연결 풀 고갈

**에러**: `MaxClientsInSessionMode: max clients reached`

**원인**: 여러 프로세스가 Session pooler 연결 점유. kill해도 Supabase 측 5-10분 후 해제

**해결**: 모든 프로세스 kill → 5분 대기 → 단일 프로세스만 실행. asyncpg 대신 psycopg2 사용

---

## 17. 인제스트 executemany 대량 INSERT 타임아웃

**에러**: 500건+ `executemany` INSERT → Supabase statement_timeout(30초) 초과

**원인**: Mumbai 리전 왕복 200-500ms × 500건 = 누적 타임아웃

**해결**: 50건씩 배치 분할 INSERT
```python
BATCH_SIZE = 50
for i in range(0, len(records), BATCH_SIZE):
    cur.executemany(UPSERT_SQL, records[i:i+BATCH_SIZE])
```

---

## 18. 인제스트 학교별 EXISTS 체크 병목

**에러**: 학교마다 `SELECT COUNT(*) WHERE school_code = %s` → 건당 300ms × 390교 = 2분+

**해결**: EXISTS 체크 제거. `ON CONFLICT DO NOTHING`이 중복 자동 처리하므로 불필요
