"""세션 라우터 — 계약 §1 (익명 세션: 닉네임 선택 + 만14세 확인만, 개인정보 컬럼 없음).

- balance는 계약 공통 규칙: 별도 잔액 API 없이 응답에 포함 — point_ledger 합산이 진실
- 삭제는 sessions 행 하나만 지운다 — 하위(퀘스트·스탬프·기록·포인트)는 ON DELETE CASCADE(#4)
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.deps import get_current_session
from app.models import Session as UserSession
from app.timebase import now_kst

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    nickname: str | None = Field(default=None, max_length=12)  # 선택, 최대 12자
    age_confirmed: bool = False  # 없으면 미확인으로 취급


@router.post("", status_code=201)
def create_session(body: SessionCreate, db=Depends(get_db)):
    if not body.age_confirmed:
        raise HTTPException(
            400, detail={"code": "AGE_NOT_CONFIRMED", "message": "만 14세 이상만 이용할 수 있어요"}
        )
    for _ in range(3):  # 64비트 id 충돌은 사실상 0이지만, 나더라도 500 대신 재발급
        session = UserSession(
            id=f"ses_{secrets.token_hex(8)}",
            nickname=body.nickname or None,
            age_confirmed=True,
            created_at=now_kst(),  # 세션 생성 시각 — KPI '탐색 시간(중앙값)'의 시작점(#36)
        )
        db.add(session)
        try:
            db.commit()
            return {"session_id": session.id, "balance": 0}
        except IntegrityError:
            db.rollback()
    raise HTTPException(
        500, detail={"code": "INTERNAL", "message": "일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요"}
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    current: UserSession = Depends(get_current_session),
    db=Depends(get_db),
):
    """전체 삭제 — 익명 집계 통계는 유지(#36의 KPI 테이블은 세션ID를 저장하지 않아 삭제와 절연)."""
    if current.id != session_id:
        # 남의 세션 삭제 시도 — 존재 여부는 흘리지 않되, Bearer 세션은 살아 있으므로
        # 401 SESSION_NOT_FOUND(=로컬 키 폐기 신호, 25-screens 0장)를 쏘면 안 된다 → 404
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "요청한 주소를 찾을 수 없어요"}
        )
    db.delete(current)
    db.commit()
