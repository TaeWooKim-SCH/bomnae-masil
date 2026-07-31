#!/usr/bin/env python3
"""R2-10(#35) 완료 조건 검증 — generate/save 2단계·캐시·개인정보 필터·실패 사다리·보관함.

사용법: cd backend && python scripts/verify_r2_10.py  (backend/.env의 DATABASE_URL 사용)
- 검증 세션·캐시는 스스로 만든 것만 지운다(연쇄 삭제 + 퀘스트별 캐시 키 스코프 삭제 —
  리허설 워밍 캐시는 건드리지 않는다)
- LLM 호출 횟수는 records 모듈의 함수를 계수 래퍼로 감싸 센다 — R4 #38 착륙 후에도 유효
"""
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.routers.records as records_mod  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers._merchant_codes_mock import merchant_code  # noqa: E402
from app.routers.records import LLM_TIMEOUT_SECONDS, build_llm_payload  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []
created_qids: list[str] = []

REAL_GEN = records_mod.generate_record_draft
COUNTER = {"n": 0}

SAVE_KEYS = {"record_id", "points_added", "completion_bonus", "balance", "title_unlocked", "verified"}
LIST_ITEM_KEYS = {"record_id", "quest_id", "title", "tags", "created_at", "verified"}

BASE_REQ = {
    "interests": ["사진·미디어"],
    "origin": {"zone_code": "4211056000", "stop_id": None},
    "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T18:00"},
    "max_budget_krw": None,
}
ANSWERS = ["새로웠어요", "", ""]
FINAL = {"title": "나의 기록", "body": "본문입니다", "tags": ["춘천", "기록"]}


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def bearer(sid: str) -> dict:
    return {"Authorization": f"Bearer {sid}"}


def setup_started_quest(with_mission: bool = True) -> tuple[str, str, dict]:
    sid = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid)
    rec = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid)).json()
    cards = rec["quests"] + rec["more"]
    created_qids.extend(c["quest_id"] for c in cards)
    card = next(c for c in cards if (c["mission"] is not None) == with_mission)
    client.post(f"/api/quests/{card['quest_id']}/start", json={}, headers=bearer(sid))
    return sid, card["quest_id"], card


def gen_req(qid: str, answers=None, attempt: int = 0) -> dict:
    return {"quest_id": qid, "action": "generate", "purpose": "hobby", "answers": answers or ANSWERS, "attempt": attempt}


def save_req(qid: str, answers=None, final=None) -> dict:
    return {"quest_id": qid, "action": "save", "purpose": "hobby", "answers": answers or ANSWERS, "final": final or FINAL}


def main() -> None:
    import os

    os.environ["CACHE_ONLY"] = "0"

    def counted(payload):  # LLM 호출 계수 래퍼 — 어떤 구현(목·R4)이든 센다
        COUNTER["n"] += 1
        return REAL_GEN(payload)

    records_mod.generate_record_draft = counted

    sid, qid, card = setup_started_quest()

    # 1. 전제 — 무인증 401 / recommended QUEST_NOT_STARTED / 없는 id 404
    sid_r = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid_r)
    rec_r = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid_r)).json()
    created_qids.extend(c["quest_id"] for c in rec_r["quests"] + rec_r["more"])
    q_rec = rec_r["quests"][0]["quest_id"]
    r1a = client.post("/api/records", json=gen_req(qid))
    r1b = client.post("/api/records", json=gen_req(q_rec), headers=bearer(sid_r))
    r1c = client.post("/api/records", json=gen_req("q_none"), headers=bearer(sid))
    check(
        "전제 — 401 / QUEST_NOT_STARTED / 404",
        r1a.status_code == 401
        and r1b.status_code == 400 and r1b.json()["error"]["code"] == "QUEST_NOT_STARTED"
        and r1c.status_code == 404,
        f"{r1a.status_code}/{r1b.status_code}/{r1c.status_code}",
    )

    # 2. generate → 200 {draft{title,body,tags}, from_template:false} + body 300~500자
    n0 = COUNTER["n"]
    r2 = client.post("/api/records", json=gen_req(qid), headers=bearer(sid))
    b2 = r2.json()
    check(
        "generate → 200 계약 형식(본문 300~500자) + LLM 경로",
        r2.status_code == 200 and set(b2) == {"draft", "from_template"}
        and set(b2["draft"]) == {"title", "body", "tags"} and b2["from_template"] is False
        and 300 <= len(b2["draft"]["body"]) <= 500
        and COUNTER["n"] == n0 + 1,
        r2.text[:200],
    )

    # 3. 같은 answers 재요청 → LLM 호출 0회(캐시 재생) + 같은 초안
    r3 = client.post("/api/records", json=gen_req(qid), headers=bearer(sid))
    check(
        "같은 입력 2회 → LLM 1회(캐시 재생) + 동일 초안",
        r3.status_code == 200 and COUNTER["n"] == n0 + 1 and r3.json()["draft"] == b2["draft"]
        and r3.json()["from_template"] is False,
        r3.text[:200],
    )

    # 4. attempt 변경 → 다른 키 = 새 호출 / attempt 3 → INVALID_ATTEMPT
    r4 = client.post("/api/records", json=gen_req(qid, attempt=1), headers=bearer(sid))
    r4b = client.post("/api/records", json=gen_req(qid, attempt=3), headers=bearer(sid))
    check(
        "attempt 1 → 새 호출 / attempt 3 → 400 INVALID_ATTEMPT",
        r4.status_code == 200 and COUNTER["n"] == n0 + 2
        and r4b.status_code == 400 and r4b.json()["error"]["code"] == "INVALID_ATTEMPT",
        f"{r4.status_code}/{r4b.status_code}",
    )

    # 5. CACHE_ONLY=1 + 빈 캐시 → 호출 0회 + 템플릿 200 (실패 사다리 최종)
    os.environ["CACHE_ONLY"] = "1"
    r5 = client.post("/api/records", json=gen_req(qid, answers=["처음 보는 답변", "", ""]), headers=bearer(sid))
    r5b = client.post("/api/records", json=gen_req(qid), headers=bearer(sid))  # 캐시 있는 건 재생
    os.environ["CACHE_ONLY"] = "0"
    check(
        "CACHE_ONLY=1 — 미스는 템플릿 200(호출 0) / 히트는 캐시 재생",
        r5.status_code == 200 and r5.json()["from_template"] is True and COUNTER["n"] == n0 + 2
        and r5b.status_code == 200 and r5b.json()["from_template"] is False
        and r5b.json()["draft"] == b2["draft"],
        f"{r5.text[:120]} / {r5b.status_code}",
    )

    # 6. LLM 예외 → 템플릿 200 / 타임아웃 → 템플릿 200 + **벽시계 보장**(0.2초 제한, 1초 지연 주입)
    def boom(payload):
        raise RuntimeError("LLM down")

    try:
        records_mod.generate_record_draft = boom
        r6a = client.post("/api/records", json=gen_req(qid, answers=["예외 케이스", "", ""]), headers=bearer(sid))
    finally:
        records_mod.generate_record_draft = counted

    def slow(payload):
        time.sleep(1.0)
        return REAL_GEN(payload)

    try:
        records_mod.generate_record_draft = slow
        records_mod.LLM_TIMEOUT_SECONDS = 0.2
        t0 = time.monotonic()
        r6b = client.post("/api/records", json=gen_req(qid, answers=["타임아웃 케이스", "", ""]), headers=bearer(sid))
        elapsed = time.monotonic() - t0
    finally:
        records_mod.generate_record_draft = counted
        records_mod.LLM_TIMEOUT_SECONDS = LLM_TIMEOUT_SECONDS
    check(
        "LLM 예외·타임아웃 → 템플릿 200 + 타임아웃이 벽시계로 지켜짐",
        r6a.status_code == 200 and r6a.json()["from_template"] is True
        and r6b.status_code == 200 and r6b.json()["from_template"] is True
        and elapsed < 0.8,  # 1초 지연 주입에도 0.2초 제한이 실제로 끊는다
        f"{r6a.status_code}/{r6b.status_code}/elapsed={elapsed:.2f}s",
    )

    # 7. 개인정보 필터 — 페이로드에 세션ID·닉네임·퀘스트ID 없음 (테스트로 고정)
    payload = build_llm_payload(card, "hobby", ANSWERS)
    dumped = json.dumps(payload, ensure_ascii=False)
    check(
        "LLM 페이로드 — 세션ID·닉네임·퀘스트ID 미포함",
        sid not in dumped and qid not in dumped
        and not any(k in payload for k in ("session_id", "nickname", "quest_id"))
        and set(payload) == {"activity_name", "activity_type", "place_name", "merchant_name", "purpose", "answers"},
        dumped,
    )

    # 8. 입력 검증 — answers 2개/201자/purpose 밖 + final 오염(태그 비문자열·빈 제목) → 400 VALIDATION
    bad = [
        gen_req(qid, answers=["a", ""]),
        gen_req(qid, answers=["가" * 201, "", ""]),
        {**gen_req(qid), "purpose": "diary"},
        save_req(qid, final={"title": " ", "body": "본문", "tags": ["a"]}),
        save_req(qid, final={"title": "제목", "body": "본문", "tags": [1, None]}),
        save_req(qid, final={"title": "제목", "body": "가" * 2001, "tags": ["a"]}),
    ]
    ok8 = all(
        (r := client.post("/api/records", json=b, headers=bearer(sid))).status_code == 400
        and r.json()["error"]["code"] == "VALIDATION"
        for b in bad
    )
    check("answers·purpose·final 검증 6형 → 400 VALIDATION", ok8)

    # 9. save (스탬프 보유) → 201 {40+20, verified:true} + recorded 전이 + 재저장 409
    client.post(
        f"/api/quests/{qid}/verify",
        json={"method": "code", "code": merchant_code(card["mission"]["merchant_id"])},
        headers=bearer(sid),
    )  # 스탬프 +40
    r9 = client.post("/api/records", json=save_req(qid), headers=bearer(sid))
    b9 = r9.json()
    with get_engine().connect() as conn:
        status9 = conn.execute(text("select status from quests where id = :q"), {"q": qid}).scalar()
    r9b = client.post("/api/records", json=save_req(qid), headers=bearer(sid))
    check(
        "save → 201 (40+20, balance 100, 칭호, verified) + recorded + 재저장 409",
        r9.status_code == 201 and set(b9) == SAVE_KEYS
        and b9["points_added"] == 40 and b9["completion_bonus"] == 20
        and b9["balance"] == 100 and b9["title_unlocked"] == "봄내 첫걸음"
        and b9["verified"] is True and status9 == "recorded"
        and r9b.status_code == 409 and r9b.json()["error"]["code"] == "ALREADY_RECORDED",
        r9.text,
    )

    # 10. 빈 answers 저장 → 저장은 되지만 적립 0 (40·20 모두)
    sid10, qid10, _ = setup_started_quest()
    r10 = client.post("/api/records", json=save_req(qid10, answers=["", "", ""]), headers=bearer(sid10))
    b10 = r10.json()
    check(
        "빈 문답 저장 → 201 + 적립 0·보너스 0",
        r10.status_code == 201 and b10["points_added"] == 0 and b10["completion_bonus"] == 0
        and b10["balance"] == 0 and b10["verified"] is False,
        r10.text,
    )

    # 11. 가게 없는 퀘스트 — 기록만으로 완주 보너스 (40+20=60), verified false
    sid11, qid11, _ = setup_started_quest(with_mission=False)
    r11 = client.post("/api/records", json=save_req(qid11), headers=bearer(sid11))
    b11 = r11.json()
    check(
        "가게 없는 퀘스트 → 기록만으로 40+20 (합 60), verified false",
        r11.status_code == 201 and b11["points_added"] == 40 and b11["completion_bonus"] == 20
        and b11["balance"] == 60 and b11["verified"] is False,
        r11.text,
    )

    # 12. 보관함 — 계약 형식·소유분만·balance·titles
    r12 = client.get("/api/records", headers=bearer(sid))
    b12 = r12.json()
    r12b = client.get("/api/records", headers=bearer(sid10))
    check(
        "보관함 — 형식·소유 분리·balance·titles",
        r12.status_code == 200 and set(b12) == {"records", "balance", "titles"}
        and len(b12["records"]) == 1 and set(b12["records"][0]) == LIST_ITEM_KEYS
        and b12["records"][0]["verified"] is True and b12["balance"] == 100
        and b12["titles"] == ["봄내 첫걸음"]
        and len(r12b.json()["records"]) == 1 and r12b.json()["balance"] == 0
        and r12b.json()["titles"] == [],
        r12.text[:300],
    )

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-10 검증 전부 통과 — #35 완료 조건 충족 (배포 curl은 머지 후, 프롬프트·문구는 #38)")


def cleanup() -> None:
    records_mod.generate_record_draft = REAL_GEN
    records_mod.LLM_TIMEOUT_SECONDS = LLM_TIMEOUT_SECONDS
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})
        # 캐시는 이 실행이 만든 퀘스트의 키만 스코프 삭제 — 리허설 워밍 캐시 보호
        for q in created_qids:
            conn.execute(
                text("delete from api_cache where cache_key like 'record:' || :q || ':%'"), {"q": q}
            )


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
