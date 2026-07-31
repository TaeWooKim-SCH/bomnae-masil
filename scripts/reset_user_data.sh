#!/usr/bin/env bash
# 시연 전 사용자 데이터 리셋 (#51) — 시연 5분 전 1회 실행 (데모 대본 #19/#44 체크리스트)
# 지움: 사용자 데이터 전부(세션 연쇄) + KPI 실사용 이벤트 / 보존: KPI 시드·LLM 캐시·원천 데이터
# 주의: LLM 캐시 워밍(리허설 답변 재생)은 quest_id 기준이라 **리셋 후 리허설 1회 → 본 시연** 순서로
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes" ]; then
  read -r -p "실사용 데이터를 전부 지웁니다 (KPI 시드·캐시는 보존). 계속할까요? [y/N] " answer
  [ "$answer" = "y" ] || { echo "중단했습니다"; exit 1; }
fi

exec ./.venv/bin/python backend/scripts/reset_user_data.py "$@"
