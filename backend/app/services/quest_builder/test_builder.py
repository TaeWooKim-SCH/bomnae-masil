"""R4-06 build_quests의 필터·완화·카드 조립 계약 테스트."""

from datetime import date, datetime
import unittest

from app.services.quest_builder.builder import (
    ActivityCandidate,
    BuildQuestsRepository,
    MerchantCandidate,
    RouteCandidate,
    SqlAlchemyQuestRepository,
    _d_day,
    build_quests,
)


DEMO_NOW = datetime(2026, 8, 1, 14, 0)
TIME_WINDOW = {"start": DEMO_NOW, "end": datetime(2026, 8, 1, 18, 0)}


class FakeRepository(BuildQuestsRepository):
    def __init__(self, scheduled: list[ActivityCandidate], always_open: list[ActivityCandidate]):
        self.scheduled = scheduled
        self.always_open = always_open

    def activities(self, *, include_always_open: bool) -> list[ActivityCandidate]:
        return self.scheduled + (self.always_open if include_always_open else [])

    def route_for(self, activity_id: str, *, zone_code: str, stop_id: str | None) -> RouteCandidate | None:
        if activity_id == "unreachable":
            return None
        return RouteCandidate(
            board_stop_id=stop_id or "stop-zone",
            board_stop_name="석사동 행정복지센터",
            alight_stop_id="stop-destination",
            access_score=90,
            route_no="7",
            stops_count=4,
            ride_min=12,
            walk_min=8,
            duration_min=20,
            no_transfer=True,
        )

    def merchant_for(self, activity_id: str) -> MerchantCandidate | None:
        if activity_id == "no-merchant":
            return None
        return MerchantCandidate(
            merchant_id=f"merchant-{activity_id}",
            name="골목 카페",
            category="음식",
            category_detail="비알코올",
            inflow_status="확정저유입",
            copy="활동을 마친 뒤 골목 카페에 들러 오늘의 경험을 기록해보세요.",
        )


def activity(
    activity_id: str,
    *,
    tags: tuple[str, ...] = ("문화·공연",),
    price: int = 0,
    kind: str = "상시형",
    schedule: str = "10:00-18:00",
    runtime: str = "60분 (데모 고정 체류)",
) -> ActivityCandidate:
    return ActivityCandidate(
        activity_id=activity_id,
        name=f"{activity_id} 활동",
        type=kind,
        venue_name="춘천 문화공간",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        schedule_text=schedule,
        runtime_text=runtime,
        price_krw=price,
        interest_tags=tags,
    )


def score(input_value: dict) -> dict:
    return {
        "total": 91,
        "breakdown": {"market": 30, "interest": 25, "access": 18, "time": 10, "budget": 8},
    }


class BuildQuestsTest(unittest.TestCase):
    def test_always_open_relaxation_keeps_scheduled_candidates_in_repository_query(self) -> None:
        class CapturingSession:
            def __init__(self) -> None:
                self.statement = None

            def scalars(self, statement):
                self.statement = statement
                return []

        session = CapturingSession()
        repository = SqlAlchemyQuestRepository(session=session)

        self.assertEqual([], repository.activities(include_always_open=True))
        self.assertNotIn("WHERE activities.type", str(session.statement))

    def test_d_day_uses_the_build_reference_date(self) -> None:
        application = ActivityCandidate(
            **{
                **activity("application", kind="신청형").__dict__,
                "start_date": date(2026, 8, 6),
            }
        )

        self.assertEqual(5, _d_day(application, date(2026, 8, 1)))

    def test_package_exports_the_router_contract_function(self) -> None:
        from app.services.quest_builder import build_quests as public_build_quests

        self.assertIs(public_build_quests, build_quests)

    def test_uses_selected_stop_and_builds_a_100_point_card(self) -> None:
        repository = FakeRepository([], [activity("culture")])

        result = build_quests(
            {
                "interests": ["문화·공연"],
                "origin": {"zone_code": "4211065000", "stop_id": "selected-stop"},
                "time_window": TIME_WINDOW,
                "max_budget_krw": 30000,
                "exclude_activity_ids": [],
            },
            repository=repository,
            score_calculator=score,
            current_time=DEMO_NOW,
        )

        self.assertEqual(["budget", "interest", "always_open"], result.relaxed["steps"])
        self.assertEqual(1, len(result.cards))
        card = result.cards[0]
        self.assertEqual("selected-stop", card["refs"]["board_stop_id"])
        self.assertIsNone(card["route"]["basis_note"])
        self.assertEqual(100, card["max_points"])
        self.assertEqual(7000, card["mission"]["expected_spend_krw"])
        self.assertEqual(10000, card["budget_total_krw"])

    def test_zone_origin_uses_best_stop_note_and_no_merchant_returns_60_points(self) -> None:
        repository = FakeRepository([], [activity("no-merchant")])

        result = build_quests(
            {
                "interests": ["문화·공연"],
                "origin": {"zone_code": "4211065000", "stop_id": None},
                "time_window": TIME_WINDOW,
                "max_budget_krw": 30000,
                "exclude_activity_ids": [],
            },
            repository=repository,
            score_calculator=score,
            current_time=DEMO_NOW,
        )

        card = result.cards[0]
        self.assertEqual("석사동 행정복지센터 정류장 기준", card["route"]["basis_note"])
        self.assertIsNone(card["mission"])
        self.assertEqual(60, card["max_points"])
        self.assertEqual(3000, card["budget_total_krw"])

    def test_relaxes_only_in_fixed_order_and_marks_revisited_cards(self) -> None:
        repository = FakeRepository(
            [activity("too-expensive", price=25000, kind="당일형")],
            [activity("revisit-me", tags=("자연·나들이",))],
        )

        result = build_quests(
            {
                "interests": ["문화·공연"],
                "origin": {"zone_code": "4211065000", "stop_id": None},
                "time_window": TIME_WINDOW,
                "max_budget_krw": 10000,
                "exclude_activity_ids": ["revisit-me"],
            },
            repository=repository,
            score_calculator=score,
            current_time=DEMO_NOW,
        )

        self.assertEqual(["budget", "interest", "always_open", "revisit"], result.relaxed["steps"])
        self.assertEqual(["revisit-me"], [card["refs"]["activity_id"] for card in result.cards])
        self.assertTrue(result.cards[0]["revisit"])

    def test_never_relaxes_unreachable_or_time_infeasible_candidates(self) -> None:
        repository = FakeRepository(
            [activity("unreachable", kind="당일형")],
            [activity("closed", schedule="10:00-12:00")],
        )

        result = build_quests(
            {
                "interests": ["문화·공연"],
                "origin": {"zone_code": "4211065000", "stop_id": None},
                "time_window": TIME_WINDOW,
                "max_budget_krw": 30000,
                "exclude_activity_ids": [],
            },
            repository=repository,
            score_calculator=score,
            current_time=DEMO_NOW,
        )

        self.assertEqual([], result.cards)
        self.assertEqual(["budget", "interest", "always_open"], result.relaxed["steps"])
        self.assertEqual("지금 조건에 맞는 활동이 없어요", result.relaxed["message"])


if __name__ == "__main__":
    unittest.main()
