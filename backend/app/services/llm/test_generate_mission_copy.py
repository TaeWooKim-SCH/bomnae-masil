import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.services.llm.generate_mission_copy import (
    ActivityMerchantPair,
    InMemoryMissionCopyStore,
    MissionCopy,
    PostgresMissionCopyStore,
    build_mission_prompt,
    demo_pairs,
    generate_missing_mission_copies,
    load_nearby_activity_merchant_pairs,
    main,
    run_demo_dry_run,
)


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None) -> None:
        self.fetchone_values = iter(fetchone_values or [])
        self.fetchall_values = fetchall_values or []
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))

    def fetchone(self):
        return next(self.fetchone_values)

    def fetchall(self):
        return self.fetchall_values


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_value = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        return None


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

        self.assertIn("활동명·가게명·업종 외의 사실을 절대 덧붙이지 마", prompt)
        self.assertIn("오늘의 경험을 한 줄로 기록", prompt)

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

    def test_uses_exact_name_template_when_copy_omits_an_input_name(self) -> None:
        store = InMemoryMissionCopyStore()

        result = generate_missing_mission_copies(
            [self.new_pair], store, lambda _prompt: "오늘의 경험을 이어가 보세요."
        )

        self.assertEqual(1, result.created_count)
        self.assertEqual(0, result.failed_count)
        self.assertEqual(
            "공지천 산책 활동을 마친 뒤 호반 서점에 들러 오늘의 경험을 한 줄로 기록해보세요.",
            store.saved_copies[0].copy,
        )

    def test_saves_when_names_differ_only_by_unicode_width(self) -> None:
        pair = ActivityMerchantPair(
            activity_id="activity-width",
            activity_name="전시 관람",
            merchant_id="merchant-width",
            merchant_name="３６６세차장",
            merchant_category="기타",
        )
        store = InMemoryMissionCopyStore()

        result = generate_missing_mission_copies(
            [pair],
            store,
            lambda _prompt: "전시 관람을 마친 뒤 366세차장에 들러 오늘의 경험을 기록해보세요.",
        )

        self.assertEqual(1, result.created_count)
        self.assertEqual(0, result.failed_count)
        self.assertEqual(1, len(store.saved_copies))

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

    def test_real_pair_loader_uses_radius_and_per_activity_limit(self) -> None:
        cursor = FakeCursor(
            fetchall_values=[
                ("activity-1", "전시 관람", "merchant-1", "골목 카페", "카페"),
                ("activity-1", "전시 관람", "merchant-2", "동네 서점", "서점"),
            ]
        )

        pairs = load_nearby_activity_merchant_pairs(
            FakeConnection(cursor), limit_per_activity=10, total_limit=20
        )

        self.assertEqual(
            [
                ActivityMerchantPair(
                    "activity-1", "전시 관람", "merchant-1", "골목 카페", "카페"
                ),
                ActivityMerchantPair(
                    "activity-1", "전시 관람", "merchant-2", "동네 서점", "서점"
                ),
            ],
            pairs,
        )
        query, params = cursor.executed[0]
        self.assertIn("BETWEEN %s AND %s", query)
        self.assertIn("candidate_rank <= %s", query)
        self.assertIn("ORDER BY random()", query)
        self.assertEqual((500, 1000, 10, 20), params)

    def test_postgres_store_skips_existing_pair_and_inserts_with_conflict_safety(self) -> None:
        cursor = FakeCursor(fetchone_values=[(False,), (True,)])
        store = PostgresMissionCopyStore(FakeConnection(cursor))

        self.assertFalse(store.has_pair(("activity-1", "merchant-1")))
        store.save(MissionCopy("activity-1", "merchant-1", "문구입니다. 해보세요."))
        self.assertTrue(store.has_pair(("activity-1", "merchant-1")))

        insert_query, insert_params = cursor.executed[1]
        self.assertIn("ON CONFLICT (activity_id, merchant_id) DO NOTHING", insert_query)
        self.assertEqual(("activity-1", "merchant-1", "문구입니다. 해보세요."), insert_params)

    def test_real_command_limits_persisted_real_pairs_and_commits_once(self) -> None:
        cursor = FakeCursor(
            fetchone_values=[(False,)],
            fetchall_values=[("activity-1", "전시 관람", "merchant-1", "골목 카페", "카페")],
        )
        connection = FakeConnection(cursor)
        output = StringIO()

        with (
            patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}),
            patch(
                "app.services.llm.generate_mission_copy.connect_database",
                return_value=connection,
            ),
            redirect_stdout(output),
        ):
            exit_code = main(
                ["--real", "--limit", "1"],
                lambda _prompt: "전시 관람 후 골목 카페에 들러 여운을 이어가 보세요.",
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(1, connection.commits)
        self.assertIn("mode=real created=1 skipped=0 failed=0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
