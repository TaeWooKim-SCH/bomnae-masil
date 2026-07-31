#!/usr/bin/env python3
"""R2-12(#36) 완료 조건 검증 — geo 무가공 서빙·KPI 동결 산식·세션 삭제 절연.

사용법: cd backend && python scripts/verify_r2_12.py  (backend/.env의 DATABASE_URL 사용)
검증이 만든 것(세션·kpi 이벤트·geo 샘플)만 지운다 — 기존 이벤트·R3 geo 데이터 무접촉.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.core.merchant_codes import derived_code  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
fails: list[str] = []
created: list[str] = []
geo_test_names: list[str] = []
id0: int | None = None  # 시작 시점 kpi_events 최대 id — 스냅샷 전 실패 시 아무것도 안 지운다
lock_conn = None  # advisory lock 보유 커넥션 — 동시 실행 차단(공유 DB에서 id 범위 정리의 전제)

KPI_KEYS = {"conversion_pct", "low_inflow_pct", "median_search_min", "feasibility_pct", "spend_total_krw", "seed_included"}

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


def kpi() -> dict:
    return client.get("/api/dashboard/kpi").json()


def main() -> None:
    global id0, lock_conn
    engine = get_engine()
    # 동시 실행 차단 — cleanup의 id 범위 삭제는 "이 스크립트 혼자 쓴다"가 전제(검수 반영).
    # 리허설·팀원 트래픽과 겹치면 그쪽 이벤트가 같이 지워지므로 조용한 시간에 돌릴 것
    lock_conn = engine.connect()
    if not lock_conn.execute(text("select pg_try_advisory_lock(721236)")).scalar():
        print("✗ 다른 검증 인스턴스가 실행 중입니다 — 중단")
        sys.exit(1)
    with engine.connect() as conn:
        id0 = conn.execute(text("select coalesce(max(id), 0) from kpi_events")).scalar()
        n_before = conn.execute(text("select count(*) from kpi_events")).scalar()
        geo_before = conn.execute(text("select count(*) from dashboard_geo")).scalar()
        # KPI 시드(#50)가 이미 적재돼 있으면 seed_included는 항상 true — 5번 검증이 이를 존중
        seed_preexists = conn.execute(
            text("select 1 from kpi_events where seed = true limit 1")
        ).first() is not None

    # 1. geo — 미적재면 빈 FeatureCollection(무인증), 적재분은 가공 없이 그대로
    if geo_before == 0:
        r1a = client.get("/api/dashboard/accessibility")
        check(
            "geo 미적재 → 빈 FeatureCollection (죽지 않음)",
            r1a.status_code == 200 and r1a.json() == {"type": "FeatureCollection", "features": []},
            r1a.text[:120],
        )
    sample_acc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[127.7, 37.8], [127.8, 37.8], [127.8, 37.9], [127.7, 37.8]]]},
                      "properties": {"zone_code": "4211056000", "name": "석사동", "score": 71.2, "quintile": 2}}],
    }
    sample_inflow = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.7269, 37.8801]},
                      "properties": {"name": "육림고개 카페", "category": "카페", "inflow_status": "확정저유입"}}],
    }
    import json as _json
    with engine.begin() as conn:
        for name, payload in (("accessibility", sample_acc), ("inflow", sample_inflow)):
            exists = conn.execute(text("select 1 from dashboard_geo where name = :n"), {"n": name}).first()
            if not exists:  # R3 실데이터가 있으면 건드리지 않고 그대로 대조
                conn.execute(
                    text("insert into dashboard_geo (name, geojson) values (:n, :g)"),
                    {"n": name, "g": _json.dumps(payload, ensure_ascii=False)},
                )
                geo_test_names.append(name)
    r1b = client.get("/api/dashboard/accessibility").json()
    r1c = client.get("/api/dashboard/inflow").json()
    with engine.connect() as conn:
        db_acc = conn.execute(text("select geojson from dashboard_geo where name='accessibility'")).scalar()
        db_inf = conn.execute(text("select geojson from dashboard_geo where name='inflow'")).scalar()
    check("geo 2레이어 — DB 원본과 응답 동일(가공 없음)", r1b == db_acc and r1c == db_inf)

    # 2. KPI 기준선 — 표가 비어 있으면 분모 0 규칙(null·—)과 형식 확인
    k0 = kpi()
    check("kpi 응답 — 계약 §6 필드 6종 정확", set(k0) == KPI_KEYS, str(k0))
    if n_before == 0:
        check(
            "빈 표 → 분모 0은 null(—), feasibility 100, spend 0, seed false",
            k0["conversion_pct"] is None and k0["low_inflow_pct"] is None
            and k0["median_search_min"] is None and k0["feasibility_pct"] == 100
            and k0["spend_total_krw"] == 0 and k0["seed_included"] is False,
            str(k0),
        )

    # 3. 플로우 — 수기 계산과 대조 (기존 이벤트 위 델타로 검증하기 위해 분자·분모를 직접 센다)
    def counts() -> dict:
        with engine.connect() as conn:
            return {
                "started_m": conn.execute(text("select count(*) from kpi_events where event_type='quest_started' and has_mission")).scalar(),
                "stamped": conn.execute(text("select count(*) from kpi_events where event_type='quest_stamped'")).scalar(),
                "exp_all": conn.execute(text("select count(*) from kpi_events where event_type='card_exposed'")).scalar(),
                "exp_m": conn.execute(text("select count(*) from kpi_events where event_type='card_exposed' and has_mission")).scalar(),
                "spend": conn.execute(text("select coalesce(sum(amount_krw),0) from kpi_events where event_type='quest_stamped' and stamp_type='spend'")).scalar(),
                "firsts": conn.execute(text("select count(*) from kpi_events where event_type='first_start'")).scalar(),
            }

    c0 = counts()
    sid = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid)
    rec = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid)).json()
    cards = rec["quests"] + rec["more"]
    mission_cards = [c for c in cards if c["mission"]]
    c1 = counts()
    check(
        "추천 → 노출 이벤트 (전 카드 + 미션 구분)",
        c1["exp_all"] - c0["exp_all"] == len(cards) and c1["exp_m"] - c0["exp_m"] == len(mission_cards),
        f"{c1['exp_all']-c0['exp_all']}/{len(cards)}",
    )

    qid = mission_cards[0]["quest_id"]
    client.post(f"/api/quests/{qid}/start", json={}, headers=bearer(sid))
    client.post(f"/api/quests/{qid}/start", json={}, headers=bearer(sid))  # 멱등 재시작 — 중복 집계 금지
    c2 = counts()
    check(
        "시작 → started+first_start 각 1 (멱등 재시작 중복 없음)",
        c2["started_m"] - c1["started_m"] == 1 and c2["firsts"] - c1["firsts"] == 1,
        str(c2),
    )

    r_stamp = client.post(
        f"/api/quests/{qid}/verify",
        json={"method": "code", "code": derived_code(mission_cards[0]["mission"]["merchant_id"])},
        headers=bearer(sid),
    )
    client.post(  # 재인증 멱등 — 이벤트 중복 금지
        f"/api/quests/{qid}/verify",
        json={"method": "code", "code": derived_code(mission_cards[0]["mission"]["merchant_id"])},
        headers=bearer(sid),
    )
    c3 = counts()
    check("인증 → stamped 1 (멱등 재인증 중복 없음)", r_stamp.status_code == 200 and c3["stamped"] - c2["stamped"] == 1)

    # 두 번째 세션 — 영수증(spend) 경로
    sid2 = client.post("/api/sessions", json={"age_confirmed": True}).json()["session_id"]
    created.append(sid2)
    rec2 = client.post("/api/quests/recommend", json=BASE_REQ, headers=bearer(sid2)).json()
    m2 = next(c for c in rec2["quests"] + rec2["more"] if c["mission"])
    client.post(f"/api/quests/{m2['quest_id']}/start", json={}, headers=bearer(sid2))
    client.post(f"/api/quests/{m2['quest_id']}/verify", json={"method": "receipt", "amount_krw": 8500}, headers=bearer(sid2))
    c4 = counts()

    # 4. kpi 값 = 동결 산식 수기 계산과 일치 (전체 표 기준 분자·분모로 검산)
    k = kpi()
    expected_conv = round(c4["stamped"] / c4["started_m"] * 100, 1) if c4["started_m"] else None
    check(
        "kpi — 전환율·spend 합계가 산식 수기 계산과 일치",
        k["conversion_pct"] == expected_conv
        and k["spend_total_krw"] == int(c4["spend"])
        and c4["spend"] - c3["spend"] == 8500
        and k["feasibility_pct"] == 100.0
        and isinstance(k["median_search_min"], float),
        f"{k} vs conv={expected_conv}",
    )

    # 5. seed 플래그
    with engine.begin() as conn:
        conn.execute(text("insert into kpi_events (event_type, seed, occurred_at) values ('quest_started', true, '2026-08-01T12:00')"))
    seed_on = kpi()["seed_included"]
    with engine.begin() as conn:
        conn.execute(text("delete from kpi_events where seed = true and id > :i"), {"i": id0})
    # 기존 시드(#50)가 있으면 제거 후에도 true가 맞다 — 시드 적재 후 재실행에도 유효한 단언(검수 반영)
    check(
        "seed 이벤트 → seed_included true (자기 것 제거 후 기존 시드 여부대로)",
        seed_on is True and kpi()["seed_included"] is seed_preexists,
    )

    # 6. 세션 삭제 절연 — 익명 집계는 유지 ("개인 식별이 불가능한 통계는 유지됩니다")
    k_before = kpi()
    for s in list(created):
        client.delete(f"/api/sessions/{s}", headers=bearer(s))
    k_after = kpi()
    check("세션 전체 삭제 후에도 KPI 불변 (익명 절연)", k_before == k_after, f"{k_before} vs {k_after}")

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-12 검증 전부 통과 — #36 완료 조건 충족 (R1 화면 결합·실 GeoJSON은 #33·#37)")


def cleanup() -> None:
    with get_engine().begin() as conn:
        for s in created:
            conn.execute(text("delete from sessions where id = :s"), {"s": s})
        if id0 is not None:  # 스냅샷 전 실패면 이벤트는 건드리지 않는다
            conn.execute(text("delete from kpi_events where id > :i"), {"i": id0})
        for n in geo_test_names:
            conn.execute(text("delete from dashboard_geo where name = :n"), {"n": n})
    if lock_conn is not None:
        lock_conn.execute(text("select pg_advisory_unlock(721236)"))
        lock_conn.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
