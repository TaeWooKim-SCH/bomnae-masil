"""미션 인증 라우터 — 계약 §4 verify (#34). stamped 전이 + 스탬프·포인트 적립.

- 검증의 실체는 가게별 4자리 코드 대조 (HMAC·QR_SECRET 없음 확정). QR과 코드 입력은 같은 대조 경로
- QR·코드 = visit, 영수증(+금액) = spend — #36 집계가 stamp_type만 본다
- 영수증 사진은 받지도 저장하지도 않는다 — 요청에 파일 필드 자체가 없다(금액·시각·방식만 DB에)
- 재인증은 멱등: 에러가 아니라 200 + already=true (stamps.quest_id unique가 DB 백스톱)
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.kpi import record_stamp_event
from app.core.points import REASON_STAMP, add_points, balance_of
from app.db import get_db
from app.deps import get_current_session
from app.models import Quest, Stamp
from app.core.merchant_codes import merchant_verify_code
from app.timebase import now_kst

router = APIRouter(prefix="/quests", tags=["quests"])

STAMP_POINTS = 40
AMOUNT_MIN, AMOUNT_MAX = 1_000, 200_000


class VerifyRequest(BaseModel):
    method: Literal["qr", "code", "receipt"]
    merchant_id: str | None = None  # qr 전용 — 클라이언트가 QR에서 파싱한 m
    code: str | None = None  # qr·code
    amount_krw: int | None = None  # receipt 전용

    @model_validator(mode="after")
    def _required_by_method(self):
        need = {"qr": ("merchant_id", "code"), "code": ("code",), "receipt": ("amount_krw",)}
        for field in need[self.method]:
            if getattr(self, field) is None:
                raise ValueError(f"{self.method} 방식에는 {field}가 필요해요")
        return self


def _error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message, **extra})


@router.post("/{quest_id}/verify")
def verify_quest(
    quest_id: str,
    body: VerifyRequest,
    current=Depends(get_current_session),
    db=Depends(get_db),
):
    quest = db.get(Quest, quest_id)
    if quest is None or quest.session_id != current.id:
        raise _error(404, "NOT_FOUND", "요청한 주소를 찾을 수 없어요")

    if quest.status not in ("started", "stamped"):  # 전제 (계약 §4)
        raise _error(400, "QUEST_NOT_STARTED", "퀘스트를 먼저 시작해 주세요")

    mission = (quest.card or {}).get("mission")
    if quest.merchant_id is None or mission is None:
        raise _error(400, "NO_MISSION", "이 퀘스트는 가게 미션이 없어요 — 기록으로 완주해요")

    # 멱등 선확인 — 이미 스탬프가 있으면 검증 없이 성공 톤 (데모 더블탭 = 에러 화면 금지)
    existing = db.scalar(select(Stamp).where(Stamp.quest_id == quest.id))
    if existing is not None:
        return _already(db, current.id, existing)

    if body.method == "qr" and body.merchant_id != quest.merchant_id:
        raise _error(
            400, "WRONG_STORE", f"이 퀘스트의 미션 가게는 {mission['merchant_name']}예요"
        )
    if body.method in ("qr", "code"):
        if body.code != merchant_verify_code(db, quest.merchant_id):
            raise _error(400, "INVALID_CODE", "코드를 다시 확인해 주세요")
        stamp_type, amount = "visit", None
    else:  # receipt — 사진은 애초에 받지 않는다. 금액 범위만 서버 검증
        if not (AMOUNT_MIN <= body.amount_krw <= AMOUNT_MAX):
            raise _error(400, "INVALID_AMOUNT", "금액을 확인해 주세요 (1,000~200,000원)")
        stamp_type, amount = "spend", body.amount_krw

    # try 범위가 add(Stamp)부터인 이유(검수 반영): add_points 안의 잔액 SELECT가 autoflush를
    # 일으켜 유니크 위반이 commit이 아니라 그 지점에서 터진다 — 좁게 감싸면 경합 패자가 500
    try:
        db.add(
            Stamp(
                session_id=current.id,
                quest_id=quest.id,
                merchant_id=quest.merchant_id,
                stamp_type=stamp_type,
                amount_krw=amount,
                created_at=now_kst(),
            )
        )
        quest.status = "stamped"
        balance, unlocked = add_points(db, current.id, quest.id, STAMP_POINTS, REASON_STAMP)
        record_stamp_event(db, stamp_type, amount)  # 익명 KPI(#36) — 경합 패자는 롤백으로 소멸
        db.commit()
    except IntegrityError:  # 동시 인증 경합 — 먼저 찍힌 스탬프가 승자, 패자는 멱등 응답
        db.rollback()
        winner = db.scalar(select(Stamp).where(Stamp.quest_id == quest_id))
        if winner is None:
            raise
        return _already(db, current.id, winner)

    return {
        "stamp_type": stamp_type,
        "already": False,
        "points_added": STAMP_POINTS,
        "balance": balance,
        "title_unlocked": unlocked,
        "message": "스탬프가 적립됐어요!",
    }


def _already(db, session_id: str, stamp: Stamp) -> dict:
    return {
        "stamp_type": stamp.stamp_type,
        "already": True,
        "points_added": 0,
        "balance": balance_of(db, session_id),
        "title_unlocked": None,  # 재인증에선 고정 null (계약 §4)
        "message": "이미 적립된 퀘스트예요",
    }
