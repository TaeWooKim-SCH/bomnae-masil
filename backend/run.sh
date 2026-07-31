#!/usr/bin/env bash
# Cloudtype 시작 명령: bash backend/run.sh (실행 루트가 어디여도 backend/로 이동해 부팅)
# 실행 루트를 backend/로 지정했다면 `bash run.sh` — 대시보드 설정에만 의존하지 않는 고정 장치(#5 검수 반영)
cd "$(dirname "$0")"
if [ -x "../.venv/bin/uvicorn" ]; then
  exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"  # 로컬: 루트 .venv
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"  # 배포: pip install된 PATH
