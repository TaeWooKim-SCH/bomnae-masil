"""추천 라우터 — 계약① §3 정본. R2는 검증→build_quests 호출→ID 발급·스냅샷 저장→응답 변환만 한다.

추천 로직(하드 필터·조립·완화)은 R4 build_quests(계약④), 점수는 R3 scoring 소유 — 여기서 재계산 금지.
추천 순간에 LLM 등 외부 호출은 절대 없다(미션 문안은 사전 생성분을 build_quests가 읽음).
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.kpi import record_cards_exposed
from app.db import get_db
from app.deps import get_current_session
from app.models import Merchant, Quest
from app.timebase import now_kst

logger = logging.getLogger("bomnae")

# R4 v1(#27) 착륙 전에는 R2 소유 목으로 배선 — quest_builder가 공개 함수를 내놓는 순간 자동 스왑
try:
    from app.services.quest_builder import build_quests  # 계약④ 공개 함수 (R4 소유)
except ImportError as _e:
    # quest_builder 내부 결함(의존성 누락 등)까지 조용히 목으로 숨기면 안 된다 — 그 경우 크게 실패
    if getattr(_e, "name", None) and not _e.name.startswith("app.services.quest_builder"):
        raise
    logger.warning("quest_builder 미노출 — 배선용 목 사용 (#27 착륙 시 자동 스왑): %s", _e)
    from app.routers._quest_builder_mock import build_quests


def _call_build_quests(payload: dict) -> tuple[list[dict], dict | None]:
    """호출 규약 어댑터 — 목(튜플)·계약④ 문서 모델(BuildQuestsResult) 어느 쪽이 와도 수용.

    파이썬 호출 규약은 계약④ 동결 시 명문화 예정(#14에 R2 리뷰 의견) — 그 전까지 양쪽 대응.
    """
    result = build_quests(payload)
    if isinstance(result, tuple):
        cards, relaxed = result
    else:  # BuildQuestsResult 모델
        cards, relaxed = result.cards, result.relaxed
    cards = [c.model_dump() if hasattr(c, "model_dump") else c for c in cards]
    if relaxed is not None and hasattr(relaxed, "model_dump"):
        relaxed = relaxed.model_dump()
    return cards, relaxed

router = APIRouter(prefix="/quests", tags=["quests"])

_KST = timezone(timedelta(hours=9))

# 관심사 칩 7종 enum(#48 확정 — 청소년·진로 제외)
Interest = Literal[
    "운동·건강", "문화·공연", "공예·만들기", "사진·미디어", "요리·먹거리", "학습·어학", "자연·나들이"
]

# 필터⑤ 대상 = "이미 시작·완주한 활동"(계약④ 4-1-5). stamped는 started의 후속 상태라 포함
_EXCLUDE_STATUSES = ("started", "stamped", "recorded")


class OriginInput(BaseModel):
    zone_code: str = Field(min_length=1)  # 존재 검증은 ①원천 zones 적재(#11) 후 추가
    stop_id: str | None = None


class TimeWindowInput(BaseModel):
    start: datetime
    end: datetime


class RecommendRequest(BaseModel):
    interests: list[Interest] = Field(min_length=1, max_length=3)
    origin: OriginInput
    time_window: TimeWindowInput
    max_budget_krw: Literal[0, 10000, 30000, 50000] | None

    @field_validator("interests")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("관심사가 중복됐어요")
        return v


def _naive_kst(dt: datetime) -> datetime:
    return dt.astimezone(_KST).replace(tzinfo=None) if dt.tzinfo else dt


@router.post("/recommend")
def recommend(body: RecommendRequest, current=Depends(get_current_session), db=Depends(get_db)):
    start = _naive_kst(body.time_window.start)
    end = _naive_kst(body.time_window.end)
    if end - start < timedelta(minutes=60):
        raise HTTPException(
            400, detail={"code": "INVALID_TIME_WINDOW", "message": "이용 시간을 60분 이상으로 선택해 주세요"}
        )

    # 필터⑤용 exclude — R2가 세션에서 조회해 전달 (계약 §3 소유 경계)
    exclude_activity_ids = list(
        db.scalars(
            select(Quest.activity_id)
            .where(Quest.session_id == current.id, Quest.status.in_(_EXCLUDE_STATUSES))
            .distinct()
        )
    )

    cards, relaxed = _call_build_quests(
        {
            "interests": list(body.interests),
            "origin": {"zone_code": body.origin.zone_code, "stop_id": body.origin.stop_id},
            "time_window": {"start": start, "end": end},
            "max_budget_krw": body.max_budget_krw,
            "exclude_activity_ids": exclude_activity_ids,
        }
    )

    # quest_id·recommendation_id 발급 + 스냅샷 저장(1~6위 전부, 상태 recommended) — R2 소유
    recommendation_id = f"rec_{secrets.token_hex(6)}"
    created_at = now_kst()
    for rank, card in enumerate(cards, start=1):
        card["quest_id"] = f"q_{secrets.token_hex(8)}"
        db.add(
            Quest(
                id=card["quest_id"],
                session_id=current.id,
                recommendation_id=recommendation_id,
                rank=rank,
                card=card,
                activity_id=card["refs"]["activity_id"],
                merchant_id=(card["mission"] or {}).get("merchant_id"),
                board_stop_id=card["refs"]["board_stop_id"],
                alight_stop_id=card["refs"]["alight_stop_id"],
                status="recommended",
                created_at=created_at,
            )
        )

    # 익명 KPI: 노출 카드 이벤트(#36) — 저유입 판정은 merchants.inflow_status 조회(목 가게는 None)
    merchant_ids = [c["mission"]["merchant_id"] for c in cards if c["mission"]]
    inflow_by_merchant = (
        dict(
            db.execute(
                select(Merchant.merchant_id, Merchant.inflow_status).where(
                    Merchant.merchant_id.in_(merchant_ids)
                )
            ).all()
        )
        if merchant_ids
        else {}
    )
    record_cards_exposed(db, cards, inflow_by_merchant)
    db.commit()

    return {
        "recommendation_id": recommendation_id,
        "quests": cards[:3],
        "more": cards[3:6],
        "relaxed": relaxed,
    }
