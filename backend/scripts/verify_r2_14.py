#!/usr/bin/env python3
"""폴백 스위치 최종 점검 드라이버 (#42) — CACHE_ONLY·DEMO_NOW 하에서 데모 시나리오 전 구간 주행.

사용법:
  cd backend && python scripts/verify_r2_14.py                     # 로컬 앱(TestClient) — CACHE_ONLY=1·DEMO_NOW 고정 강제
  cd backend && python scripts/verify_r2_14.py http://localhost:8000   # 떠 있는 서버(오프라인 스택·배포) 대상
                                                                       # (서버의 CACHE_ONLY·DEMO_NOW 설정을 그대로 따름)

시나리오: health → 세션 → 추천 → 상세 → 시작 → 인증(코드) → 기록 생성(폴백) → 워밍 재생 확인
         → 저장 → 보관함 → 대시보드 3종 → 세션 삭제(원상 복구). 전 구간 2xx·500 0건이 통과 기준.
"""
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

DEMO_NOW_VALUE = "2026-08-01T14:00"  # 데모 대본 기준 시각 (8.1 토 14:00 — 10-architecture 8장)

fails: list[str] = []
statuses: list[int] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def build_client(base_url: str | None):
    if base_url:
        import httpx

        print(f"대상: {base_url} (서버 설정의 CACHE_ONLY·DEMO_NOW 그대로)")
        return httpx.Client(base_url=base_url, timeout=30), False
    # 로컬 모드 — 스위치를 직접 켜고 점검한다
    os.environ["CACHE_ONLY"] = "1"
    os.environ["DEMO_NOW"] = DEMO_NOW_VALUE
    from fastapi.testclient import TestClient

    from app.main import app

    print(f"대상: 로컬 앱 (CACHE_ONLY=1 · DEMO_NOW={DEMO_NOW_VALUE} 강제)")
    return TestClient(app, raise_server_exceptions=False), True


def req(client, method: str, path: str, **kw):
    r = getattr(client, method)(path, **kw)
    statuses.append(r.status_code)
    return r


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else None
    client, local_mode = build_client(base_url)

    # 1. health — 깨우기 겸 DEMO_NOW 확인
    r = req(client, "get", "/api/health")
    body = r.json()
    check("health 200 + db true", r.status_code == 200 and body.get("db") is True, r.text)
    if local_mode:
        check("DEMO_NOW 고정 반영", body.get("demo_now") == "2026-08-01T14:00:00", str(body))
    else:
        print(f"  · demo_now = {body.get('demo_now')} (대본 기준 {DEMO_NOW_VALUE}인지 육안 확인)")

    # 2. 세션 → 추천 (외부 호출 없는 구간 — CACHE_ONLY에서도 그대로 돌아야 정상)
    sid = req(client, "post", "/api/sessions", json={"nickname": "점검봇", "age_confirmed": True}).json()["session_id"]
    auth = {"Authorization": f"Bearer {sid}"}
    rec = req(
        client, "post", "/api/quests/recommend",
        json={
            "interests": ["사진·미디어", "문화·공연"],
            "origin": {"zone_code": "4211056000", "stop_id": None},
            "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T18:00"},
            "max_budget_krw": 30000,
        },
        headers=auth,
    )
    cards = rec.json().get("quests", []) + rec.json().get("more", [])
    mission_card = next((c for c in cards if c["mission"]), None)
    check("추천 200 + 카드 1장 이상(빈 화면 0)", rec.status_code == 200 and len(cards) >= 1 and mission_card is not None, rec.text[:200])

    qid = mission_card["quest_id"]

    # 3. 상세(버스 정보 포함) → 시작
    detail = req(client, "get", f"/api/quests/{qid}", headers=auth)
    check("상세 200 + coords·버스 필드", detail.status_code == 200 and "coords" in detail.json() and detail.json()["route"]["stops_count"] is not None, detail.text[:150])
    start = req(client, "post", f"/api/quests/{qid}/start", json={}, headers=auth)
    check("시작 200", start.status_code == 200, start.text)

    # 4. 인증 — 코드 대조는 DB만 쓴다(외부 호출 없음)
    from app.core.merchant_codes import derived_code  # 목 가게 코드 유도(시드 후엔 실코드로 바꿔 입력)

    verify = req(
        client, "post", f"/api/quests/{qid}/verify",
        json={"method": "code", "code": derived_code(mission_card["mission"]["merchant_id"])},
        headers=auth,
    )
    check("인증 200 + 적립 40", verify.status_code == 200 and verify.json().get("balance", 0) >= 40, verify.text)

    # 5. 기록 생성 — CACHE_ONLY 미스면 템플릿 200 (500 절대 금지 구간)
    gen_body = {"quest_id": qid, "action": "generate", "purpose": "hobby", "answers": ["새로웠어요", "", ""], "attempt": 0}
    gen = req(client, "post", "/api/records", json=gen_body, headers=auth)
    check(
        "기록 생성 200 (캐시 재생 또는 템플릿 — 죽지 않음)",
        gen.status_code == 200 and "draft" in gen.json(),
        gen.text[:200],
    )
    if local_mode:
        check("CACHE_ONLY 미스 → from_template true", gen.json().get("from_template") is True, gen.text[:150])
        # 5b. 워밍 메커니즘 — 온라인(CACHE_ONLY=0)에서 생성해 캐시를 채우고, 차단 후 재생되는지
        os.environ["CACHE_ONLY"] = "0"
        warm = req(client, "post", "/api/records", json={**gen_body, "attempt": 1}, headers=auth)
        os.environ["CACHE_ONLY"] = "1"
        replay = req(client, "post", "/api/records", json={**gen_body, "attempt": 1}, headers=auth)
        check(
            "워밍 → 차단 후 같은 초안 재생 (본 시연 폴백 경로)",
            warm.status_code == 200 and replay.status_code == 200
            and replay.json()["from_template"] is False
            and replay.json()["draft"] == warm.json()["draft"],
            replay.text[:150],
        )

    # 6. 저장 → 보관함
    save = req(
        client, "post", "/api/records",
        json={**gen_body, "action": "save", "final": gen.json()["draft"]},
        headers=auth,
    )
    check("저장 201 + 완주 100점", save.status_code == 201 and save.json().get("balance") == 100, save.text)
    listing = req(client, "get", "/api/records", headers=auth)
    check("보관함 200 + 칭호", listing.status_code == 200 and listing.json().get("titles") == ["봄내 첫걸음"], listing.text[:150])

    # 7. 대시보드 3종 (인증 불필요)
    ok_dash = all(req(client, "get", f"/api/dashboard/{p}").status_code == 200 for p in ("accessibility", "inflow", "kpi"))
    check("대시보드 3종 200", ok_dash)

    # 8. 원상 복구 — 점검 세션 삭제
    done = req(client, "delete", f"/api/sessions/{sid}", headers=auth)
    check("점검 세션 삭제 204 (원상 복구)", done.status_code == 204, done.text)

    n500 = sum(1 for s in statuses if s >= 500)
    check(f"전 구간 {len(statuses)}요청 — 500 오류 0건", n500 == 0, f"500 {n500}건")

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("폴백 예행 전부 통과 — 남은 것은 리허설 항목(배포 CACHE_ONLY 재시작·콜드스타트 측정·오프라인 녹화)")
    if local_mode:
        print("주의: 이 프로세스의 CACHE_ONLY·DEMO_NOW는 스크립트 안에서만 켰습니다 — 서버 환경변수 원상 확인은 별도")


if __name__ == "__main__":
    main()
