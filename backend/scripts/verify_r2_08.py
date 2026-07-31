#!/usr/bin/env python3
"""R2-08(#57) 완료 조건 검증 — 상세(계약 §4)·start 전이·409·abandon.

사용법: cd backend && python scripts/verify_r2_08.py  (backend/.env의 DATABASE_URL 사용)
검증 세션은 스스로 만들고 try/finally로 전부 지운다(연쇄 삭제).
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

CARD_KEYS = {"quest_id", "title", "activity", "mission", "route", "budget_total_krw", "score", "max_points", "revisit", "refs"}
COORDS_KEYS = {"activity", "mission", "board_stop", "alight_stop", "path"}

BASE_REQ = {
    "interests": ["사진·미디어"],
    "origin": {"zone_code": "4211056000", "stop_id": None},
    "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T18:00"},
    "max_budget_krw": None,
}


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def new_session() -> str:
    sid = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid)
    return sid


def bearer(sid: str) -> dict:
    return {"Authorization": f"Bearer {sid}"}


def is_latlng(v) -> bool:
    return isinstance(v, dict) and set(v) == {"lat", "lng"} and all(isinstance(x, float) for x in v.values())


def main() -> None:
    sid = new_session()
    rec = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid)).json()
    cards = rec["quests"] + rec["more"]
    qid = cards[0]["quest_id"]
    q_no_mission = next(c for c in cards if c["mission"] is None)["quest_id"]
    qid2 = cards[1]["quest_id"]

    # 1. 접근 제어 — 무인증 401 / 남의 세션 404 / 없는 id 404
    r1a = client.get(f"/api/quests/{qid}")
    other = new_session()
    r1b = client.get(f"/api/quests/{qid}", headers=bearer(other))
    r1c = client.get("/api/quests/q_none", headers=bearer(sid))
    check(
        "상세 접근 제어 — 401/404/404",
        r1a.status_code == 401
        and r1b.status_code == 404 and r1b.json()["error"]["code"] == "NOT_FOUND"
        and r1c.status_code == 404,
        f"{r1a.status_code}/{r1b.status_code}/{r1c.status_code}",
    )

    # 2. 상세 — 계약 §4: QuestCard 전체 + status·started_at·coords
    r2 = client.get(f"/api/quests/{qid}", headers=bearer(sid))
    d = r2.json()
    coords = d.get("coords", {})
    ok2 = (
        r2.status_code == 200
        and set(d) == CARD_KEYS | {"status", "started_at", "coords"}
        and d["status"] == "recommended"
        and d["started_at"] is None
        and set(coords) == COORDS_KEYS
        and is_latlng(coords["activity"]) and is_latlng(coords["board_stop"]) and is_latlng(coords["alight_stop"])
        and is_latlng(coords["mission"])  # qid 카드는 미션 있음
        and coords["path"] == [
            [coords["board_stop"]["lat"], coords["board_stop"]["lng"]],
            [coords["alight_stop"]["lat"], coords["alight_stop"]["lng"]],
        ]
        and d["quest_id"] == qid
    )
    check("상세 응답 — 카드+status+started_at+coords(path 포함)", ok2, r2.text[:300])

    # 3. 가게 없는 퀘스트 → coords.mission null
    r3 = client.get(f"/api/quests/{q_no_mission}", headers=bearer(sid))
    check("가게 없는 퀘스트 → coords.mission null", r3.status_code == 200 and r3.json()["coords"]["mission"] is None)

    # 4a. start 접근 제어 — 무인증 401 / 남의 세션 404 / 없는 id 404
    r4a = client.post(f"/api/quests/{qid}/start", json={})
    r4b = client.post(f"/api/quests/{qid}/start", json={}, headers=bearer(other))
    r4c = client.post("/api/quests/q_none/start", json={}, headers=bearer(sid))
    check(
        "start 접근 제어 — 401/404/404",
        r4a.status_code == 401 and r4b.status_code == 404 and r4c.status_code == 404,
        f"{r4a.status_code}/{r4b.status_code}/{r4c.status_code}",
    )

    # 4. start → 200 {status, started_at} + DB 반영 + 상세에도 반영
    r4 = client.post(f"/api/quests/{qid}/start", json={"abandon_current": False}, headers=bearer(sid))
    b4 = r4.json()
    d4 = client.get(f"/api/quests/{qid}", headers=bearer(sid)).json()
    ok4 = (
        r4.status_code == 200
        and set(b4) == {"status", "started_at"}
        and b4["status"] == "started"
        and isinstance(b4["started_at"], str)
        and d4["status"] == "started" and d4["started_at"] == b4["started_at"]
    )
    check("start → 200 + 상세 반영", ok4, r4.text)

    # 5. 같은 퀘스트 재시작 → 멱등(같은 started_at)
    r5 = client.post(f"/api/quests/{qid}/start", json={}, headers=bearer(sid))
    check("재시작 멱등 — 같은 started_at", r5.status_code == 200 and r5.json()["started_at"] == b4["started_at"], r5.text)

    # 5b. stamped 자기 재시작도 멱등 200 — 계약의 409 복구 경로 데드엔드 방지(검수 반영)
    with get_engine().begin() as conn:
        conn.execute(text("update quests set status = 'stamped' where id = :q"), {"q": qid})
    r5b = client.post(f"/api/quests/{qid}/start", json={"abandon_current": True}, headers=bearer(sid))
    with get_engine().begin() as conn:
        after5b = conn.execute(text("select status from quests where id = :q"), {"q": qid}).scalar()
        conn.execute(text("update quests set status = 'started' where id = :q"), {"q": qid})
    check(
        "stamped 자기 재시작 → 멱등 200 + 진행 안 되돌림",
        r5b.status_code == 200 and r5b.json()["started_at"] == b4["started_at"] and after5b == "stamped",
        f"{r5b.status_code}/{after5b}",
    )

    # 6. 진행 중 상태에서 다른 퀘스트 start(abandon_current=false) → 409 + current_quest_id
    r6 = client.post(f"/api/quests/{qid2}/start", json={"abandon_current": False}, headers=bearer(sid))
    e6 = r6.json().get("error", {})
    check(
        "동시 진행 → 409 QUEST_IN_PROGRESS + current_quest_id",
        r6.status_code == 409 and e6.get("code") == "QUEST_IN_PROGRESS" and e6.get("current_quest_id") == qid,
        r6.text,
    )

    # 7. abandon_current=true → 새 퀘스트 started + 기존 abandoned
    r7 = client.post(f"/api/quests/{qid2}/start", json={"abandon_current": True}, headers=bearer(sid))
    with get_engine().connect() as conn:
        old_status = conn.execute(text("select status from quests where id = :q"), {"q": qid}).scalar()
    check("abandon 재요청 → 기존 건 abandoned + 새 건 started", r7.status_code == 200 and old_status == "abandoned", f"{r7.status_code}/{old_status}")

    # 8. stamped 상태의 다른 퀘스트가 있으면 → 409 (진행 중 = started·stamped)
    with get_engine().begin() as conn:
        conn.execute(text("update quests set status = 'stamped' where id = :q"), {"q": qid2})
    r8 = client.post(f"/api/quests/{qid}/start", json={"abandon_current": False}, headers=bearer(sid))
    e8 = r8.json().get("error", {})
    check("stamped도 진행 중 취급 → 409", r8.status_code == 409 and e8.get("current_quest_id") == qid2, r8.text)

    # 9. recorded 퀘스트 start → 409 ALREADY_RECORDED
    with get_engine().begin() as conn:
        conn.execute(text("update quests set status = 'recorded' where id = :q"), {"q": qid2})
    r9 = client.post(f"/api/quests/{qid2}/start", json={}, headers=bearer(sid))
    check("완주 퀘스트 재시작 → 409 ALREADY_RECORDED", r9.status_code == 409 and r9.json()["error"]["code"] == "ALREADY_RECORDED", r9.text)

    # 10. abandoned 퀘스트 재시작 허용 (recommended와 동일 취급)
    r10 = client.post(f"/api/quests/{qid}/start", json={"abandon_current": True}, headers=bearer(sid))
    check("abandoned 퀘스트 재시작 → 200", r10.status_code == 200, r10.text)

    # 11. DB 백스톱 — 같은 세션에 진행 중 2건 강제 삽입 시 부분 유니크 인덱스가 거부
    sid_bs = new_session()
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                " board_stop_id, alight_stop_id, status, created_at) "
                "values ('q_r2_08_bs1', :s, 'rec_bs', 1, '{}', 'a_bs', 'stp_a', 'stp_b', 'started', '2026-08-01T12:00')"
            ),
            {"s": sid_bs},
        )
    blocked = False
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                    " board_stop_id, alight_stop_id, status, created_at) "
                    "values ('q_r2_08_bs2', :s, 'rec_bs', 2, '{}', 'a_bs2', 'stp_a', 'stp_b', 'stamped', '2026-08-01T12:01')"
                ),
                {"s": sid_bs},
            )
    except Exception:
        blocked = True
    check("동시 진행 2건 강제 삽입 → DB가 거부 (uq_quests_one_in_progress)", blocked)

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-08 검증 전부 통과 — #57 완료 조건 충족 (①원천 적재 후 coords 실조인 교체 예정)")


def cleanup() -> None:
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
