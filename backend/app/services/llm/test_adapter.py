import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.llm.adapter import _print_smoke_result, generate


class GenerateTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_returns_none_when_api_key_is_missing(self) -> None:
        self.assertIsNone(generate("안녕이라고 답해줘"))

    @patch("app.services.llm.adapter.anthropic.Anthropic")
    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "gateway-test-key",
            "LLM_MODEL": "claude-sonnet-4-6",
        },
        clear=True,
    )
    def test_uses_the_aihub_anthropic_gateway(
        self, client_class: object
    ) -> None:
        client_class.return_value.messages.create.return_value.content = [
            SimpleNamespace(text="안녕하세요")
        ]

        result = generate("안녕이라고 답해줘")

        self.assertEqual("안녕하세요", result)
        client_class.assert_called_once_with(
            api_key="gateway-test-key",
            base_url="https://factchat-cloud.mindlogic.ai/v1/gateway/claude",
        )

    @patch("app.services.llm.adapter.anthropic.Anthropic")
    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "official-test-key",
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            "LLM_MODEL": "claude-haiku-4-5-20251001",
        },
        clear=True,
    )
    def test_uses_the_configured_official_anthropic_base_url(
        self, client_class: object
    ) -> None:
        client_class.return_value.messages.create.return_value.content = [
            SimpleNamespace(text="OK")
        ]

        generate("Reply with OK.")

        client_class.assert_called_once_with(
            api_key="official-test-key",
            base_url="https://api.anthropic.com",
        )

    @patch("app.services.llm.adapter.anthropic.Anthropic")
    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "gateway-test-key",
            "LLM_MODEL": "claude-sonnet-4-6",
        },
        clear=True,
    )
    def test_uses_the_requested_token_limit(self, client_class: object) -> None:
        client_class.return_value.messages.create.return_value.content = [
            SimpleNamespace(text="짧은 문구")
        ]

        generate("짧게 생성해줘", max_tokens=200)

        client_class.return_value.messages.create.assert_called_once_with(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": "짧게 생성해줘"}],
        )

    @patch("builtins.print")
    @patch("app.services.llm.adapter.sys.stdout")
    def test_prints_the_smoke_result_as_utf8(
        self, stdout: object, print_function: object
    ) -> None:
        _print_smoke_result("안녕하세요 😊")

        stdout.reconfigure.assert_called_once_with(encoding="utf-8")
        print_function.assert_called_once_with("안녕하세요 😊")

    @patch("app.services.llm.adapter.anthropic.Anthropic", side_effect=RuntimeError)
    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "invalid-test-key",
            "LLM_MODEL": "test-model",
        },
        clear=True,
    )
    def test_returns_none_when_claude_client_fails(self, _client: object) -> None:
        self.assertIsNone(generate("안녕이라고 답해줘"))
