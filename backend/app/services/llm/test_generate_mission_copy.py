import unittest
from contextlib import redirect_stdout
from io import StringIO

from app.services.llm.generate_mission_copy import (
    ActivityMerchantPair,
    InMemoryMissionCopyStore,
    build_mission_prompt,
    demo_pairs,
    generate_missing_mission_copies,
    main,
    run_demo_dry_run,
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
        self.assertIn("할인·혜택", prompt)
        self.assertIn("정확히 한 문장", prompt)
        self.assertIn("제목·마크다운·따옴표", prompt)
        self.assertIn("입력에 없는 위치·상품·역사", prompt)
        self.assertIn("사실로 사용할 수 있는 정보는 활동명·가게명·업종뿐", prompt)

    def test_skips_existing_pair_and_saves_only_new_copy(self) -> None:
        store = InMemoryMissionCopyStore(
            existing_keys={self.existing_pair.key}
        )
        generated_prompts: list[str] = []

        def fake_generate(prompt: str) -> str | None:
            generated_prompts.append(prompt)
            return " 공지천 산책을 마친 뒤 호반 서점에 들러 오늘의 장면을 한 줄로 남겨보세요. "

        result = generate_missing_mission_copies(
            [self.existing_pair, self.new_pair], store, fake_generate
        )

        self.assertEqual(1, result.created_count)
        self.assertEqual(1, result.skipped_count)
        self.assertEqual(0, result.failed_count)
        self.assertEqual(1, len(store.saved_copies))
        self.assertEqual(
            "공지천 산책을 마친 뒤 호반 서점에 들러 오늘의 장면을 한 줄로 남겨보세요.",
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

    def test_does_not_save_markdown_formatted_copy(self) -> None:
        store = InMemoryMissionCopyStore()

        result = generate_missing_mission_copies(
            [self.new_pair], store, lambda _prompt: "# 미션\n\n서점에 들러보세요."
        )

        self.assertEqual(0, result.created_count)
        self.assertEqual(1, result.failed_count)
        self.assertEqual([], store.saved_copies)

    def test_does_not_save_when_copy_omits_an_input_name(self) -> None:
        store = InMemoryMissionCopyStore()

        result = generate_missing_mission_copies(
            [self.new_pair], store, lambda _prompt: "오늘의 경험을 이어가 보세요."
        )

        self.assertEqual(0, result.created_count)
        self.assertEqual(1, result.failed_count)
        self.assertEqual([], store.saved_copies)

    def test_demo_pairs_provides_ten_unique_fake_combinations(self) -> None:
        pairs = demo_pairs()

        self.assertEqual(10, len(pairs))
        self.assertEqual(10, len({pair.key for pair in pairs}))
        self.assertTrue(all(pair.activity_name for pair in pairs))
        self.assertTrue(all(pair.merchant_name for pair in pairs))
        self.assertTrue(all(pair.merchant_category for pair in pairs))

    def test_demo_dry_run_generates_and_keeps_all_ten_fake_copies(self) -> None:
        prompt_count = 0

        def fake_generate(_prompt: str) -> str | None:
            nonlocal prompt_count
            pair = demo_pairs()[prompt_count]
            prompt_count += 1
            return f"{pair.activity_name}을 마친 뒤 {pair.merchant_name}에 들러보세요."

        result, copies = run_demo_dry_run(fake_generate)

        self.assertEqual(10, result.created_count)
        self.assertEqual(0, result.skipped_count)
        self.assertEqual(0, result.failed_count)
        self.assertEqual(10, prompt_count)
        self.assertEqual(10, len(copies))
        self.assertEqual(
            "드라이런 전시 관람을 마친 뒤 드라이런 카페에 들러보세요.",
            copies[0].copy,
        )

    def test_demo_command_prints_summary_without_database_writes(self) -> None:
        pairs = demo_pairs()
        generator_index = 0

        def fake_generate(_prompt: str) -> str | None:
            nonlocal generator_index
            pair = pairs[generator_index]
            generator_index += 1
            return f"{pair.activity_name} 후 {pair.merchant_name}에 들러 오늘의 경험을 이어가 보세요."

        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["--demo"], fake_generate)

        self.assertEqual(0, exit_code)
        self.assertIn("created=10 skipped=0 failed=0", output.getvalue())
        self.assertIn("demo-a-01/demo-m-01", output.getvalue())


if __name__ == "__main__":
    unittest.main()
