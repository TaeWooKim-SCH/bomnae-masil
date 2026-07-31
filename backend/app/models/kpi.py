"""익명 KPI 집계 이벤트 — **세션ID를 저장하지 않는다** (#36 확정).

상태 전이·스탬프·카드 노출 시점에 R2 라우터가 함께 적재하고, dashboard kpi는 이 테이블만
읽는다. 세션 삭제(#24 연쇄 삭제)와 절연 — 삭제 확인창 "개인 식별이 불가능한 통계는
유지됩니다" 문구의 저장 근거다 (PR #59 검수 때부터의 미결 충돌이 이 테이블로 해소).
KPI 시드(#50)는 seed=true로 넣고, 시연 전 리셋(#51)은 seed=false 실사용분만 지운다.

event_type별 사용 컬럼:
- card_exposed:  has_mission · inflow_status · no_transfer  (추천 응답 카드 1장당 1행)
- quest_started: has_mission                                 (퀘스트 최초 시작 시 1행)
- quest_stamped: stamp_type · amount_krw(spend만)            (스탬프 적립 시 1행)
- first_start:   search_min                                  (세션의 첫 시작 — 간격(분)이라 익명)
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Identity, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from .base import Base


class KpiEvent(Base):
    __tablename__ = "kpi_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    has_mission: Mapped[bool | None] = mapped_column(Boolean)
    inflow_status: Mapped[str | None] = mapped_column(String)  # 확정저유입|추정후보|일반|붐빔
    no_transfer: Mapped[bool | None] = mapped_column(Boolean)
    stamp_type: Mapped[str | None] = mapped_column(String)  # visit|spend
    amount_krw: Mapped[int | None] = mapped_column(Integer)
    search_min: Mapped[float | None] = mapped_column(Numeric)
    seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("ix_kpi_events_type", "event_type"),)
