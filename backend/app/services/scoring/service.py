from __future__ import annotations

"""Pure R3 ranking implementation for one already-eligible activity/merchant pair."""

import math
import re
from typing import Literal, TypedDict

InterestChip = Literal[
    "운동·건강", "문화·공연", "공예·만들기", "사진·미디어", "요리·먹거리", "학습·어학", "자연·나들이",
]
InflowStatus = Literal["확정저유입", "추정후보", "일반", "붐빔"]
INTEREST_CHIPS = frozenset(InterestChip.__args__)
INFLOW_COMPONENT_RATIO: dict[str | None, float] = {
    "확정저유입": 1.0,
    "추정후보": 0.5,
    None: 0.5,
    "일반": 0.25,
    "붐빔": 0.0,
}


class ScoreInput(TypedDict):
    activity_id: str
    interests: list[str]
    activity_interest_tags: list[str]
    merchant_inflow_status: str | None
    access_score: float
    time_fit_ratio: float
    budget_fit_ratio: float


class ScoreBreakdown(TypedDict):
    market: int
    interest: int
    access: int
    time: int
    budget: int


class ScoreResult(TypedDict):
    total: int
    breakdown: ScoreBreakdown


def normalize_merchant_name(value: str) -> str:
    """Normalize the name portion used by the one visitor-stat matching rule."""
    normalized = value.lower().strip()
    for token in ("주식회사", "(주)", "㈜", "유한회사", "합자회사"):
        normalized = normalized.replace(token, "")
    return re.sub(r"[\s\W_]+", "", normalized)


def classify_inflow_status(visitor_count: int, peer_visitor_counts: list[int]) -> InflowStatus:
    """Apply the frozen lower-40% / upper-20% rule for one matched merchant.

    Unmatched merchants never call this function; they remain ``추정후보``.
    Equal counts use the first sorted position so equal shops cannot be split
    into different labels merely by input order.
    """
    if visitor_count < 0 or not peer_visitor_counts or any(count < 0 for count in peer_visitor_counts):
        raise ValueError("visitor counts must be non-negative and non-empty")
    ordered = sorted(peer_visitor_counts)
    if visitor_count not in ordered:
        raise ValueError("visitor_count must belong to peer_visitor_counts")
    rank = ordered.index(visitor_count)
    lower_end = math.ceil(len(ordered) * 0.4)
    upper_start = math.ceil(len(ordered) * 0.8)
    if rank < lower_end:
        return "확정저유입"
    if rank >= upper_start:
        return "붐빔"
    return "일반"


def _rounded_component(ratio: float, maximum: int, name: str) -> int:
    if not 0 <= ratio <= 1:
        raise ValueError(f"{name} must be in 0..1")
    return round(ratio * maximum)


def calculate_score(input: ScoreInput) -> ScoreResult:
    """Return the frozen five weighted components for an eligible candidate."""
    interests = set(input["interests"])
    tags = set(input["activity_interest_tags"])
    if not input["activity_id"] or not 1 <= len(interests) <= 3 or not interests.issubset(INTEREST_CHIPS):
        raise ValueError("interests must contain one to three frozen chips")
    if not tags.issubset(INTEREST_CHIPS):
        raise ValueError("activity_interest_tags must use frozen chips")
    status = input["merchant_inflow_status"]
    if status not in INFLOW_COMPONENT_RATIO:
        raise ValueError("merchant_inflow_status is invalid")
    breakdown: ScoreBreakdown = {
        "market": _rounded_component(INFLOW_COMPONENT_RATIO[status], 30, "market"),
        "interest": _rounded_component(len(interests & tags) / len(interests), 25, "interest"),
        "access": _rounded_component(float(input["access_score"]) / 100, 20, "access_score"),
        "time": _rounded_component(float(input["time_fit_ratio"]), 15, "time_fit_ratio"),
        "budget": _rounded_component(float(input["budget_fit_ratio"]), 10, "budget_fit_ratio"),
    }
    return {"total": sum(breakdown.values()), "breakdown": breakdown}
