import sys
import unittest


ACTIVITIES = [
    {"name": "공연 관람", "time": "14:00", "price_krw": 8_000},
    {"name": "전시 관람", "time": "15:00", "price_krw": 0},
    {"name": "원데이 공예", "time": "16:00", "price_krw": 10_000},
    {"name": "독립영화", "time": "18:00", "price_krw": 7_000},
    {"name": "야외 산책", "time": "19:00", "price_krw": 0},
    {"name": "고가 강좌", "time": "20:00", "price_krw": 20_000},
]

SHOPS = [
    {"name": "골목 카페", "low_inflow": True},
    {"name": "동네 서점", "low_inflow": True},
    {"name": "인기 식당", "low_inflow": False},
    {"name": "공방 상점", "low_inflow": True},
    {"name": "시장 가게", "low_inflow": False},
    {"name": "작은 찻집", "low_inflow": True},
]


def score(activity: dict, shop: dict) -> float:
    low_inflow_bonus = 30 if shop["low_inflow"] else 0
    price_bonus = max(0, 10 - activity["price_krw"] / 1_000)
    return float(low_inflow_bonus + price_bonus)


def build_spike_cards(
    activities: list[dict], shops: list[dict], max_budget_krw: int
) -> list[dict]:
    affordable_activities = [
        activity for activity in activities if activity["price_krw"] <= max_budget_krw
    ]
    cards = [
        {
            "activity": activity,
            "shop": shop,
            "score": score(activity, shop),
        }
        for activity in affordable_activities
        for shop in shops
    ]
    return sorted(cards, key=lambda card: card["score"], reverse=True)[:3]


class SpikeTest(unittest.TestCase):
    def test_build_spike_cards_filters_budget_and_returns_three_sorted_cards(self) -> None:
        cards = build_spike_cards(ACTIVITIES, SHOPS, max_budget_krw=10_000)

        self.assertEqual(3, len(cards))
        self.assertTrue(all(card["activity"]["price_krw"] <= 10_000 for card in cards))
        self.assertEqual(
            sorted((card["score"] for card in cards), reverse=True),
            [card["score"] for card in cards],
        )


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0]])
    else:
        for card in build_spike_cards(ACTIVITIES, SHOPS, max_budget_krw=10_000):
            print(card)
