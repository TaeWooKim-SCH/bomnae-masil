#!/usr/bin/env python3
"""R2-15(#99) 완료 조건 검증 — zone_map 파생·중복 없음·available·수집 칭호.

사용법: cd backend && python scripts/verify_r2_15.py  (backend/.env의 DATABASE_URL 사용)
임시 활동(a_zone_test_*)을 심어 검증하고 try/finally로 전부 지운다(세션은 연쇄 삭제).
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []

TEST_ZONES = [f"421105{i}000" for i in range(1, 7)]  # 임시 6동


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def bearer(sid: str) -> dict:
    return {"Authorization": f"Bearer {sid}"}


def seed_recorded_quest(conn, sid: str, n: int, zone_idx: int) -> None:
    conn.execute(
        text(
            "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
            " board_stop_id, alight_stop_id, status, started_at, created_at) "
            "values (:q, :s, 'rec_zone_test', 1, '{}', :a, 'stp_z', 'stp_z', 'recorded', '2026-08-01T10:00', '2026-08-01T10:00')"
        ),
        {"q": f"q_zone_test_{n}", "s": sid, "a": f"a_zone_test_{zone_idx}"},
    )


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for i, z in enumerate(TEST_ZONES, 1):
            conn.execute(
                text(
                    "insert into activities (activity_id, source_event_id, name, type, start_date, end_date, "
                    " price_unknown, venue_name, needs_geocode, source_url, zone_code) "
                    "values (:a, :a, :n, '상시형', '2026-08-01', '2026-12-31', false, :n, false, 'https://test', :z)"
                ),
                {"a": f"a_zone_test_{i}", "n": f"조각검증활동{i}", "z": z},
            )
        available_expected = conn.execute(
            text("select count(distinct zone_code) from activities where zone_code is not null")
        ).scalar()

    sid = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid)

    # 1. 완주 0건 → collected 빈 배열 + zone_map 형식(계약 §5)
    r1 = client.get("/api/records", headers=bearer(sid)).json()
    zm1 = r1.get("zone_map", {})
    check(
        "zone_map 형식 — collected []·available = 활동 보유 동 수",
        set(r1) == {"records", "balance", "titles", "zone_map"}
        and set(zm1) == {"collected", "available"}
        and zm1["collected"] == [] and len(zm1["available"]) == available_expected
        and all(z in zm1["available"] for z in TEST_ZONES),
        str(zm1)[:200],
    )

    # 2. 서로 다른 동 완주 2건 → collected 2
    with engine.begin() as conn:
        seed_recorded_quest(conn, sid, 1, 1)
        seed_recorded_quest(conn, sid, 2, 2)
    zm2 = client.get("/api/records", headers=bearer(sid)).json()["zone_map"]
    check("서로 다른 동 완주 2건 → collected 2", sorted(zm2["collected"]) == sorted(TEST_ZONES[:2]), str(zm2["collected"]))

    # 3. 같은 동 재완주 → collected 불변 (중복 없음)
    with engine.begin() as conn:
        seed_recorded_quest(conn, sid, 3, 1)
    zm3 = client.get("/api/records", headers=bearer(sid)).json()["zone_map"]
    check("같은 동 재완주 → collected 불변", sorted(zm3["collected"]) == sorted(TEST_ZONES[:2]), str(zm3["collected"]))

    # 4. recorded 아닌 상태(started)는 미집계
    with engine.begin() as conn:
        conn.execute(
            text(
                "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                " board_stop_id, alight_stop_id, status, started_at, created_at) "
                "values ('q_zone_test_s', :s, 'rec_zone_test', 1, '{}', 'a_zone_test_3', 'stp_z', 'stp_z', 'started', '2026-08-01T10:00', '2026-08-01T10:00')"
            ),
            {"s": sid},
        )
    zm4 = client.get("/api/records", headers=bearer(sid)).json()["zone_map"]
    check("완주 전(started) 활동은 미집계", len(zm4["collected"]) == 2)

    # 5. 5동 도달 → titles에 「동네 수집가」 합류 (포인트 칭호와 공존)
    with engine.begin() as conn:
        for n, zi in ((4, 3), (5, 4), (6, 5)):
            seed_recorded_quest(conn, sid, n, zi)
    r5 = client.get("/api/records", headers=bearer(sid)).json()
    check(
        "5동 도달 → 「동네 수집가」 titles 합류",
        len(r5["zone_map"]["collected"]) == 5 and "동네 수집가" in r5["titles"] and "골목 탐험가" not in r5["titles"],
        str(r5["titles"]),
    )

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-15 검증 전부 통과 — #99 서버 몫 충족 (available 실데이터는 R3 zone_code 백필 후)")


def cleanup() -> None:
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})
        conn.execute(text("delete from activities where activity_id like 'a_zone_test_%'"))


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
