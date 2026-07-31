"""DB 모델 — R2만 수정한다(AGENTS 절대 규칙 1). R3·R4는 이슈·단톡으로 컬럼을 요청한다.

세 덩어리(10-architecture 5장) 전부:
①원천(catalog) · ②사전계산(precomputed + api_cache) · ③사용자(user)
"""
from .base import Base
from .cache import ApiCache
from .kpi import KpiEvent
from .catalog import (
    Activity,
    BusStop,
    FloatingPopulation,
    Merchant,
    ResidentPopulation,
    StopRoute,
)
from .precomputed import AccessibilityScore, DashboardGeo, MissionCopy
from .user import (
    QUEST_STATUSES,
    RECORD_PURPOSES,
    PointLedgerEntry,
    Quest,
    Record,
    Session,
    Stamp,
)

__all__ = [
    "Base",
    "ApiCache",
    "KpiEvent",
    "Activity",
    "BusStop",
    "FloatingPopulation",
    "Merchant",
    "ResidentPopulation",
    "StopRoute",
    "AccessibilityScore",
    "DashboardGeo",
    "MissionCopy",
    "QUEST_STATUSES",
    "RECORD_PURPOSES",
    "PointLedgerEntry",
    "Quest",
    "Record",
    "Session",
    "Stamp",
]
