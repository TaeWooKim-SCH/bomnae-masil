"""Frozen, shared cost assumptions for recommendation filtering and scoring."""

BUS_ROUND_TRIP_KRW = 3_000
MISSION_SPEND_KRW = {
    "cafe": 7_000,
    "restaurant": 12_000,
    "retail": 5_000,
    "other": 8_000,
}


def mission_spend_krw(category: str | None) -> int:
    """Return the frozen mission estimate without making a database query."""
    value = (category or "").replace(" ", "")
    if "카페" in value or "제과" in value:
        return MISSION_SPEND_KRW["cafe"]
    if "음식" in value or "식당" in value:
        return MISSION_SPEND_KRW["restaurant"]
    if "편의" in value or "소매" in value:
        return MISSION_SPEND_KRW["retail"]
    return MISSION_SPEND_KRW["other"]


def budget_total_krw(activity_price_krw: int, merchant_category: str | None) -> int:
    """Activity price + frozen mission estimate + fixed return bus fare."""
    if activity_price_krw < 0:
        raise ValueError("activity_price_krw must be non-negative")
    return activity_price_krw + mission_spend_krw(merchant_category) + BUS_ROUND_TRIP_KRW
