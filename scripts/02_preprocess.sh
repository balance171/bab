#!/usr/bin/env bash
# meals 테이블의 soup/main_dish/side1/dessert NULL 행 전처리
#
# 사용법:
#   bash scripts/02_preprocess.sh              # 기본 배치 500
#   bash scripts/02_preprocess.sh --batch 1000
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "[ERROR] backend/.env 파일이 없습니다."
  exit 1
fi

cd "$BACKEND_DIR"
echo "[02_preprocess.sh] 전처리 시작: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
uv run python -m app.preprocess "$@"
echo "[02_preprocess.sh] 전처리 완료: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
