"""포인트 원장 헬퍼 — 적립·잔액·칭호의 유일한 창구 (#34에서 시작, #53에서 확장).

확정 결정: 가게 인증 +40 / 기록 저장 +40(문답 1개 이상) / 완주 +20 = 100.
잔액은 별도 컬럼 없이 point_ledger 합산이 진실. 칭호는 100점 도달 시 "봄내 첫걸음" 자동 해금.
"""
from sqlalchemy import func, select

from app.models import PointLedgerEntry
from app.timebase import now_kst

REASON_STAMP = "stamp"
REASON_RECORD = "record"
REASON_COMPLETION = "completion_bonus"

FIRST_TITLE_AT = 100
FIRST_TITLE = "봄내 첫걸음"


def balance_of(db, session_id: str) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(PointLedgerEntry.delta), 0)).where(
            PointLedgerEntry.session_id == session_id
        )
    )


def add_points(db, session_id: str, quest_id: str, delta: int, reason: str) -> tuple[int, str | None]:
    """원장에 적립하고 (새 잔액, 이번에 해금된 칭호|None)을 돌려준다. commit은 호출부가.

    한계(#53에서 판단): 잔액 계산이 read-then-add라 서로 다른 엔드포인트의 동시 적립이
    겹치면 응답의 balance·칭호 판정이 어긋날 수 있다. 현재는 적립 경로마다 퀘스트당 1회
    유니크 백스톱(stamps·records)이 있어 실제 중복 적립은 불가 — 응답 표시값 한정 리스크.
    """
    before = balance_of(db, session_id)
    db.add(
        PointLedgerEntry(
            session_id=session_id, quest_id=quest_id, delta=delta, reason=reason, created_at=now_kst()
        )
    )
    after = before + delta
    unlocked = FIRST_TITLE if before < FIRST_TITLE_AT <= after else None
    return after, unlocked


def titles_of(balance: int) -> list[str]:
    """보유 칭호 목록 — GET /records 응답용(#35)."""
    return [FIRST_TITLE] if balance >= FIRST_TITLE_AT else []
