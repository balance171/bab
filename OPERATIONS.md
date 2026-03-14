# NEIS 급식 검색 — 운영 가이드

> 프로젝트 루트: `/Users/jameskim_mini/trybab/20260314_bab/`

---

## 1. 사전 요구사항

| 항목 | 버전 | 확인 방법 |
|------|------|-----------|
| Python | 3.11 (uv 관리) | `uv python list` |
| Node.js | 20.x 이상 | `node -v` |
| uv | 최신 | `uv --version` |
| Supabase | PostgreSQL + pg_trgm | DB 접속 확인 |

---

## 2. 최초 실행 순서

### 2-1. 환경 변수 설정

```bash
# backend
cp backend/.env.example backend/.env
# .env 편집: DATABASE_URL, NEIS_API_KEY 입력

# frontend
cp frontend/.env.example frontend/.env.local
# .env.local 편집: VITE_API_BASE_URL=http://localhost:8000
```

### 2-2. 의존성 설치

```bash
# Backend (uv가 자동으로 venv 생성)
cd backend && uv sync

# Frontend
cd frontend && npm install
```

### 2-3. DB 마이그레이션

```bash
cd backend && uv run python migrate.py
```

- `meals` 테이블, GIN 인덱스(pg_trgm), RLS 생성
- **롤백**: `uv run python migrate.py --rollback`

### 2-4. 데이터 수집 (소량 테스트)

```bash
# 서울 1개교만 (빠른 확인용)
bash scripts/01_ingest.sh --region B10 --limit 1
```

### 2-5. 전처리

```bash
bash scripts/02_preprocess.sh
```

### 2-6. 전체 테스트

```bash
bash scripts/04_test_all.sh
```

### 2-7. API + 프론트 실행

```bash
# 터미널 1 — API 서버
bash scripts/03_run_api.sh

# 터미널 2 — 프론트 개발 서버
cd frontend && npm run dev
```

브라우저: http://localhost:5173

---

## 3. 전체 데이터 수집 (5개 지역 전체)

> 약 1~3시간 소요. 수집 전 DB 용량 확인 권장.

```bash
# 전체 지역 (B10=서울, C10=부산, D10=대구, E10=인천, J10=경기)
bash scripts/01_ingest.sh
```

지역별 개별 수집:

```bash
bash scripts/01_ingest.sh --region B10   # 서울
bash scripts/01_ingest.sh --region C10   # 부산
bash scripts/01_ingest.sh --region D10   # 대구
bash scripts/01_ingest.sh --region E10   # 인천
bash scripts/01_ingest.sh --region J10   # 경기
```

수집 후 전처리 재실행:

```bash
bash scripts/02_preprocess.sh --batch 1000
```

수집 기간: `20230101 ~ 20260313` (ingest.py `DATE_FROM`, `DATE_TO` 상수)

---

## 4. 정기 업데이트

새 급식 데이터 추가 시:

```bash
bash scripts/01_ingest.sh   # ON CONFLICT DO NOTHING — 중복 안전
bash scripts/02_preprocess.sh
```

---

## 5. 로그 위치

| 파일 | 내용 |
|------|------|
| `backend/logs/api.log` | API 요청/응답, 오류 (JSON 구조화) |
| `/tmp/neis_smoke_api.log` | 04_test_all.sh 스모크 테스트 서버 로그 |

실시간 로그 확인:

```bash
tail -f backend/logs/api.log | python3 -m json.tool   # JSON 예쁘게
tail -f backend/logs/api.log                           # 원본
```

---

## 6. 장애 대응

### API 서버가 뜨지 않음

```bash
# 포트 8000 충돌 확인
lsof -i :8000

# .env 값 확인
cat backend/.env

# DB 접속 테스트
cd backend && uv run python -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()
asyncio.run(asyncpg.connect(os.environ['DATABASE_URL']))
print('DB 접속 OK')
"
```

### pytest 실패

```bash
cd backend && uv run pytest tests/ -v --tb=long
```

### DB 연결 오류 (Supabase)

- Supabase pooler URL 사용 여부 확인 (`aws-ap-south-1.pooler.supabase.com:5432`)
- 비밀번호에 특수문자 포함 시 URL 인코딩 필요

### 수집 도중 중단

`ON CONFLICT DO NOTHING` upsert이므로 재실행 안전. 이미 수집된 행은 건너뜁니다.

```bash
bash scripts/01_ingest.sh --region B10   # 중단된 지역부터 재실행
```

### search_key NULL 행 발생

전처리가 미실행된 경우:

```bash
bash scripts/02_preprocess.sh --batch 500
```

### 프론트 빌드 실패

```bash
cd frontend
npm install          # node_modules 갱신
npm run type-check   # TS 오류만 확인
npm run build-only   # vite 빌드만
```

---

## 7. 전체 스크립트 요약

| 스크립트 | 역할 |
|----------|------|
| `scripts/01_ingest.sh` | NEIS API → DB 수집 |
| `scripts/02_preprocess.sh` | NULL 컬럼 파싱 (soup/main_dish/side1/dessert) |
| `scripts/03_run_api.sh` | FastAPI 서버 실행 (`--reload`) |
| `scripts/04_test_all.sh` | pytest + build + 스모크 테스트 일괄 실행 |

---

## 8. 환경변수 정리

### `backend/.env`

```
DATABASE_URL=postgresql://...@aws-ap-south-1.pooler.supabase.com:5432/postgres
NEIS_API_KEY=fcf0d92556374190a6655f466c1b857e
LOG_LEVEL=INFO
```

### `frontend/.env.local`

```
VITE_API_BASE_URL=http://localhost:8000
```

---

## 9. DB 스키마 요약

```sql
meals (
  id            bigint  PK
  acquired_at   timestamptz
  region        text          -- 서울특별시 등
  region_code   text          -- B10, C10 등
  school_name   text
  school_code   text
  meal_date     date
  meal_type     text          -- 조식 | 중식 | 석식
  menu_full     text          -- 원문 메뉴 (알레르기 코드 포함)
  search_key    text          -- 정규화된 검색 키
  soup          text          -- 국
  main_dish     text          -- 주요리
  side1         text          -- 부요리
  dessert       text          -- 디저트
  UNIQUE (school_code, meal_date, meal_type, menu_full)
)
```
