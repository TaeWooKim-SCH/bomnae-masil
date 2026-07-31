"""라우터 공용 의존성 — 세션 인증 (계약 §0: Authorization: Bearer <session_id>, HMAC 없음 확정).

실패는 전부 401 SESSION_NOT_FOUND 하나다 — 이 응답이 화면의 세션 무효 복구 신호(25-screens 0장):
R1은 이걸 받으면 localStorage 키(session_id·active_quest_id)를 폐기하고 첫 방문 모달을 띄운다.
토큰 만료는 만들지 않는다(#24 팁 — 데모 중 만료 버그가 더 큰 위험).
"""
from fastapi import Depends, Header, HTTPException

from app.db import get_db
from app.models import Session as UserSession


def _session_not_found() -> HTTPException:
    return HTTPException(
        401,
        detail={"code": "SESSION_NOT_FOUND", "message": "세션이 없어요 — 처음 화면에서 다시 시작해 주세요"},
    )


def get_current_session(
    authorization: str | None = Header(default=None), db=Depends(get_db)
) -> UserSession:
    if not authorization:
        raise _session_not_found()
    scheme, _, session_id = authorization.partition(" ")
    session_id = session_id.strip()
    if scheme.lower() != "bearer" or not session_id:  # 스킴은 RFC 7235대로 대소문자 무관
        raise _session_not_found()
    session = db.get(UserSession, session_id)
    if session is None:
        raise _session_not_found()
    return session
