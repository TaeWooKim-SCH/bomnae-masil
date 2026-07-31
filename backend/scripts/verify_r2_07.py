#!/usr/bin/env python3
"""R2-07(#25) 완료 조건 검증 — 계약 §3 형식·스냅샷 저장·more 소진·완화 200.

사용법: cd backend && python scripts/verify_r2_07.py  (backend/.env의 DATABASE_URL 사용)
검증 세션은 스스로 만들고 try/finally로 전부 지운다(연쇄 삭제로 스냅샷도 정리).
"""
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers._quest_builder_mock import MOCK_ACTIVITY_IDS  # noqa: E402

T0 = datetime(2026, 8, 1, 12, 0, 0)  # 고정 리터럴 — 규칙 6
client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []

CARD_KEYS = {"quest_id", "title", "activity", "mission", "route", "budget_total_krw", "score", "max_points", "revisit", "refs"}
ROUTE_KEYS = {"board_stop_name", "route_no", "stops_count", "ride_min", "walk_min", "no_transfer", "basis_note"}
BREAKDOWN_KEYS = {"market", "interest", "access", "time", "budget"}

BASE_REQ = {
    "interests": ["사진·미디어", "문화·공연"],
    "origin": {"zone_code": "4211056000", "stop_id": None},
    "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T18:00"},
    "max_budget_krw": 30000,
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


def main() -> None:
    sid = new_session()

    # 1. 인증 없음 → 401
    r1 = client.post("/api/quests/recommend", json=BASE_REQ)
    check("인증 없음 → 401 SESSION_NOT_FOUND", r1.status_code == 401 and r1.json()["error"]["code"] == "SESSION_NOT_FOUND", r1.text)

    # 2. 입력 검증 — 관심사 0·4개·enum 밖·중복, 예산 밖 → 400 VALIDATION
    bad_inputs = [
        {**BASE_REQ, "interests": []},
        {**BASE_REQ, "interests": ["운동·건강", "문화·공연", "공예·만들기", "사진·미디어"]},
        {**BASE_REQ, "interests": ["청소년·진로"]},
        {**BASE_REQ, "interests": ["문화·공연", "문화·공연"]},
        {**BASE_REQ, "max_budget_krw": 20000},
    ]
    ok2 = all(
        (r := client.post("/api/quests/recommend", json=b, headers=bearer(sid))).status_code == 400
        and r.json()["error"]["code"] == "VALIDATION"
        for b in bad_inputs
    )
    check("잘못된 입력 5종 → 400 VALIDATION", ok2)

    # 3. 시간 창 59분 → 400 INVALID_TIME_WINDOW
    r3 = client.post(
        "/api/quests/recommend",
        json={**BASE_REQ, "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T14:59"}},
        headers=bearer(sid),
    )
    check("59분 창 → 400 INVALID_TIME_WINDOW", r3.status_code == 400 and r3.json()["error"]["code"] == "INVALID_TIME_WINDOW", r3.text)

    # 3b. 경계: 정확히 60분 → 200 ("최소 60분" 포함 경계)
    r3b = client.post(
        "/api/quests/recommend",
        json={**BASE_REQ, "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T15:00"}},
        headers=bearer(sid),
    )
    check("정확히 60분 창 → 200", r3b.status_code == 200, r3b.text[:150])

    # 3c. 오프셋 입력(+09:00·Z) — 브라우저 toISOString()은 Z를 붙인다 → 나이브 KST로 정규화되어 통과
    r3c = client.post(
        "/api/quests/recommend",
        json={**BASE_REQ, "time_window": {"start": "2026-08-01T14:00:00+09:00", "end": "2026-08-01T18:00:00+09:00"}},
        headers=bearer(sid),
    )
    r3z = client.post(
        "/api/quests/recommend",
        json={**BASE_REQ, "time_window": {"start": "2026-08-01T05:00:00Z", "end": "2026-08-01T09:00:00Z"}},
        headers=bearer(sid),
    )
    check("오프셋(+09:00·Z) 입력 → 200", r3c.status_code == 200 and r3z.status_code == 200, f"{r3c.status_code}/{r3z.status_code}")

    # 4. 정상 호출 → 계약 §3 형식
    r4 = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid))
    body = r4.json()
    all_cards = body.get("quests", []) + body.get("more", [])
    ok4 = (
        r4.status_code == 200
        and set(body) == {"recommendation_id", "quests", "more", "relaxed"}
        and 1 <= len(body["quests"]) <= 3
        and len(body["more"]) <= 3
        and body["relaxed"] is None
        and all(set(c) == CARD_KEYS for c in all_cards)
        and all(set(c["route"]) == ROUTE_KEYS for c in all_cards)  # 배차·시각표·실시간 필드 없음
        and all(set(c["score"]["breakdown"]) == BREAKDOWN_KEYS for c in all_cards)
        and all(c["max_points"] == (60 if c["mission"] is None else 100) for c in all_cards)
        and [c["score"]["total"] for c in all_cards] == sorted((c["score"]["total"] for c in all_cards), reverse=True)
        and all(c["budget_total_krw"] <= 30000 for c in all_cards)  # 하드 필터 3(예산 내)
        and all(
            c["route"]["basis_note"] == f"{c['route']['board_stop_name']} 정류장 기준" for c in all_cards
        )  # stop_id 미선택 → 카드별 승차 정류장 기준 표기
    )
    check("정상 응답 — 4필드·카드 형식·점수 내림차순·예산 내·basis_note", ok4, r4.text[:300])

    # 5. 스냅샷 저장 — 1~6위 전부 quests 테이블, rank 순서, refs 컬럼 일치, quest_id 재조회
    rec_id = body["recommendation_id"]
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("select id, rank, activity_id, board_stop_id, alight_stop_id, status, card from quests where recommendation_id = :r order by rank"),
            {"r": rec_id},
        ).mappings().all()
    ok5 = (
        len(rows) == len(all_cards)
        and [row["rank"] for row in rows] == list(range(1, len(all_cards) + 1))
        and all(row["status"] == "recommended" for row in rows)
        and all(row["id"] == c["quest_id"] and row["card"]["quest_id"] == c["quest_id"] for row, c in zip(rows, all_cards))
        and all(
            row["activity_id"] == c["refs"]["activity_id"]
            and row["board_stop_id"] == c["refs"]["board_stop_id"]
            and row["alight_stop_id"] == c["refs"]["alight_stop_id"]
            for row, c in zip(rows, all_cards)
        )
    )
    check("스냅샷 저장 — 전 카드·rank·refs 컬럼·재조회", ok5, f"rows={len(rows)} cards={len(all_cards)}")

    # 6. stop_id 선택 시 basis_note null
    r6 = client.post(
        "/api/quests/recommend",
        json={**BASE_REQ, "origin": {"zone_code": "4211056000", "stop_id": "stp_1041"}},
        headers=bearer(sid),
    )
    cards6 = r6.json()["quests"] + r6.json()["more"]
    check("정류장 직접 선택 → basis_note null", r6.status_code == 200 and all(c["route"]["basis_note"] is None for c in cards6))

    # 7. 예산 0(무료만) → more 소진(빈 배열) 케이스
    r7 = client.post("/api/quests/recommend", json={**BASE_REQ, "max_budget_krw": 0}, headers=bearer(sid))
    b7 = r7.json()
    ok7 = (
        r7.status_code == 200
        and b7["more"] == []
        and len(b7["quests"]) >= 1
        and all(c["activity"]["price_krw"] == 0 and c["mission"] is None for c in b7["quests"])
    )
    check("예산 0 → 무료 카드만 + more 소진([])", ok7, r7.text[:200])

    # 8. 전 활동 기시작 → 완화(revisit) 거쳐 200 (후보 0 상황에서도 500 없음)
    sid2 = new_session()
    with get_engine().begin() as conn:
        for i, aid in enumerate(MOCK_ACTIVITY_IDS):
            conn.execute(
                text(
                    "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                    " merchant_id, board_stop_id, alight_stop_id, status, started_at, created_at) "
                    "values (:q, :s, 'rec_r2_07_seed', :rk, '{}', :a, null, 'stp_x', 'stp_y', 'recorded', :t, :t)"
                ),
                {"q": f"q_r2_07_seed_{i}", "s": sid2, "rk": i + 1, "a": aid, "t": T0},
            )
    r8 = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid2))
    b8 = r8.json()
    cards8 = b8.get("quests", []) + b8.get("more", [])
    ok8 = (
        r8.status_code == 200
        and b8["relaxed"] is not None
        and b8["relaxed"]["steps"] == ["revisit"]
        and b8["relaxed"]["message"] == "조건을 조금 넓혀 찾았어요"
        and len(cards8) >= 1
        and all(c["revisit"] for c in cards8)
    )
    check("전 활동 기시작 → 완화(revisit) 200 + 뱃지", ok8, r8.text[:200])

    # 9. 필터⑤ 부분 제외 — 일부만 시작한 활동은 응답에서 빠짐
    sid3 = new_session()
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                " merchant_id, board_stop_id, alight_stop_id, status, started_at, created_at) "
                "values ('q_r2_07_seed_p', :s, 'rec_r2_07_seed2', 1, '{}', :a, null, 'stp_x', 'stp_y', 'started', :t, :t)"
            ),
            {"s": sid3, "a": MOCK_ACTIVITY_IDS[0], "t": T0},
        )
    r9 = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid3))
    ids9 = [c["refs"]["activity_id"] for c in r9.json()["quests"] + r9.json()["more"]]
    check("필터⑤ — 기시작 활동 제외됨", r9.status_code == 200 and MOCK_ACTIVITY_IDS[0] not in ids9, str(ids9))

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-07 검증 전부 통과 — #25 완료 조건 충족 (배포 curl·R1 목 대조는 머지 후)")


def cleanup() -> None:
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
