"""상세 coords 조인 — ①원천 실데이터(activities·merchants·bus_stops) 기반 (#9 적재 후 교체).

R4 build_quests 목(#27 착륙 전)이 만드는 가짜 id(a_mock_* 등)나 좌표 누락 행은 결정적
모의 좌표로 폴백한다 — 데모가 좌표 하나 때문에 죽지 않게. 실카드가 흐르기 시작하면
전부 실좌표 경로를 탄다.
"""
import hashlib
import logging

from sqlalchemy import select

from app.models import Activity, BusStop, Merchant

logger = logging.getLogger("bomnae")

_BASE_LAT, _BASE_LNG = 37.8813, 127.7298  # 춘천 시청 부근 — 폴백 기준점


def _fallback(ref_id: str) -> dict:
    h = int(hashlib.sha256(ref_id.encode()).hexdigest()[:8], 16)
    return {
        "lat": round(_BASE_LAT + ((h % 200) - 100) / 10000, 4),
        "lng": round(_BASE_LNG + (((h // 200) % 200) - 100) / 10000, 4),
    }


def _pick(db, stmt, ref_id: str) -> dict:
    row = db.execute(stmt).first()
    if row is None or row[0] is None or row[1] is None:
        logger.debug("coords 폴백 사용: %s", ref_id)
        return _fallback(ref_id)
    return {"lat": float(row[0]), "lng": float(row[1])}


def resolve_coords(db, card: dict) -> dict:
    """계약 §4 coords — activity·mission(null 가능)·board_stop·alight_stop·path(단순 연결)."""
    refs = card["refs"]
    activity = _pick(
        db,
        select(Activity.latitude, Activity.longitude).where(
            Activity.activity_id == refs["activity_id"]
        ),
        refs["activity_id"],
    )
    board = _pick(
        db,
        select(BusStop.latitude, BusStop.longitude).where(BusStop.stop_id == refs["board_stop_id"]),
        refs["board_stop_id"],
    )
    alight = _pick(
        db,
        select(BusStop.latitude, BusStop.longitude).where(
            BusStop.stop_id == refs["alight_stop_id"]
        ),
        refs["alight_stop_id"],
    )
    mission = card.get("mission")
    mission_coords = (
        _pick(
            db,
            select(Merchant.latitude, Merchant.longitude).where(
                Merchant.merchant_id == mission["merchant_id"]
            ),
            mission["merchant_id"],
        )
        if mission
        else None
    )
    return {
        "activity": activity,
        "mission": mission_coords,
        "board_stop": board,
        "alight_stop": alight,
        "path": [[board["lat"], board["lng"]], [alight["lat"], alight["lng"]]],  # 버스 구간 단순 연결
    }
