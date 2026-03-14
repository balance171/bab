#!/usr/bin/env bash
# NEIS 급식 검색 — 전체 테스트 일괄 실행
#
# 포함 항목:
#   1. Backend pytest (tests/)
#   2. Frontend npm run build (type-check + vite build)
#   3. API 스모크 테스트 (GET /health, GET /api/meals?school=가락)
#   4. 로그 파일 존재 확인
#
# 사용법:
#   bash scripts/04_test_all.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

SMOKE_PORT=18099   # 기존 서비스 충돌 방지용 포트
SMOKE_PID=""

PASS=0
FAIL=0

# ── 색상 (터미널 지원 시) ──────────────────────────────────────
if [ -t 1 ]; then
  GREEN="\033[0;32m"; RED="\033[0;31m"; RESET="\033[0m"; BOLD="\033[1m"
else
  GREEN=""; RED=""; RESET=""; BOLD=""
fi

log_section() { echo; echo -e "${BOLD}══ $1 ══${RESET}"; }
log_ok()      { echo -e "  ${GREEN}[OK]${RESET}  $1"; PASS=$((PASS + 1)); }
log_fail()    { echo -e "  ${RED}[FAIL]${RESET} $1"; FAIL=$((FAIL + 1)); }
log_skip()    { echo    "  [SKIP] $1"; }

cleanup() {
  if [ -n "$SMOKE_PID" ]; then
    kill "$SMOKE_PID" 2>/dev/null || true
    SMOKE_PID=""
  fi
}
trap cleanup EXIT INT TERM

echo -e "${BOLD}[04_test_all.sh] 전체 테스트 시작: $(date '+%Y-%m-%d %H:%M:%S')${RESET}"

# ────────────────────────────────────────────────────────────────
# 1. Backend: pytest
# ────────────────────────────────────────────────────────────────
log_section "Backend: pytest"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  log_fail "backend/.env 없음 — pytest 건너뜀"
elif (cd "$BACKEND_DIR" && uv run pytest tests/ -v --tb=short 2>&1); then
  log_ok "pytest 전체 통과"
else
  log_fail "pytest 실패"
fi

# ────────────────────────────────────────────────────────────────
# 2. Frontend: npm run build
# ────────────────────────────────────────────────────────────────
log_section "Frontend: npm run build"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log_fail "node_modules 없음 — cd frontend && npm install 먼저 실행하세요"
elif (cd "$FRONTEND_DIR" && npm run build 2>&1); then
  log_ok "frontend build (type-check + vite) 통과"
else
  log_fail "frontend build 실패"
fi

# ────────────────────────────────────────────────────────────────
# 3. API 스모크 테스트
# ────────────────────────────────────────────────────────────────
log_section "API smoke test (포트 $SMOKE_PORT)"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  log_skip "backend/.env 없음 — 스모크 테스트 건너뜀"
else
  # 백그라운드로 API 서버 기동
  cd "$BACKEND_DIR"
  API_PORT=$SMOKE_PORT uv run uvicorn app.main:app \
    --host 127.0.0.1 --port "$SMOKE_PORT" \
    --no-access-log \
    >/tmp/neis_smoke_api.log 2>&1 &
  SMOKE_PID=$!

  # 최대 20초 대기
  READY=0
  for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:${SMOKE_PORT}/health" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 1
  done

  if [ "$READY" -eq 0 ]; then
    log_fail "API 서버 기동 실패 (20초 타임아웃) — /tmp/neis_smoke_api.log 확인"
    SMOKE_PID=""
  else
    # GET /health
    HEALTH_BODY=$(curl -sf "http://127.0.0.1:${SMOKE_PORT}/health" 2>/dev/null)
    if echo "$HEALTH_BODY" | grep -q '"status":"ok"'; then
      log_ok "GET /health  →  $HEALTH_BODY"
    else
      log_fail "GET /health 응답 이상: $HEALTH_BODY"
    fi

    # GET /api/meals?school=가락
    MEALS_BODY=$(curl -sf \
      "http://127.0.0.1:${SMOKE_PORT}/api/meals?school=%EA%B0%80%EB%9D%BD" \
      2>/dev/null)
    if echo "$MEALS_BODY" | grep -q '"total"'; then
      TOTAL=$(echo "$MEALS_BODY" | grep -o '"total":[0-9]*' | head -1)
      log_ok "GET /api/meals?school=가락  →  $TOTAL"
    else
      log_fail "GET /api/meals?school=가락 응답 이상: ${MEALS_BODY:0:120}"
    fi

    kill "$SMOKE_PID" 2>/dev/null || true
    SMOKE_PID=""
  fi
fi

# ────────────────────────────────────────────────────────────────
# 4. 로그 파일 확인
# ────────────────────────────────────────────────────────────────
log_section "로그 파일 확인"

LOG_FILE="$BACKEND_DIR/logs/api.log"
if [ -f "$LOG_FILE" ]; then
  SIZE=$(wc -c < "$LOG_FILE" | tr -d ' ')
  log_ok "backend/logs/api.log 존재 (${SIZE}B)"
  echo "  ── 최근 3줄 ──"
  tail -3 "$LOG_FILE" | sed 's/^/    /'
else
  log_fail "backend/logs/api.log 없음"
fi

# ────────────────────────────────────────────────────────────────
# 결과 요약
# ────────────────────────────────────────────────────────────────
echo
echo -e "${BOLD}══════════════════════════════════════${RESET}"
echo -e "  완료: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "  ${GREEN}통과 $PASS${RESET}  /  ${RED}실패 $FAIL${RESET}"
echo -e "${BOLD}══════════════════════════════════════${RESET}"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
