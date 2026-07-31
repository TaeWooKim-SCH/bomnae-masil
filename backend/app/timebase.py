"""봄내마실의 '지금' — 전 코드가 이 함수 하나만 쓴다 (AGENTS 절대 규칙 6: now() 직접 호출 금지).

DEMO_NOW 환경변수(예: 2026-08-01T14:00)가 있으면 그 시각으로 고정 — 심야 통합·리허설에도
"오늘 활동"이 나오게 하는 시연 스위치 (10-architecture 8장).
반환은 Asia/Seoul 나이브(naive) — 계약 0장. KST는 DST가 없어 고정 오프셋(+9)이 정확하다.
"""
import os
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    demo = os.environ.get("DEMO_NOW")
    if demo:
        return _parse_demo_now(demo)
    return datetime.now(tz=_KST).replace(tzinfo=None)


def _parse_demo_now(value: str) -> datetime:
    """오타는 요청마다 500이 아니라 부팅 실패로 조기에 드러나야 한다 — main.py가 부팅 시 1회 호출."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise RuntimeError(
            f"DEMO_NOW 형식 오류: {value!r} — 예: 2026-08-01T14:00 (월·일·시 0 패딩 필수)"
        ) from None
    if dt.tzinfo is not None:  # 오프셋이 붙어 와도 나이브 KST로 정규화 (계약 0장)
        dt = dt.astimezone(_KST).replace(tzinfo=None)
    return dt
