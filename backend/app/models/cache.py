"""② 사전 계산 덩어리의 api_cache — 용도는 LLM 활동 기록 캐시 하나뿐(#4 코멘트).

TAGO 실시간 도착은 미사용 확정(#39 닫힘) — tago용 캐시는 만들지 않는다.
나머지 ②(accessibility_scores·mission_copy·dashboard_geo)와 ①원천 모델은 #11 동결 후 추가.
"""
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime
from sqlalchemy import String

from .base import Base


class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
