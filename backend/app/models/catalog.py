"""① 원천 데이터 6종 (10-architecture 5장) — 파이프라인이 채우고 서버는 읽기만 한다.

구조의 정본은 R3 초안(pipeline/load/schema.sql, R2 승인 절차)을 그대로 승인한 것이다.
- FK 없음: 적재 순서를 강제하지 않는다 (R3 로더 친화)
- 좌표는 전부 EPSG:4326 (경도 longitude·위도 latitude)
- 추가분: merchants.verify_code — 데모 가게 4자리 인증코드(#47 시드, 그 외 가게는 null).
  코드 확정·인쇄 후 merchants 재적재 금지(ID 동결 — pipeline/AGENTS.md)
"""
from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BusStop(Base):
    __tablename__ = "bus_stops"

    stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_stop_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    source_date: Mapped[date | None] = mapped_column(Date)


class StopRoute(Base):
    __tablename__ = "stop_routes"

    route_id: Mapped[str] = mapped_column(String, primary_key=True)
    route_no: Mapped[str] = mapped_column(String, nullable=False)
    stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_name: Mapped[str] = mapped_column(String, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    source_date: Mapped[date | None] = mapped_column(Date)


class Activity(Base):
    __tablename__ = "activities"

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_event_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 당일형|신청형|상시형
    status: Mapped[str | None] = mapped_column(String)
    genre: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    schedule_text: Mapped[str | None] = mapped_column(Text)
    runtime_text: Mapped[str | None] = mapped_column(Text)
    price_krw: Mapped[int | None] = mapped_column(Integer)
    price_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)
    audience_text: Mapped[str | None] = mapped_column(Text)
    venue_name: Mapped[str] = mapped_column(String, nullable=False)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    needs_geocode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    poster_url: Mapped[str | None] = mapped_column(Text)


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_merchant_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    category_detail: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(Text)
    zone_code: Mapped[str | None] = mapped_column(String)
    zone_name: Mapped[str | None] = mapped_column(String)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    # 확정저유입 | 추정후보 | 일반 | 붐빔 (31-scoring-contract ScoreInput — 값 검증은 R3 배치)
    inflow_status: Mapped[str] = mapped_column(String, nullable=False)
    # 데모 가게 5곳만 4자리 코드(#47 시드), 그 외 null — 인쇄 후 재적재 금지(ID 동결)
    verify_code: Mapped[str | None] = mapped_column(String(4))


class FloatingPopulation(Base):
    __tablename__ = "floating_population"

    zone_code: Mapped[str] = mapped_column(String, primary_key=True)
    zone_name: Mapped[str] = mapped_column(String, nullable=False)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    daily_average_floating_population: Mapped[int] = mapped_column(Integer, nullable=False)


class ResidentPopulation(Base):
    __tablename__ = "resident_population"

    zone_code: Mapped[str] = mapped_column(String, primary_key=True)
    zone_name: Mapped[str] = mapped_column(String, nullable=False)
    reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    resident_population: Mapped[int] = mapped_column(Integer, nullable=False)
