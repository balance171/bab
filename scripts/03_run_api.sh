#!/usr/bin/env bash
# FastAPI 서버 실행 (포트 충돌 시 자동으로 다음 빈 포트 사용)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "[ERROR] backend/.env 파일이 없습니다. backend/.env.example을 복사해 작성하세요."
  exit 1
fi

# 빈 포트 찾기 (기본값: API_PORT 환경변수 → 8000부터 순차 탐색)
START_PORT=${API_PORT:-8007}
PORT=$START_PORT
while lsof -i ":$PORT" >/dev/null 2>&1; do
  echo "[03_run_api.sh] 포트 $PORT 사용 중, 다음 포트 시도..."
  PORT=$((PORT + 1))
done

if [ "$PORT" -ne "$START_PORT" ]; then
  echo "[03_run_api.sh] 포트 $PORT 로 변경됨"
  echo "[03_run_api.sh] frontend/.env.local 의 BACKEND_URL 을 http://localhost:$PORT 로 수정하세요"
fi

cd "$BACKEND_DIR"
echo "[03_run_api.sh] FastAPI 서버 시작: http://localhost:$PORT"
uv run uvicorn app.main:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "$PORT" \
  --reload
