"""R4가 제공하는 LLM 서비스 공개 함수."""

from app.services.llm.record_draft import generate_record_draft, template_draft

__all__ = ["generate_record_draft", "template_draft"]
