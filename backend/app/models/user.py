"""③ 사용자 데이터 5종 (10-architecture 5장) — sessions·quests·stamps·records·point_ledger.

- 사용자 테이블의 외래키는 전부 ON DELETE CASCADE — "세션 삭제 = 내 기록 전체 삭제"(#24)
- 필드명·상태값은 계약①(30-api-contract) 동결값과 일치시킨다
- ①원천·②사전계산 모델은 #11 동결 후 별도 모듈로 추가 (#4 코멘트: 부분 완료 선언)
- merchant_id·activity_id·정류장 id는 ①원천 테이블 적재 전이므로 아직 FK 없이 문자열 참조만 둔다
  (merchants FK 등은 ①원천 모델 커밋에서 후속)
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from .base import Base

# 5-1 상태 모델 — DB·화면·성과 집계가 전부 이 정의 하나를 쓴다
QUEST_STATUSES = ("recommended", "started", "stamped", "recorded", "abandoned")

# 계약① §5 purpose enum
RECORD_PURPOSES = ("portfolio", "hobby", "learning")


class Session(Base):
    """익명 세션 — 닉네임+만14세 확인만, 개인정보 없음. 잔액은 point_ledger 합산."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "ses_a1b2c3"
    nickname: Mapped[str | None] = mapped_column(String(12))  # 선택, 최대 12자
    age_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Quest(Base):
    """퀘스트 = 추천 카드 스냅샷 1장 + 진행 상태.

    컬럼 구성은 #4 코멘트 확정: refs 컬럼 + QuestCard 원본 JSONB + status + started_at.
    quest_id·recommendation_id 발급과 스냅샷 저장은 R2 라우터 소유(계약① §3).
    """

    __tablename__ = "quests"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "q_301"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_id: Mapped[str] = mapped_column(String, nullable=False)  # "rec_x1"
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1~3=quests, 4~6=more
    card: Mapped[dict] = mapped_column(JSONB, nullable=False)  # QuestCard 원본
    # refs 컬럼 — 계약① QuestCard.refs + 미션 가게. 필터⑤(기시작·완주 활동 제외)와
    # 방문 전환율(stamped ÷ 가게 미션 있는 started) 집계가 이 컬럼을 조회한다
    activity_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str | None] = mapped_column(String)  # 가게 없는 퀘스트 null
    board_stop_id: Mapped[str] = mapped_column(String, nullable=False)
    alight_stop_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="recommended"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('recommended','started','stamped','recorded','abandoned')",
            name="ck_quests_status",
        ),
        # "이어하기"(가장 최근 started 1건)·동시 진행 1개 판정·필터⑤ 조회용
        Index("ix_quests_session_status", "session_id", "status"),
        Index("ix_quests_recommendation_id", "recommendation_id"),
    )


class Stamp(Base):
    """미션 인증 스탬프 — 퀘스트당 1장(재인증 멱등, #34).

    stamp_type: QR·코드 = 'visit'(방문), 영수증+금액 = 'spend'(소비) — 구분 집계(#36).
    """

    __tablename__ = "stamps"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    stamp_type: Mapped[str] = mapped_column(String, nullable=False)  # 'visit'|'spend'
    amount_krw: Mapped[int | None] = mapped_column(Integer)  # spend만 (1,000~200,000 검증은 API 계층)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("stamp_type in ('visit','spend')", name="ck_stamps_type"),
        CheckConstraint(
            "(stamp_type = 'spend') = (amount_krw is not null)",
            name="ck_stamps_amount_iff_spend",
        ),
        Index("ix_stamps_session_id", "session_id"),
    )


class Record(Base):
    """활동 기록 — 저장 시 recorded 전이(완주), 저장 후 읽기 전용. 퀘스트당 1건(409 ALREADY_RECORDED)."""

    __tablename__ = "records"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "rec_77"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    purpose: Mapped[str] = mapped_column(String, nullable=False, default="hobby")
    answers: Mapped[list] = mapped_column(JSONB, nullable=False)  # 고정 3문항 답변(빈 값 허용)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)  # 스탬프 없이 저장 시 false
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "purpose in ('portfolio','hobby','learning')", name="ck_records_purpose"
        ),
        Index("ix_records_session_id", "session_id"),
    )


class PointLedgerEntry(Base):
    """포인트 원장(#4 코멘트) — 적립은 상태 전이에 정확히 걸린다: stamped +40 / recorded +40 / 완주 +20.

    잔액·칭호(100점 도달 해금)는 이 원장 합산으로 계산한다(별도 잔액 컬럼 없음).
    reason 값은 R2-11(#53)에서 확정해 쓴다 (예: 'stamp'|'record'|'completion_bonus').
    """

    __tablename__ = "point_ledger"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("ix_point_ledger_session_id", "session_id"),)
