import unittest

from app.services.llm.generate_mission_copy import (
    ActivityMerchantPair,
    InMemoryMissionCopyStore,
    build_mission_prompt,
    generate_missing_mission_copies,
)


class GenerateMissionCopyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.existing_pair = ActivityMerchantPair(
            activity_id="activity-1",
            activity_name="춘천 전시 관람",
            merchant_id="merchant-1",
            merchant_name="봄내 카페",
            merchant_category="카페",
        )
        self.new_pair = ActivityMerchantPair(
            activity_id="activity-2",
            activity_name="공지천 산책",
            merchant_id="merchant-2",
            merchant_name="호반 서점",
            merchant_category="소매",
        )

    def test_prompt_uses_only_activity_merchant_and_category_context(self) -> None:
        prompt = build_mission_prompt(self.new_pair)

        self.assertIn("공지천 산책", prompt)
        self.assertIn("호반 서점", prompt)
        self.assertIn("소매", prompt)
        self.assertIn("없는 할인", prompt)
        self.assertIn("1~2문장", prompt)

    def test_skips_existing_pair_and_saves_only_new_copy(self) -> None:
        store = InMemoryMissionCopyStore(
            existing_keys={self.existing_pair.key}
        )
        generated_prompts: list[str] = []

        def fake_generate(prompt: str) -> str | None:
            generated_prompts.append(prompt)
            return " 산책 뒤 서점에서 오늘의 장면을 한 줄로 남겨보세요. "

        result = generate_missing_mission_copies(
            [self.existing_pair, self.new_pair], store, fake_generate
        )

        self.assertEqual(1, result.created_count)
        self.assertEqual(1, result.skipped_count)
        self.assertEqual(0, result.failed_count)
        self.assertEqual(1, len(store.saved_copies))
        self.assertEqual(
            "산책 뒤 서점에서 오늘의 장면을 한 줄로 남겨보세요.",
            store.saved_copies[0].copy,
        )
        self.assertEqual(1, len(generated_prompts))
        self.assertIn("공지천 산책", generated_prompts[0])

    def test_does_not_save_when_generator_returns_empty_text(self) -> None:
        store = InMemoryMissionCopyStore()

        result = generate_missing_mission_copies(
            [self.new_pair], store, lambda _prompt: "   "
        )

        self.assertEqual(0, result.created_count)
        self.assertEqual(0, result.skipped_count)
        self.assertEqual(1, result.failed_count)
        self.assertEqual([], store.saved_copies)


if __name__ == "__main__":
    unittest.main()
