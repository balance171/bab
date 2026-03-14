#!/usr/bin/env bash
# NEIS 급식 데이터 수집 및 DB upsert
#
# 사용법:
#   bash scripts/01_ingest.sh                  # 전체 지역
#   bash scripts/01_ingest.sh --region B10     # 서울만
#   bash scripts/01_ingest.sh --region B10 --limit 1  # 서울 1개교 (테스트)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "[ERROR] backend/.env 파일이 없습니다."
  exit 1
fi

cd "$BACKEND_DIR"
echo "[01_ingest.sh] 수집 시작: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
uv run python -m app.ingest "$@"
echo "[01_ingest.sh] 수집 완료: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
