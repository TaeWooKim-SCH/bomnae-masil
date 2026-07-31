"""대시보드 라우터 — 계약 §6 (#36). 인증 불필요(데모 공개).

- 지도 2종은 R3 배치 산출물(dashboard_geo)을 **가공 없이 그대로** 서빙 — R2가 만지면 계약 ③ 붕괴
- kpi는 익명 집계 테이블(kpi_events)만 읽는다 — 세션 삭제와 절연(#24)
"""
from fastapi import APIRouter, Depends

from app.core.kpi import compute_kpi
from app.db import get_db
from app.models import DashboardGeo

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_EMPTY = {"type": "FeatureCollection", "features": []}


def _geo(db, name: str) -> dict:
    # R3 적재 전이면 빈 FeatureCollection — 화면이 빈 레이어로 그려지되 죽지 않는다(#37에서 실데이터)
    row = db.get(DashboardGeo, name)
    return row.geojson if row is not None else _EMPTY


@router.get("/accessibility")
def accessibility_geo(db=Depends(get_db)):
    """접근성 히트맵 — FeatureCollection(Polygon), properties {zone_code, name, score, quintile}."""
    return _geo(db, "accessibility")


@router.get("/inflow")
def inflow_geo(db=Depends(get_db)):
    """저유입 상권 — FeatureCollection(Point), properties {name, category, inflow_status}."""
    return _geo(db, "inflow")


@router.get("/kpi")
def kpi(db=Depends(get_db)):
    """성과 숫자 — 산식·분모 0 규칙은 core/kpi.py 주석(#36 동결안, #43 검수 대조)."""
    return compute_kpi(db)
