"""② 사전 계산 덩어리 (10-architecture 5장) — R3가 대회 전 배치로 만들고 전 코드가 조회만 한다.

- accessibility_scores: 구조는 동결 계약(31-scoring-contract §3) 그대로.
  무환승·경로·소요시간의 단일 원천 — 어디서도 재계산 금지(절대 규칙 7)
- mission_copy: (활동×가게) 조합별 사전 생성 미션 문안(#18, R4 배치)
- dashboard_geo: 대시보드 GeoJSON 2종(#12) 저장 — name으로 구분(accessibility|inflow)
(api_cache는 cache.py — LLM 활동 기록 전용)
"""
from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from .base import Base


class AccessibilityScore(Base):
    __tablename__ = "accessibility_scores"

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    board_stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    zone_code: Mapped[str | None] = mapped_column(String)  # 경계 밖 정류장은 null
    score: Mapped[float] = mapped_column(Numeric, nullable=False)  # 0~100, 경로 불가 행은 0
    no_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 아래 전부: 경로 불가 행(no_transfer=false)이면 null (계약 §3 "경로 불가 행")
    best_route_id: Mapped[str | None] = mapped_column(String)
    route_no: Mapped[str | None] = mapped_column(String)
    alight_stop_id: Mapped[str | None] = mapped_column(String)
    stops_count: Mapped[int | None] = mapped_column(Integer)
    ride_min: Mapped[int | None] = mapped_column(Integer)
    walk_min: Mapped[int | None] = mapped_column(Integer)
    duration_min: Mapped[int | None] = mapped_column(Integer)  # ride+walk, 대기 버퍼 10분 미포함

    __table_args__ = (
        # 동 단위 대표 정류장 조회(계약 §4 두 번째 SQL)와 GET /zones "경로 보유 동" 판정용
        Index("ix_access_activity_zone", "activity_id", "zone_code"),
        Index("ix_access_zone", "zone_code"),
    )


class MissionCopy(Base):
    __tablename__ = "mission_copy"

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String, primary_key=True)
    copy: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class DashboardGeo(Base):
    __tablename__ = "dashboard_geo"

    name: Mapped[str] = mapped_column(String, primary_key=True)  # accessibility | inflow
    geojson: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
