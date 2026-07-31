#!/usr/bin/env python3
"""시연 전 사용자 데이터 리셋 (#51) — scripts/reset_user_data.sh가 부른다.

지움: sessions 전체(연쇄: quests·stamps·records·point_ledger) + kpi_events 실사용분(seed=false)
보존: KPI 시드(seed=true — #50, 리셋 후에도 대시보드가 시뮬레이션 숫자 유지),
     api_cache(LLM 폴백 자산 — #42 인터넷 장애 대비), ①원천·②사전계산 전부
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402

USER_TABLES = ("sessions", "quests", "stamps", "records", "point_ledger")


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        before = {t: conn.execute(text(f"select count(*) from {t}")).scalar() for t in USER_TABLES}  # noqa: S608
        events_user = conn.execute(text("select count(*) from kpi_events where not seed")).scalar()
        cache_before = conn.execute(text("select count(*) from api_cache")).scalar()

    with engine.begin() as conn:
        conn.execute(text("delete from sessions"))  # 연쇄: quests·stamps·records·point_ledger
        conn.execute(text("delete from kpi_events where not seed"))

    with engine.connect() as conn:
        after = {t: conn.execute(text(f"select count(*) from {t}")).scalar() for t in USER_TABLES}  # noqa: S608
        seeds = conn.execute(text("select count(*) from kpi_events where seed")).scalar()
        cache_after = conn.execute(text("select count(*) from api_cache")).scalar()

    print(f"삭제: 세션 {before['sessions']}건 + 하위 연쇄, KPI 실사용 이벤트 {events_user}건")
    leftovers = {t: n for t, n in after.items() if n}
    if leftovers:  # point_ledger 포함 5테이블 전부 0이어야 한다(#51 확정 1)
        print(f"✗ 잔여 행 발견: {leftovers}")
        sys.exit(1)
    print(f"✓ 사용자 5테이블(point_ledger 포함) 전부 0행")
    print(f"✓ KPI 시드 보존: {seeds}건" + (" — ⚠ 시드 없음: #50 시드 스크립트를 실행하세요(대시보드가 '—'로 보임)" if seeds == 0 else ""))
    if cache_after != cache_before:
        print(f"✗ api_cache가 변했습니다: {cache_before} → {cache_after}")
        sys.exit(1)
    print(f"✓ api_cache(LLM 폴백 자산) 보존: {cache_after}건")
    print("리셋 완료 — 초기 상태")


if __name__ == "__main__":
    main()
