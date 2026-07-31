#!/usr/bin/env python3
"""R2-06(#24) 완료 조건 검증 — 세션 생성·인증·연쇄 삭제·개인정보 무컬럼.

사용법: cd backend && python scripts/verify_r2_06.py  (backend/.env의 DATABASE_URL 사용)
TestClient로 실제 앱·실제 DB를 관통한다. 검증 세션은 스스로 만들었다 전부 지운다.
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

T0 = datetime(2026, 8, 1, 14, 0, 0)  # 고정 리터럴 — 규칙 6
client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def bearer(sid: str) -> dict:
    return {"Authorization": f"Bearer {sid}"}


def main() -> None:
    # 1. age 미확인(false·누락 둘 다) → 400 AGE_NOT_CONFIRMED
    r1 = client.post("/api/sessions", json={"age_confirmed": False})
    r1b = client.post("/api/sessions", json={"nickname": "봄내"})
    check(
        "age 미확인 → 400 AGE_NOT_CONFIRMED",
        r1.status_code == 400 and r1.json()["error"]["code"] == "AGE_NOT_CONFIRMED"
        and r1b.status_code == 400 and r1b.json()["error"]["code"] == "AGE_NOT_CONFIRMED",
        r1.text,
    )

    # 2. 생성 → 201 {session_id, balance:0} (계약 §1 — 필드 정확히 두 개)
    r2 = client.post("/api/sessions", json={"nickname": "봄내마실러", "age_confirmed": True})
    body = r2.json() if r2.status_code == 201 else {}
    sid = body.get("session_id", "")
    if sid:
        created.append(sid)
    check(
        "생성 → 201 {session_id, balance:0}",
        r2.status_code == 201 and set(body) == {"session_id", "balance"}
        and body["balance"] == 0 and sid.startswith("ses_"),
        r2.text,
    )

    # 3. 닉네임 13자 → 400 VALIDATION
    r3 = client.post("/api/sessions", json={"nickname": "가" * 13, "age_confirmed": True})
    if r3.status_code == 201:  # 회귀로 통과해 버려도 잔재는 남기지 않는다
        created.append(r3.json().get("session_id", ""))
    check("닉네임 12자 초과 → 400 VALIDATION", r3.status_code == 400 and r3.json()["error"]["code"] == "VALIDATION", r3.text)

    # 4. 위조 토큰(존재하지 않는 id) → 401 SESSION_NOT_FOUND
    r4 = client.delete("/api/sessions/ses_forged0000000000", headers=bearer("ses_forged0000000000"))
    check("위조 토큰 → 401 SESSION_NOT_FOUND", r4.status_code == 401 and r4.json()["error"]["code"] == "SESSION_NOT_FOUND", r4.text)

    # 5. 헤더 없음 → 401
    r5 = client.delete(f"/api/sessions/{sid}")
    check("헤더 없음 → 401", r5.status_code == 401 and r5.json()["error"]["code"] == "SESSION_NOT_FOUND", r5.text)

    # 6. 남의 세션 삭제 시도 → 404 NOT_FOUND (401은 로컬 키 폐기 신호라 살아있는 세션에 금지)
    r6c = client.post("/api/sessions", json={"age_confirmed": True})
    other = r6c.json().get("session_id", "")
    if other:
        created.append(other)
    r6 = client.delete(f"/api/sessions/{sid}", headers=bearer(other))
    check(
        "남의 세션 삭제 시도 → 404 NOT_FOUND",
        r6.status_code == 404 and r6.json()["error"]["code"] == "NOT_FOUND",
        r6.text,
    )

    # 6b. 소문자 bearer 스킴도 인증 성공 (RFC 7235 — 스킴 대소문자 무관)
    r6b = client.delete(f"/api/sessions/{sid}", headers={"Authorization": f"bearer {other}"})
    check("소문자 bearer 스킴 인식 (404 = 인증은 통과)", r6b.status_code == 404, r6b.text)

    # 7. 연쇄 삭제 — 하위 4종을 심고 세션 DELETE → 204 + 전부 0행
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "insert into quests (id, session_id, recommendation_id, rank, card, activity_id, "
                " merchant_id, board_stop_id, alight_stop_id, status, started_at, created_at) "
                "values ('q_r2_06_verify', :s, 'rec_r2_06', 1, '{}', 'a_v', 'm_v', 'stp_a', 'stp_b', 'started', :t, :t)"
            ),
            {"s": sid, "t": T0},
        )
        conn.execute(
            text("insert into stamps (session_id, quest_id, merchant_id, stamp_type, created_at) values (:s, 'q_r2_06_verify', 'm_v', 'visit', :t)"),
            {"s": sid, "t": T0},
        )
        conn.execute(
            text(
                "insert into records (id, session_id, quest_id, purpose, answers, title, body, tags, verified, created_at) "
                "values ('rec_r2_06_verify', :s, 'q_r2_06_verify', 'hobby', '[]', '검증', '본문', '[]', true, :t)"
            ),
            {"s": sid, "t": T0},
        )
        conn.execute(
            text("insert into point_ledger (session_id, quest_id, delta, reason, created_at) values (:s, 'q_r2_06_verify', 40, 'stamp', :t)"),
            {"s": sid, "t": T0},
        )
    r7 = client.delete(f"/api/sessions/{sid}", headers=bearer(sid))
    with get_engine().connect() as conn:
        leftovers = {
            t: conn.execute(text(f"select count(*) from {t} where session_id = :s"), {"s": sid}).scalar()  # noqa: S608
            for t in ("quests", "stamps", "records", "point_ledger")
        }
        gone = conn.execute(text("select count(*) from sessions where id = :s"), {"s": sid}).scalar()
    check(
        "삭제 → 204 + 하위 4종(point_ledger 포함) 연쇄 삭제",
        r7.status_code == 204 and gone == 0 and not any(leftovers.values()),
        f"{r7.status_code} leftovers={leftovers}",
    )

    # 8. 삭제된 세션의 토큰 → 401 (세션 무효 복구 신호)
    r8 = client.delete(f"/api/sessions/{sid}", headers=bearer(sid))
    check("삭제된 세션 토큰 → 401", r8.status_code == 401 and r8.json()["error"]["code"] == "SESSION_NOT_FOUND", r8.text)

    # 9. 개인정보 컬럼 없음 — sessions 컬럼이 정확히 4개
    with get_engine().connect() as conn:
        cols = set(
            conn.execute(
                text("select column_name from information_schema.columns where table_schema='public' and table_name='sessions'")
            ).scalars()
        )
    check("개인정보 컬럼 없음 (id·nickname·age_confirmed·created_at 뿐)", cols == {"id", "nickname", "age_confirmed", "created_at"}, str(cols))

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-06 검증 전부 통과 — #24 완료 조건 충족 (배포 서버 curl은 머지·재배포 후)")


def cleanup() -> None:
    """중간 예외에도 실DB에 잔재를 남기지 않는다 — 세션 삭제가 하위를 연쇄 정리."""
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})
        # 고정 id 하위 행 방어적 정리 (이전 실행이 세션 삭제 직전에 죽었을 때 대비)
        conn.execute(text("delete from records where id = 'rec_r2_06_verify'"))
        conn.execute(text("delete from quests where id = 'q_r2_06_verify'"))


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
