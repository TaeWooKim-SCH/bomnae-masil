"""KPI 이벤트 적재·집계 — 산식은 #36 동결안 그대로 (#43 검수가 이 주석과 대조한다).

- 방문 전환율 conversion_pct = stamped ÷ (가게 미션이 있는 started) × 100
- 저유입 비중 low_inflow_pct = 저유입 '확정' 가게 미션 노출 카드 ÷ 가게 미션 있는 노출 카드 × 100
  (추정후보는 분자 제외 — "측정 이력 없음 ≠ 저유입 확정" 편향 방지 원칙)
- 탐색 시간 median_search_min = 세션 생성 → 첫 started 간격(분)의 **중앙값**
- 실행 가능성 feasibility_pct = 무환승 노출 카드 비율 (설계로 보장 — 노출 0이면 100)
- spend_total_krw = 영수증(spend) 인증 금액 합계
- 분모 0이면 null → 화면 "—" (0.0을 돌려주면 "전환율 0%"라는 거짓 숫자 — 0÷0 금지)

적재는 라우터의 비즈니스 트랜잭션에 함께 실려 커밋된다(경합 패자·롤백 시 이벤트도 소멸).
"""
import statistics
from datetime import datetime

from sqlalchemy import func, select

from app.models import KpiEvent
from app.timebase import now_kst


def _at() -> datetime:
    """이벤트 시각은 초 단위로 뭉갠다 — 산식이 안 쓰는 정밀도를 저장하지 않는 익명성 강화(검수 반영)."""
    return now_kst().replace(microsecond=0)


def record_cards_exposed(db, cards: list[dict], inflow_by_merchant: dict[str, str]) -> None:
    at = _at()
    for card in cards:
        mission = card.get("mission")
        db.add(
            KpiEvent(
                event_type="card_exposed",
                has_mission=mission is not None,
                inflow_status=inflow_by_merchant.get(mission["merchant_id"]) if mission else None,
                no_transfer=bool(card["route"]["no_transfer"]),
                occurred_at=at,
            )
        )


def record_quest_started(db, has_mission: bool) -> None:
    db.add(KpiEvent(event_type="quest_started", has_mission=has_mission, occurred_at=_at()))


def record_first_start(db, search_min: float) -> None:
    db.add(
        KpiEvent(event_type="first_start", search_min=round(search_min, 1), occurred_at=_at())
    )


def record_stamp_event(db, stamp_type: str, amount_krw: int | None) -> None:
    db.add(
        KpiEvent(
            event_type="quest_stamped",
            stamp_type=stamp_type,
            amount_krw=amount_krw,
            occurred_at=_at(),
        )
    )


def _count(db, *conds) -> int:
    return db.scalar(select(func.count()).select_from(KpiEvent).where(*conds))


def compute_kpi(db) -> dict:
    started_with_mission = _count(
        db, KpiEvent.event_type == "quest_started", KpiEvent.has_mission.is_(True)
    )
    stamped = _count(db, KpiEvent.event_type == "quest_stamped")
    exposed_mission = _count(
        db, KpiEvent.event_type == "card_exposed", KpiEvent.has_mission.is_(True)
    )
    exposed_low = _count(
        db,
        KpiEvent.event_type == "card_exposed",
        KpiEvent.has_mission.is_(True),
        KpiEvent.inflow_status == "확정저유입",
    )
    exposed_all = _count(db, KpiEvent.event_type == "card_exposed")
    exposed_no_transfer = _count(
        db, KpiEvent.event_type == "card_exposed", KpiEvent.no_transfer.is_(True)
    )
    mins = [float(m) for m in db.scalars(
        select(KpiEvent.search_min).where(KpiEvent.event_type == "first_start")
    )]
    spend_total = db.scalar(
        select(func.coalesce(func.sum(KpiEvent.amount_krw), 0)).where(
            KpiEvent.event_type == "quest_stamped", KpiEvent.stamp_type == "spend"
        )
    )
    seed_included = db.scalar(select(KpiEvent.id).where(KpiEvent.seed.is_(True)).limit(1)) is not None

    return {
        "conversion_pct": round(stamped / started_with_mission * 100, 1) if started_with_mission else None,
        "low_inflow_pct": round(exposed_low / exposed_mission * 100, 1) if exposed_mission else None,
        "median_search_min": round(statistics.median(mins), 1) if mins else None,
        "feasibility_pct": round(exposed_no_transfer / exposed_all * 100, 1) if exposed_all else 100,
        "spend_total_krw": int(spend_total),
        "seed_included": seed_included,
    }
