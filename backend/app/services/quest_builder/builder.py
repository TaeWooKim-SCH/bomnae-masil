"""R4-06 퀘스트 조립기.

경로·접근성 값은 R3의 ``accessibility_scores``를 조회만 하고, 점수 산식은 R3의
``calculate_score``에 위임한다. 이 모듈은 후보 필터, 완화 순서, 카드 조립만 담당한다.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol

from app.services.scoring import calculate_score
from app.services.scoring.constants import BUS_ROUND_TRIP_KRW, budget_total_krw, mission_spend_krw
from app.timebase import now_kst


RELAXED_MESSAGE = "조건을 조금 넓혀 찾았어요"
WAIT_BUFFER_MIN = 10

_OPERATING_HOURS = re.compile(r"(\d{1,2}):(\d{2})\s*[-~–]\s*(\d{1,2}):(\d{2})")
_RUNTIME_MINUTES = re.compile(r"(\d+)\s*분")
_WEEKDAY = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_INFLOW_PRIORITY = {"확정저유입": 0, "추정후보": 1, "일반": 2, "붐빔": 3}


@dataclass(frozen=True)
class ActivityCandidate:
    activity_id: str
    name: str
    type: str
    venue_name: str
    start_date: date
    end_date: date
    schedule_text: str | None
    runtime_text: str | None
    price_krw: int | None
    interest_tags: tuple[str, ...]


@dataclass(frozen=True)
class RouteCandidate:
    board_stop_id: str
    board_stop_name: str
    alight_stop_id: str
    access_score: float
    route_no: str
    stops_count: int
    ride_min: int
    walk_min: int
    duration_min: int
    no_transfer: bool


@dataclass(frozen=True)
class MerchantCandidate:
    merchant_id: str
    name: str
    category: str
    category_detail: str | None
    inflow_status: str | None
    copy: str


class BuildQuestsRepository(Protocol):
    """R4가 필요한 읽기 전용 데이터만 노출하는 저장소 경계."""

    def activities(self, *, include_always_open: bool) -> list[ActivityCandidate]: ...

    def route_for(
        self, activity_id: str, *, zone_code: str, stop_id: str | None
    ) -> RouteCandidate | None: ...

    def merchant_for(self, activity_id: str) -> MerchantCandidate | None: ...


@dataclass(frozen=True)
class BuildQuestsResult:
    cards: list[dict]
    relaxed: dict | None


class SqlAlchemyQuestRepository:
    """R2 DB helper와 동결 모델을 사용한 실제 읽기 전용 저장소."""

    def __init__(self) -> None:
        from sqlalchemy.orm import Session

        from app.db import get_engine

        self._session = Session(get_engine())

    def close(self) -> None:
        self._session.close()

    def activities(self, *, include_always_open: bool) -> list[ActivityCandidate]:
        from sqlalchemy import select

        from app.models import Activity

        statement = select(Activity)
        if include_always_open:
            statement = statement.where(Activity.type == "상시형")
        else:
            statement = statement.where(Activity.type != "상시형")

        return [
            ActivityCandidate(
                activity_id=row.activity_id,
                name=row.name,
                type=row.type,
                venue_name=row.venue_name,
                start_date=row.start_date,
                end_date=row.end_date,
                schedule_text=row.schedule_text,
                runtime_text=row.runtime_text,
                price_krw=row.price_krw,
                interest_tags=tuple(
                    tag for tag in (row.interest_tags or "").split(";") if tag
                ),
            )
            for row in self._session.scalars(statement)
        ]

    def route_for(
        self, activity_id: str, *, zone_code: str, stop_id: str | None
    ) -> RouteCandidate | None:
        from sqlalchemy import select

        from app.models import AccessibilityScore, BusStop

        statement = (
            select(AccessibilityScore, BusStop.name)
            .join(BusStop, BusStop.stop_id == AccessibilityScore.board_stop_id)
            .where(
                AccessibilityScore.activity_id == activity_id,
                AccessibilityScore.no_transfer.is_(True),
            )
        )
        if stop_id:
            statement = statement.where(AccessibilityScore.board_stop_id == stop_id)
        else:
            statement = (
                statement.where(AccessibilityScore.zone_code == zone_code)
                .order_by(
                    AccessibilityScore.score.desc(),
                    AccessibilityScore.duration_min.asc(),
                    AccessibilityScore.board_stop_id.asc(),
                )
                .limit(1)
            )

        row = self._session.execute(statement).first()
        if row is None:
            return None
        access, board_stop_name = row
        if any(
            value is None
            for value in (
                access.route_no,
                access.alight_stop_id,
                access.stops_count,
                access.ride_min,
                access.walk_min,
                access.duration_min,
            )
        ):
            return None
        return RouteCandidate(
            board_stop_id=access.board_stop_id,
            board_stop_name=board_stop_name,
            alight_stop_id=access.alight_stop_id,
            access_score=float(access.score),
            route_no=access.route_no,
            stops_count=access.stops_count,
            ride_min=access.ride_min,
            walk_min=access.walk_min,
            duration_min=access.duration_min,
            no_transfer=access.no_transfer,
        )

    def merchant_for(self, activity_id: str) -> MerchantCandidate | None:
        from sqlalchemy import case, select

        from app.models import Merchant, MissionCopy

        priority = case(
            _INFLOW_PRIORITY,
            value=Merchant.inflow_status,
            else_=len(_INFLOW_PRIORITY),
        )
        row = self._session.execute(
            select(Merchant, MissionCopy.copy)
            .join(MissionCopy, MissionCopy.merchant_id == Merchant.merchant_id)
            .where(MissionCopy.activity_id == activity_id)
            .order_by(priority, Merchant.merchant_id.asc())
            .limit(1)
        ).first()
        if row is None:
            return None
        merchant, copy = row
        return MerchantCandidate(
            merchant_id=merchant.merchant_id,
            name=merchant.name,
            category=merchant.category,
            category_detail=merchant.category_detail,
            inflow_status=merchant.inflow_status,
            copy=copy,
        )


def build_quests(
    user_input: Mapping[str, object],
    *,
    repository: BuildQuestsRepository | None = None,
    score_calculator: Callable[[dict], Mapping[str, object]] | None = None,
    current_time: datetime | None = None,
) -> BuildQuestsResult:
    """필터를 통과한 후보를 최대 6장 카드로 조립한다.

    ``repository``와 ``score_calculator``는 단위 테스트용 주입 지점이다. 실제 호출은 R2 DB
    helper 및 R3 공개 점수 함수를 사용한다.
    """

    now = current_time or now_kst()
    owns_repository = repository is None
    repository = repository or SqlAlchemyQuestRepository()
    score_calculator = score_calculator or calculate_score
    try:
        return _build_with_relaxation(user_input, repository, score_calculator, now)
    finally:
        if owns_repository:
            repository.close()  # type: ignore[union-attr]


def _build_with_relaxation(
    user_input: Mapping[str, object],
    repository: BuildQuestsRepository,
    score_calculator: Callable[[dict], Mapping[str, object]],
    now: datetime,
) -> BuildQuestsResult:
    interests = _required_list(user_input, "interests")
    origin = _required_mapping(user_input, "origin")
    time_window = _required_mapping(user_input, "time_window")
    zone_code = _required_string(origin, "zone_code")
    stop_id = origin.get("stop_id") or None
    if stop_id is not None and not isinstance(stop_id, str):
        raise ValueError("origin.stop_id must be a string or null")

    start = _as_datetime(time_window.get("start"), "time_window.start")
    end = _as_datetime(time_window.get("end"), "time_window.end")
    if end - start < timedelta(minutes=60):
        raise ValueError("time window must be at least 60 minutes")
    budget = user_input.get("max_budget_krw")
    if budget is not None and (not isinstance(budget, int) or budget < 0):
        raise ValueError("max_budget_krw must be a non-negative integer or null")
    excluded = set(_optional_list(user_input, "exclude_activity_ids"))

    steps: list[str] = []
    state = _SearchState(
        budget_krw=budget,
        require_interest=True,
        include_always_open=False,
        allow_revisit=False,
    )
    cards = _eligible_cards(
        repository, score_calculator, interests, zone_code, stop_id, start, end, budget, excluded, state, now
    )

    if len(cards) < 3 and isinstance(budget, int) and budget > 0:
        steps.append("budget")
        state = _SearchState(
            budget_krw=int(budget * 1.3),
            require_interest=True,
            include_always_open=False,
            allow_revisit=False,
        )
        cards = _eligible_cards(
            repository, score_calculator, interests, zone_code, stop_id, start, end, budget, excluded, state, now
        )

    if len(cards) < 3:
        steps.append("interest")
        state = _SearchState(
            budget_krw=state.budget_krw,
            require_interest=False,
            include_always_open=False,
            allow_revisit=False,
        )
        cards = _eligible_cards(
            repository, score_calculator, interests, zone_code, stop_id, start, end, budget, excluded, state, now
        )

    if len(cards) < 3:
        steps.append("always_open")
        state = _SearchState(
            budget_krw=state.budget_krw,
            require_interest=False,
            include_always_open=True,
            allow_revisit=False,
        )
        cards = _eligible_cards(
            repository, score_calculator, interests, zone_code, stop_id, start, end, budget, excluded, state, now
        )

    if len(cards) < 3 and excluded:
        steps.append("revisit")
        state = _SearchState(
            budget_krw=state.budget_krw,
            require_interest=False,
            include_always_open=True,
            allow_revisit=True,
        )
        cards = _eligible_cards(
            repository, score_calculator, interests, zone_code, stop_id, start, end, budget, excluded, state, now
        )

    cards.sort(key=lambda card: (-card["score"]["total"], card["refs"]["activity_id"]))
    relaxed = {"steps": steps, "message": RELAXED_MESSAGE} if steps else None
    return BuildQuestsResult(cards=cards[:6], relaxed=relaxed)


@dataclass(frozen=True)
class _SearchState:
    budget_krw: int | None
    require_interest: bool
    include_always_open: bool
    allow_revisit: bool


def _eligible_cards(
    repository: BuildQuestsRepository,
    score_calculator: Callable[[dict], Mapping[str, object]],
    interests: list[str],
    zone_code: str,
    stop_id: str | None,
    window_start: datetime,
    window_end: datetime,
    requested_budget: int | None,
    excluded: set[str],
    state: _SearchState,
    now: datetime,
) -> list[dict]:
    cards: list[dict] = []
    for activity in repository.activities(include_always_open=state.include_always_open):
        if not _is_available_today(activity, now.date()):
            continue
        if state.require_interest and not set(interests).intersection(activity.interest_tags):
            continue
        if not state.allow_revisit and activity.activity_id in excluded:
            continue
        activity_timing = _activity_timing(activity, window_start, window_end, now)
        if activity_timing is None:
            continue
        route = repository.route_for(activity.activity_id, zone_code=zone_code, stop_id=stop_id)
        if route is None or not route.no_transfer:
            continue
        fit = _time_fit(window_start, window_end, activity_timing, route.duration_min)
        if fit is None:
            continue
        merchant = None if requested_budget == 0 else repository.merchant_for(activity.activity_id)
        cost = _budget_total(activity, merchant)
        if requested_budget == 0:
            if activity.price_krw != 0:
                continue
        elif state.budget_krw is not None and cost > state.budget_krw:
            continue
        cards.append(
            _build_card(
                activity,
                route,
                merchant,
                interests,
                cost,
                fit,
                stop_id is None,
                activity.activity_id in excluded,
                score_calculator,
                requested_budget,
            )
        )
    return cards


def _is_available_today(activity: ActivityCandidate, today: date) -> bool:
    return activity.start_date <= today <= activity.end_date


def _activity_timing(
    activity: ActivityCandidate, window_start: datetime, window_end: datetime, now: datetime
) -> tuple[datetime, datetime, int] | None:
    """상시형에만 적재된 운영시간·60분 체류 정보를 읽는다.

    시간 원천이 없는 당일형은 시간 하드 필터에서 제외한다는 R3 확정 사항을 따른다.
    """

    if activity.type != "상시형" or _is_closed_today(activity.schedule_text, now.weekday()):
        return None
    hours = _parse_operating_hours(activity.schedule_text)
    runtime_min = _parse_runtime_minutes(activity.runtime_text)
    if hours is None or runtime_min is None:
        return None
    opens, closes = hours
    day = window_start.date()
    if window_end.date() != day or now.date() != day:
        return None
    return (
        datetime.combine(day, opens),
        datetime.combine(day, closes),
        runtime_min,
    )


def _time_fit(
    window_start: datetime,
    window_end: datetime,
    timing: tuple[datetime, datetime, int],
    duration_min: int,
) -> float | None:
    opens, closes, runtime_min = timing
    arrival = window_start + timedelta(minutes=duration_min + WAIT_BUFFER_MIN)
    activity_start = max(arrival, opens)
    activity_end = activity_start + timedelta(minutes=runtime_min)
    if activity_end > closes or activity_end > window_end:
        return None
    total_window = (window_end - window_start).total_seconds() / 60
    remaining = (window_end - activity_end).total_seconds() / 60
    return max(0.0, min(1.0, remaining / total_window))


def _build_card(
    activity: ActivityCandidate,
    route: RouteCandidate,
    merchant: MerchantCandidate | None,
    interests: list[str],
    budget_total_krw: int,
    time_fit_ratio: float,
    uses_zone_stop: bool,
    revisit: bool,
    score_calculator: Callable[[dict], Mapping[str, object]],
    requested_budget: int | None,
) -> dict:
    score = dict(
        score_calculator(
            {
                "activity_id": activity.activity_id,
                "interests": interests,
                "activity_interest_tags": list(activity.interest_tags),
                "merchant_inflow_status": merchant.inflow_status if merchant else None,
                "access_score": route.access_score,
                "time_fit_ratio": time_fit_ratio,
                "budget_fit_ratio": _budget_fit_ratio(budget_total_krw, requested_budget),
            }
        )
    )
    _validate_score(score)
    mission = (
        {
            "merchant_id": merchant.merchant_id,
            "merchant_name": merchant.name,
            "copy": merchant.copy,
            "expected_spend_krw": _expected_spend(merchant),
        }
        if merchant
        else None
    )
    return {
        "title": activity.name,
        "activity": {
            "name": activity.name,
            "type": activity.type,
            "place_name": activity.venue_name,
            "schedule_text": activity.schedule_text or "",
            "price_krw": activity.price_krw,
            "d_day": _d_day(activity),
        },
        "mission": mission,
        "route": {
            "board_stop_name": route.board_stop_name,
            "route_no": route.route_no,
            "stops_count": route.stops_count,
            "ride_min": route.ride_min,
            "walk_min": route.walk_min,
            "no_transfer": route.no_transfer,
            "basis_note": f"{route.board_stop_name} 정류장 기준" if uses_zone_stop else None,
        },
        "budget_total_krw": budget_total_krw,
        "score": score,
        "max_points": 100 if mission else 60,
        "revisit": revisit,
        "refs": {
            "activity_id": activity.activity_id,
            "board_stop_id": route.board_stop_id,
            "alight_stop_id": route.alight_stop_id,
        },
    }


def _parse_operating_hours(schedule_text: str | None) -> tuple[time, time] | None:
    match = _OPERATING_HOURS.search(schedule_text or "")
    if match is None:
        return None
    values = [int(value) for value in match.groups()]
    try:
        opens = time(values[0], values[1])
        closes = time(values[2], values[3])
    except ValueError:
        return None
    return (opens, closes) if opens < closes else None


def _parse_runtime_minutes(runtime_text: str | None) -> int | None:
    match = _RUNTIME_MINUTES.search(runtime_text or "")
    return int(match.group(1)) if match and int(match.group(1)) > 0 else None


def _is_closed_today(schedule_text: str | None, weekday: int) -> bool:
    match = re.search(r"휴관\s*([월화수목금토일])", schedule_text or "")
    return bool(match and _WEEKDAY[match.group(1)] == weekday)


def _expected_spend(merchant: MerchantCandidate) -> int:
    return mission_spend_krw(_merchant_spend_category(merchant))


def _budget_total(activity: ActivityCandidate, merchant: MerchantCandidate | None) -> int:
    if activity.price_krw is None:
        return 10**9
    if merchant is None:
        return activity.price_krw + BUS_ROUND_TRIP_KRW
    return budget_total_krw(activity.price_krw, _merchant_spend_category(merchant))


def _merchant_spend_category(merchant: MerchantCandidate) -> str:
    """공용 비용표가 이해하는 업종명으로 원천 대분류·상세분류를 정규화한다."""

    detail = merchant.category_detail or ""
    if any(word in detail for word in ("카페", "커피", "비알코올")):
        return "카페"
    return merchant.category


def _budget_fit_ratio(budget_total_krw: int, budget_krw: int | None) -> float:
    if budget_krw in (None, 0):
        return 1.0
    return max(0.0, min(1.0, (budget_krw - budget_total_krw) / budget_krw))


def _d_day(activity: ActivityCandidate) -> int | None:
    return None if activity.type != "신청형" else max(0, (activity.start_date - now_kst().date()).days)


def _validate_score(score: Mapping[str, object]) -> None:
    breakdown = score.get("breakdown")
    if not isinstance(score.get("total"), int) or not isinstance(breakdown, Mapping):
        raise ValueError("R3 calculate_score returned an invalid score result")
    fields = ("market", "interest", "access", "time", "budget")
    if any(not isinstance(breakdown.get(field), int) for field in fields):
        raise ValueError("R3 calculate_score returned an invalid score breakdown")
    if score["total"] != sum(breakdown[field] for field in fields):
        raise ValueError("R3 calculate_score total must equal the breakdown sum")


def _required_mapping(values: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = values.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _required_list(values: Mapping[str, object], key: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def _optional_list(values: Mapping[str, object], key: str) -> list[str]:
    value = values.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def _required_string(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _as_datetime(value: object, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError(f"{field_name} must be an ISO datetime")
