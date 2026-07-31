"""봄내 조각지도 파생 계산 (#99) — 새 테이블·상태 없음, 완주 기록에서 계산한다.

계약 §5 zone_map(8/1 결정자 승인 추가):
- collected = 완주(recorded)한 퀘스트 활동지의 행정동 zone_code distinct
- available = 활동이 1건 이상 있는 동 distinct (activities.zone_code — R3 백필)
지오메트리는 대시보드 접근성 GeoJSON을 화면이 재사용(서버는 요약 배열 2개만).
수집 칭호는 titles 배열로 합류 — point_ledger 무관(차감·환불 없음 원칙 유지).
"""
from sqlalchemy import select

from app.models import Activity, Quest

COLLECTOR_AT, COLLECTOR_TITLE = 5, "동네 수집가"
EXPLORER_AT, EXPLORER_TITLE = 10, "골목 탐험가"
COMPLETE_TITLE = "봄내 완주"


def compute_zone_map(db, session_id: str) -> dict:
    collected = sorted(
        db.scalars(
            select(Activity.zone_code)
            .join(Quest, Quest.activity_id == Activity.activity_id)
            .where(
                Quest.session_id == session_id,
                Quest.status == "recorded",
                Activity.zone_code.is_not(None),
            )
            .distinct()
        )
    )
    available = sorted(
        db.scalars(select(Activity.zone_code).where(Activity.zone_code.is_not(None)).distinct())
    )
    return {"collected": collected, "available": available}


def zone_titles(zone_map: dict) -> list[str]:
    """수집 칭호 마일스톤 — 5동·10동·전판(available 전부, 빈 판 제외)."""
    n = len(zone_map["collected"])
    titles = []
    if n >= COLLECTOR_AT:
        titles.append(COLLECTOR_TITLE)
    if n >= EXPLORER_AT:
        titles.append(EXPLORER_TITLE)
    if zone_map["available"] and set(zone_map["available"]) <= set(zone_map["collected"]):
        titles.append(COMPLETE_TITLE)
    return titles
