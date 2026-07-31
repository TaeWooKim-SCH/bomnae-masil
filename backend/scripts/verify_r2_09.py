#!/usr/bin/env python3
"""R2-09(#34) 완료 조건 검증 — verify 3방식·멱등·포인트·에러 케이스.

사용법: cd backend && python scripts/verify_r2_09.py  (backend/.env의 DATABASE_URL 사용)
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
from app.core.merchant_codes import derived_code as merchant_code  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []

RESPONSE_KEYS = {"stamp_type", "already", "points_added", "balance", "title_unlocked", "message"}

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


def bearer(sid: str) -> dict:
    return {"Authorization": f"Bearer {sid}"}


def setup_started_quest(with_mission: bool = True) -> tuple[str, str, dict]:
    """새 세션 + 추천 + 시작까지. (session_id, quest_id, card) 반환."""
    sid = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid)
    rec = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid)).json()
    cards = rec["quests"] + rec["more"]
    card = next(c for c in cards if (c["mission"] is not None) == with_mission)
    client.post(f"/api/quests/{card['quest_id']}/start", json={}, headers=bearer(sid))
    return sid, card["quest_id"], card


def main() -> None:
    sid, qid, card = setup_started_quest()
    mid = card["mission"]["merchant_id"]
    good_code = merchant_code(mid)
    bad_code = f"{(int(good_code) + 1) % 10000:04d}"

    # 1. 전제·접근 제어 — 무인증 401 / recommended 상태 400 QUEST_NOT_STARTED / 없는 id 404
    sid_r = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid_r)
    rec_r = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid_r)).json()
    q_rec = rec_r["quests"][0]["quest_id"]
    r1a = client.post(f"/api/quests/{qid}/verify", json={"method": "code", "code": good_code})
    r1b = client.post(f"/api/quests/{q_rec}/verify", json={"method": "code", "code": good_code}, headers=bearer(sid_r))
    r1c = client.post("/api/quests/q_none/verify", json={"method": "code", "code": good_code}, headers=bearer(sid))
    check(
        "전제 — 401 / QUEST_NOT_STARTED / 404",
        r1a.status_code == 401
        and r1b.status_code == 400 and r1b.json()["error"]["code"] == "QUEST_NOT_STARTED"
        and r1c.status_code == 404,
        f"{r1a.status_code}/{r1b.status_code}/{r1c.status_code}",
    )

    # 2. 틀린 코드 → 400 INVALID_CODE (재시도 무제한 — 연속 3회도 같은 응답)
    ok2 = all(
        (r := client.post(f"/api/quests/{qid}/verify", json={"method": "code", "code": bad_code}, headers=bearer(sid))).status_code == 400
        and r.json()["error"]["code"] == "INVALID_CODE"
        for _ in range(3)
    )
    check("틀린 코드 → 400 INVALID_CODE (락아웃 없음)", ok2)

    # 3. qr 다른 가게 → 400 WRONG_STORE + 가게 이름 문구
    r3 = client.post(
        f"/api/quests/{qid}/verify",
        json={"method": "qr", "merchant_id": "m_other", "code": good_code},
        headers=bearer(sid),
    )
    e3 = r3.json().get("error", {})
    check(
        "다른 가게 QR → 400 WRONG_STORE + '미션 가게는 ○○예요'",
        r3.status_code == 400 and e3.get("code") == "WRONG_STORE"
        and card["mission"]["merchant_name"] in e3.get("message", ""),
        r3.text,
    )

    # 4. code 방식 성공 → 200 계약 형식 + visit + 40점 + stamped 전이 + 원장 1행
    r4 = client.post(f"/api/quests/{qid}/verify", json={"method": "code", "code": good_code}, headers=bearer(sid))
    b4 = r4.json()
    with get_engine().connect() as conn:
        row = conn.execute(
            text("select stamp_type, amount_krw, merchant_id from stamps where quest_id = :q"), {"q": qid}
        ).first()
        status = conn.execute(text("select status from quests where id = :q"), {"q": qid}).scalar()
        ledger = conn.execute(
            text("select count(*), coalesce(sum(delta),0) from point_ledger where session_id = :s"), {"s": sid}
        ).first()
    ok4 = (
        r4.status_code == 200
        and set(b4) == RESPONSE_KEYS
        and b4["stamp_type"] == "visit" and b4["already"] is False
        and b4["points_added"] == 40 and b4["balance"] == 40
        and b4["title_unlocked"] is None and b4["message"] == "스탬프가 적립됐어요!"
        and row is not None and row[0] == "visit" and row[1] is None and row[2] == mid
        and status == "stamped" and ledger[0] == 1 and ledger[1] == 40
    )
    check("코드 성공 → 200 계약 형식 + visit + stamped + 원장 40", ok4, r4.text)

    # 5. 재인증(다른 방식 receipt여도) → 성공 톤 멱등 + 중복 적립 없음 + 타입은 기존 유지
    r5 = client.post(f"/api/quests/{qid}/verify", json={"method": "receipt", "amount_krw": 8500}, headers=bearer(sid))
    b5 = r5.json()
    with get_engine().connect() as conn:
        n_stamps = conn.execute(text("select count(*) from stamps where quest_id = :q"), {"q": qid}).scalar()
        bal = conn.execute(text("select coalesce(sum(delta),0) from point_ledger where session_id = :s"), {"s": sid}).scalar()
    ok5 = (
        r5.status_code == 200
        and b5["already"] is True and b5["points_added"] == 0 and b5["balance"] == 40
        and b5["stamp_type"] == "visit" and b5["title_unlocked"] is None
        and b5["message"] == "이미 적립된 퀘스트예요"
        and n_stamps == 1 and bal == 40
    )
    check("재인증 → 멱등 성공 톤 + 중복 적립 없음", ok5, r5.text)

    # 6. qr 정상 (새 퀘스트) → visit
    sid6, qid6, card6 = setup_started_quest()
    mid6 = card6["mission"]["merchant_id"]
    r6 = client.post(
        f"/api/quests/{qid6}/verify",
        json={"method": "qr", "merchant_id": mid6, "code": merchant_code(mid6)},
        headers=bearer(sid6),
    )
    check("QR 성공 → visit (코드와 같은 대조 경로)", r6.status_code == 200 and r6.json()["stamp_type"] == "visit", r6.text)

    # 7. receipt — 범위 검증 + spend 저장(금액 기록)
    sid7, qid7, _ = setup_started_quest()
    bad_amounts = [999, 200_001]
    ok7a = all(
        (r := client.post(f"/api/quests/{qid7}/verify", json={"method": "receipt", "amount_krw": a}, headers=bearer(sid7))).status_code == 400
        and r.json()["error"]["code"] == "INVALID_AMOUNT"
        for a in bad_amounts
    )
    r7 = client.post(f"/api/quests/{qid7}/verify", json={"method": "receipt", "amount_krw": 1000}, headers=bearer(sid7))
    with get_engine().connect() as conn:
        row7 = conn.execute(text("select stamp_type, amount_krw from stamps where quest_id = :q"), {"q": qid7}).first()
    check(
        "영수증 — 999·200001 거절 + 1000 경계 통과 + spend·금액 저장",
        ok7a and r7.status_code == 200 and r7.json()["stamp_type"] == "spend"
        and row7 is not None and row7[0] == "spend" and row7[1] == 1000,
        r7.text,
    )

    # 8. 가게 없는 퀘스트 → 400 NO_MISSION (3방식 공통)
    sid8, qid8, _ = setup_started_quest(with_mission=False)
    r8 = client.post(f"/api/quests/{qid8}/verify", json={"method": "receipt", "amount_krw": 5000}, headers=bearer(sid8))
    check("가게 없는 퀘스트 → 400 NO_MISSION", r8.status_code == 400 and r8.json()["error"]["code"] == "NO_MISSION", r8.text)

    # 9. 방식별 필수 필드 누락 → 400 VALIDATION
    ok9 = all(
        (r := client.post(f"/api/quests/{qid7}/verify", json=b, headers=bearer(sid7))).status_code == 400
        and r.json()["error"]["code"] == "VALIDATION"
        for b in [{"method": "qr", "code": "1234"}, {"method": "code"}, {"method": "receipt"}, {"method": "ocr"}]
    )
    check("필수 필드 누락·미정의 method → 400 VALIDATION", ok9)

    # 10. 칭호 해금 — 60점 보유 상태에서 +40 → 100 도달 "봄내 첫걸음"
    sid10, qid10, card10 = setup_started_quest()
    with get_engine().begin() as conn:
        conn.execute(
            text("insert into point_ledger (session_id, quest_id, delta, reason, created_at) values (:s, :q, 60, 'record', '2026-08-01T13:00')"),
            {"s": sid10, "q": qid10},
        )
    r10 = client.post(
        f"/api/quests/{qid10}/verify",
        json={"method": "code", "code": merchant_code(card10["mission"]["merchant_id"])},
        headers=bearer(sid10),
    )
    b10 = r10.json()
    check(
        "100점 도달 → title_unlocked '봄내 첫걸음' + balance 100",
        r10.status_code == 200 and b10["balance"] == 100 and b10["title_unlocked"] == "봄내 첫걸음",
        r10.text,
    )

    # 11. 사진 미저장 — stamps 컬럼에 사진·파일 계열 없음 + 요청 모델에 파일 필드 없음(구조 확인)
    with get_engine().connect() as conn:
        cols = set(
            conn.execute(
                text("select column_name from information_schema.columns where table_name='stamps'")
            ).scalars()
        )
    check(
        "사진 미저장 — stamps 컬럼 7개뿐(id·소유·가게·방식·금액·시각 — 사진·파일 계열 없음)",
        cols == {"id", "session_id", "quest_id", "merchant_id", "stamp_type", "amount_krw", "created_at"},
        str(cols),
    )

    # 12. 동시 인증 경합 — 멱등 선확인 통과 직후 승자가 먼저 커밋해도 패자는 500이 아니라 200 already
    #     (검수 재현 기법: 스탬프 생성 시각을 읽는 순간 승자 스탬프를 다른 커넥션으로 주입)
    sid12, qid12, card12 = setup_started_quest()
    import app.routers.verify as verify_mod  # noqa: PLC0415

    real_now = verify_mod.now_kst
    injected = {"done": False}

    def hooked_now():
        if not injected["done"]:
            injected["done"] = True
            with get_engine().begin() as conn:
                conn.execute(
                    text(
                        "insert into stamps (session_id, quest_id, merchant_id, stamp_type, created_at) "
                        "values (:s, :q, :m, 'visit', '2026-08-01T14:00')"
                    ),
                    {"s": sid12, "q": qid12, "m": card12["mission"]["merchant_id"]},
                )
        return real_now()

    verify_mod.now_kst = hooked_now
    try:
        r12 = client.post(
            f"/api/quests/{qid12}/verify",
            json={"method": "code", "code": merchant_code(card12["mission"]["merchant_id"])},
            headers=bearer(sid12),
        )
    finally:
        verify_mod.now_kst = real_now
    b12 = r12.json()
    with get_engine().connect() as conn:
        n12 = conn.execute(text("select count(*) from stamps where quest_id = :q"), {"q": qid12}).scalar()
    check(
        "동시 인증 경합 — 패자도 200 already (스탬프 1장 유지)",
        r12.status_code == 200 and b12.get("already") is True and b12.get("points_added") == 0 and n12 == 1,
        r12.text,
    )

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-09 검증 전부 통과 — #34 완료 조건 충족 (배포 curl·#20 인쇄물 왕복은 시드 후)")


def cleanup() -> None:
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
