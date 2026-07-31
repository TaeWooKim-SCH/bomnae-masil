"""출발지 참조 라우터 — 계약 §2 (인증 불필요).

- GET /zones: 무환승 경로를 보유한 행정동만, 가나다순 — 원천은 R3 점수표(zone_code)와
  resident_population(zone_name). 점수표가 비면 빈 배열(화면은 안내만 뜨고 죽지 않는다)
- GET /stops?zone=: 그 동에서 무환승 경로가 있는 승차 정류장, 가나다순.
  양방향 정류장(같은 이름, 다른 stop_id)은 이름당 1개만 — 화면 혼란 방지, 점수 차는 미미
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.db import get_db
from app.models import AccessibilityScore, BusStop, ResidentPopulation

router = APIRouter(tags=["refs"])


@router.get("/zones")
def zones(db=Depends(get_db)):
    rows = db.execute(
        select(AccessibilityScore.zone_code, ResidentPopulation.zone_name)
        .join(ResidentPopulation, ResidentPopulation.zone_code == AccessibilityScore.zone_code)
        .where(AccessibilityScore.no_transfer, AccessibilityScore.zone_code.is_not(None))
        .group_by(AccessibilityScore.zone_code, ResidentPopulation.zone_name)
        .order_by(ResidentPopulation.zone_name)
    ).all()
    return [{"zone_code": z, "name": n} for z, n in rows]


@router.get("/stops")
def stops(zone: str = Query(min_length=1), db=Depends(get_db)):
    rows = db.execute(
        select(func.min(BusStop.stop_id), BusStop.name)
        .join(AccessibilityScore, AccessibilityScore.board_stop_id == BusStop.stop_id)
        .where(AccessibilityScore.zone_code == zone, AccessibilityScore.no_transfer)
        .group_by(BusStop.name)
        .order_by(BusStop.name)
    ).all()
    return [{"stop_id": s, "name": n} for s, n in rows]
