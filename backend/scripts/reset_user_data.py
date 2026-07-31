#!/usr/bin/env python3
"""시연 전 사용자 데이터 리셋 (#51) — scripts/reset_user_data.sh가 부른다.

지움: sessions 전체(연쇄: quests·stamps·records·point_ledger) + kpi_events 실사용분(seed=false)
보존: KPI 시드(seed=true — #50, 리셋 후에도 대시보드가 시뮬레이션 숫자 유지),
     api_cache(LLM 폴백 자산 — #42 인터넷 장애 대비), ①원천·②사전계산 전부

--demo-seed: 리셋 후 조각지도 시연용 세션(#99 4단계 — 완주 5~8동 채움)을 만들고 session_id 출력.
            발표 기기 localStorage의 session_id에 넣으면 보관함·조각지도가 채워진 상태로 시작.
"""
import secrets
import sys
from datetime import timedelta
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

    if "--demo-seed" in sys.argv:
        demo_seed(engine)


def demo_seed(engine) -> None:
    """조각지도 데모 시드(#99) — 서로 다른 동의 완주 기록 6건 + 포인트(기록 40+완주 20)씩."""
    with engine.connect() as conn:
        zones = conn.execute(
            text(
                "select a.zone_code, min(a.activity_id), coalesce(min(r.zone_name), a.zone_code) "
                "from activities a left join resident_population r on r.zone_code = a.zone_code "
                "where a.zone_code is not null group by a.zone_code order by a.zone_code limit 6"
            )
        ).fetchall()
    if len(zones) < 5:
        print(f"⚠ 조각 시드 생략 — activities.zone_code 백필이 {len(zones)}동뿐(5동 필요). R3 백필 후 재실행")
        return
    from app.timebase import now_kst  # 기준 시각 유틸(규칙 6) — DEMO_NOW를 켠 기기에서도 전부 '과거' 기록이 된다

    base = now_kst().replace(minute=0, second=0, microsecond=0)
    sid = f"ses_demo_{secrets.token_hex(4)}"
    with engine.begin() as conn:
        conn.execute(
            text("insert into sessions (id, nickname, age_confirmed, created_at) values (:s, '봄내마실러', true, :t)"),
            {"s": sid, "t": base - timedelta(hours=7)},
        )
        for i, (zone, aid, zname) in enumerate(zones):
            qid = f"q_demo_{secrets.token_hex(4)}"
            at = base - timedelta(hours=6 - i)  # 6~1시간 전 — 시연 중 저장하는 실기록이 항상 맨 위
            conn.execute(
                text(
                    "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                    " board_stop_id, alight_stop_id, status, started_at, created_at) "
                    "values (:q, :s, 'rec_demo_seed', 1, '{}', :a, 'stp_seed', 'stp_seed', 'recorded', :t, :t)"
                ),
                {"q": qid, "s": sid, "a": aid, "t": at},
            )
            conn.execute(
                text(
                    "insert into records (id, session_id, quest_id, purpose, answers, title, body, tags, verified, created_at) "
                    "values (:r, :s, :q, 'hobby', '[\"좋았어요\",\"\",\"\"]', :ti, '동네 곳곳을 다니며 채운 기록', '[\"조각지도\"]', false, :t)"
                ),
                {"r": f"rec_demo_{secrets.token_hex(4)}", "s": sid, "q": qid, "ti": f"{zname} 마실 기록", "t": at},
            )
            for delta, reason in ((40, "record"), (20, "completion_bonus")):
                conn.execute(
                    text("insert into point_ledger (session_id, quest_id, delta, reason, created_at) values (:s, :q, :d, :re, :t)"),
                    {"s": sid, "q": qid, "d": delta, "re": reason, "t": at},
                )
    print(f"✓ 조각 시드 완료 — {len(zones)}동 완주, session_id = {sid}")
    print("  발표 기기 브라우저 localStorage의 session_id에 위 값을 넣으면 채워진 보관함으로 시작")
    print("  (주의: 시드 퀘스트의 상세 화면은 카드가 비어 있음 — 대본은 보관함·조각지도만 열 것)")


if __name__ == "__main__":
    main()
