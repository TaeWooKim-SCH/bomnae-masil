"""모델 공통 Base.

시각 컬럼 규칙(AGENTS 절대 규칙 6): DB의 now()·server_default를 쓰지 않는다.
created_at·started_at 등 모든 시각 값은 앱의 기준 시각 유틸(DEMO_NOW 지원)이 공급한다.
시각은 Asia/Seoul 나이브(naive) — 30-api-contract 0장.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
