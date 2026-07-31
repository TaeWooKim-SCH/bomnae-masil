import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

GATEWAY_BASE_URL = "https://factchat-cloud.mindlogic.ai/v1/gateway/claude"


def generate(prompt: str, max_tokens: int = 300) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("LLM_MODEL")

    if not api_key or not model:
        return None

    try:
        base_url = os.getenv("ANTHROPIC_BASE_URL", GATEWAY_BASE_URL)
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        return None


def _print_smoke_result(result: str | None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(result if result is not None else "LLM 생성 실패")


if __name__ == "__main__":
    _print_smoke_result(generate("안녕이라고 답해줘"))
