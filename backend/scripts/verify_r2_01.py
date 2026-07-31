#!/usr/bin/env python3
"""R2-01(#4) 완료 조건 검증 — 접속·PostGIS·테이블 생성·연쇄 삭제를 한 번에 확인한다.

사용법:
  cd backend
  cp .env.example .env        # DATABASE_URL에 실제 Session pooler URI 입력(팀 비밀 저장소)
  pip install -r requirements.txt
  python scripts/verify_r2_01.py

검사 항목:
  1. DB 접속 성공 (Session pooler URI)
  2. PostGIS 활성화 — select postgis_version()
  3. ③사용자 테이블 5종 + api_cache 생성 (이미 있으면 통과)
  4. sessions 행 삭제 시 quests·stamps·records·point_ledger 연쇄 삭제(CASCADE)

여러 번 실행해도 안전하다(검증 데이터는 ses_r2_01_verify 계열만 쓰고 시작·종료 시 정리).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.models import Base  # noqa: E402

# 고정 리터럴 시각 — 규칙 6(now() 금지). 검증 데이터라 실제 시각이 필요 없다.
T0 = datetime(2026, 8, 1, 14, 0, 0)

SES = "ses_r2_01_verify"
USER_TABLES = ("quests", "stamps", "records", "point_ledger")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    sys.exit(1)


def main() -> None:
    load_dotenv(BACKEND_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url or "<PROJECT_ID>" in url:
        fail("DATABASE_URL이 없습니다 — backend/.env에 실제 Session pooler URI를 넣어주세요")
    host = url.split("@")[-1]
    if ".supabase.co" in host and "pooler.supabase.com" not in host:
        print("  ⚠ Direct connection 주소로 보입니다 — Session pooler URI를 쓰세요 (#4 함정 항목)")

    engine = create_engine(url)

    # 1. 접속
    with engine.connect() as conn:
        conn.execute(text("select 1"))
    print("  ✓ 1. DB 접속 성공")

    # 2. PostGIS
    with engine.begin() as conn:
        conn.execute(text("create extension if not exists postgis"))
        ver = conn.execute(text("select postgis_version()")).scalar()
    print(f"  ✓ 2. PostGIS 활성화 — {ver}")

    # 3. 테이블 생성
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        names = set(
            conn.execute(
                text("select tablename from pg_tables where schemaname = 'public'")
            ).scalars()
        )
    expected = {"sessions", "api_cache", *USER_TABLES}
    missing = expected - names
    if missing:
        fail(f"3. 테이블 누락: {sorted(missing)}")
    print(f"  ✓ 3. 테이블 생성 확인 — {sorted(expected)}")

    # 4. CASCADE — 세션 1건 + 하위 4종을 넣고 세션만 지워 전부 사라지는지 본다
    with engine.begin() as conn:
        conn.execute(text("delete from sessions where id = :s"), {"s": SES})  # 이전 실행 잔재 정리
        conn.execute(
            text(
                "insert into sessions (id, nickname, age_confirmed, created_at) "
                "values (:s, '검증봇', true, :t)"
            ),
            {"s": SES, "t": T0},
        )
        conn.execute(
            text(
                "insert into quests (id, session_id, recommendation_id, rank, card, "
                " activity_id, merchant_id, board_stop_id, alight_stop_id, status, started_at, created_at) "
                "values ('q_r2_01_verify', :s, 'rec_r2_01_verify', 1, '{}', "
                " 'a_verify', 'm_verify', 'stp_a', 'stp_b', 'started', :t, :t)"
            ),
            {"s": SES, "t": T0},
        )
        conn.execute(
            text(
                "insert into stamps (session_id, quest_id, merchant_id, stamp_type, amount_krw, created_at) "
                "values (:s, 'q_r2_01_verify', 'm_verify', 'spend', 8500, :t)"
            ),
            {"s": SES, "t": T0},
        )
        conn.execute(
            text(
                "insert into records (id, session_id, quest_id, purpose, answers, title, body, tags, verified, created_at) "
                "values ('rec_r2_01_verify', :s, 'q_r2_01_verify', 'hobby', '[\"새로웠어요\",\"\",\"\"]', "
                " '검증', '검증 본문', '[\"검증\"]', true, :t)"
            ),
            {"s": SES, "t": T0},
        )
        conn.execute(
            text(
                "insert into point_ledger (session_id, quest_id, delta, reason, created_at) "
                "values (:s, 'q_r2_01_verify', 40, 'stamp', :t)"
            ),
            {"s": SES, "t": T0},
        )

    with engine.begin() as conn:
        conn.execute(text("delete from sessions where id = :s"), {"s": SES})

    with engine.connect() as conn:
        leftovers = {
            t: conn.execute(
                text(f"select count(*) from {t} where session_id = :s"), {"s": SES}  # noqa: S608 — t는 고정 목록
            ).scalar()
            for t in USER_TABLES
        }
    bad = {t: n for t, n in leftovers.items() if n}
    if bad:
        fail(f"4. 연쇄 삭제 실패 — 남은 행: {bad}")
    print("  ✓ 4. 세션 삭제 → 하위 4종 연쇄 삭제(CASCADE) 확인")

    print("\nR2-01 검증 전부 통과 — #4 완료 조건 충족")


if __name__ == "__main__":
    main()
