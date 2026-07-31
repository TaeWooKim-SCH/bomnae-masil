"""기록 라우터 — 계약 §5 (#35). 생성(generate)·저장(save) 한 창구 + 보관함.

- 실시간 LLM을 부르는 유일한 지점 — 반드시 캐시 프록시(#7)를 통과하고, 어떤 경우에도 500을
  내지 않는다: LLM 오류·8초 초과·CACHE_ONLY=1 미스 → 템플릿 초안으로 200(from_template)
- 개인정보 원칙 4: LLM 페이로드에 닉네임·세션ID를 절대 넣지 않는다 — build_llm_payload가
  유일한 조립 창구(검증 스크립트가 금지 필드를 테스트로 고정)
- 프롬프트·대체 문구는 R4 소유(#38) — 여기는 호출·저장·캐시 배선만
"""
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.cache import build_record_cache_key, cached_call
from app.core.points import (
    REASON_COMPLETION,
    REASON_RECORD,
    add_points,
    balance_of,
    titles_of,
)
from app.db import get_db
from app.deps import get_current_session
from app.models import Quest, Record, Stamp
from app.timebase import now_kst

logger = logging.getLogger("bomnae")

# R4 #38 착륙 전에는 R2 소유 목으로 배선 — llm 패키지가 공개 함수를 내놓는 순간 자동 스왑
try:
    from app.services.llm import generate_record_draft, template_draft  # R4 소유 (#38)
except ImportError as _e:
    if getattr(_e, "name", None) and not _e.name.startswith("app.services.llm"):
        raise
    logger.warning("llm 기록 함수 미노출 — 배선용 목 사용 (#38 착륙 시 자동 스왑): %s", _e)
    from app.routers._record_draft_mock import generate_record_draft, template_draft

router = APIRouter(tags=["records"])

LLM_TIMEOUT_SECONDS = 8.0  # 확정: 초과 시 템플릿 초안으로 200
RECORD_POINTS = 40
COMPLETION_BONUS = 20

Purpose = Literal["portfolio", "hobby", "learning"]


class RecordRequest(BaseModel):
    quest_id: str
    action: Literal["generate", "save"]
    purpose: Purpose = "hobby"
    answers: list[str] = Field(min_length=3, max_length=3)  # 고정 3문항, 빈 값 허용
    attempt: int = 0  # generate 전용 — 다시 생성 최대 2
    final: dict | None = None  # save 전용 — {"title","body","tags"}

    @field_validator("answers")
    @classmethod
    def _max_len(cls, v: list[str]) -> list[str]:
        if any(len(a) > 200 for a in v):
            raise ValueError("답변은 각 200자까지예요")
        return v


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def build_llm_payload(card: dict, purpose: str, answers: list[str]) -> dict:
    """LLM에 보내는 유일한 페이로드 — 활동 내용만. 닉네임·세션ID·퀘스트ID 금지(개인정보 원칙 4)."""
    mission = card.get("mission") or {}
    return {
        "activity_name": card["activity"]["name"],
        "activity_type": card["activity"]["type"],
        "place_name": card["activity"]["place_name"],
        "merchant_name": mission.get("merchant_name"),
        "purpose": purpose,
        "answers": [a.strip() for a in answers],
    }


def _valid_final(final: dict) -> bool:
    """저장 후 읽기 전용(수정 API 없음)이라 오염이 영구 — 타입·상한을 저장 전에 막는다."""
    title, body_, tags = final.get("title"), final.get("body"), final.get("tags")
    return (
        isinstance(title, str) and bool(title.strip()) and len(title) <= 100
        and isinstance(body_, str) and bool(body_.strip()) and len(body_) <= 2000
        and isinstance(tags, list) and len(tags) <= 10
        and all(isinstance(t, str) and t.strip() and len(t) <= 20 for t in tags)
    )


def _get_recordable_quest(db, body: RecordRequest, session_id: str) -> Quest:
    quest = db.get(Quest, body.quest_id)
    if quest is None or quest.session_id != session_id:
        raise _error(404, "NOT_FOUND", "요청한 주소를 찾을 수 없어요")
    if quest.status == "recorded":
        raise _error(409, "ALREADY_RECORDED", "이미 완주한 퀘스트예요")
    if quest.status not in ("started", "stamped"):
        raise _error(400, "QUEST_NOT_STARTED", "퀘스트를 먼저 시작해 주세요")
    return quest


@router.post("/records")
def records(body: RecordRequest, current=Depends(get_current_session), db=Depends(get_db)):
    quest = _get_recordable_quest(db, body, current.id)
    if body.action == "generate":
        # rollback 전에 필요한 값을 로컬로 추출 — rollback이 ORM 속성을 expire시켜
        # 이후 접근이 재조회(커넥션 재점유)가 되는 함정 방지(검수 반영)
        card, quest_id = dict(quest.card), quest.id
        # #7 호출 규약: LLM을 최대 8초 기다리는 동안 요청 커넥션을 쥐고 있으면 풀 고갈 —
        # 여기까지 읽기만 했으므로 반납하고 간다 (cached_call은 자기 커넥션을 쓴다)
        db.rollback()
        return _generate(body, card, quest_id)
    return _save(db, body, quest, current.id)


def _generate(body: RecordRequest, card: dict, quest_id: str) -> dict:
    if body.attempt > 2:
        raise _error(400, "INVALID_ATTEMPT", "다시 생성은 두 번까지예요")
    if body.attempt < 0:
        raise _error(400, "VALIDATION", "입력 값을 확인해 주세요")

    payload = build_llm_payload(card, body.purpose, body.answers)
    fallback = template_draft(payload)

    def fetch():
        # 8초 초과·오류는 cached_call이 받아 fallback으로 — 이 API는 어떤 경우에도 500 금지.
        # with(컨텍스트)를 쓰지 않는 이유: __exit__이 워커 join이라 타임아웃이 벽시계로
        # 안 지켜진다(검수 실측) — shutdown(wait=False)로 즉시 반환
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            return pool.submit(generate_record_draft, payload).result(LLM_TIMEOUT_SECONDS)
        except FutureTimeout:
            raise TimeoutError(f"LLM {LLM_TIMEOUT_SECONDS}초 초과")
        finally:
            pool.shutdown(wait=False)

    key = build_record_cache_key(quest_id, body.purpose, body.answers, body.attempt)
    draft = cached_call(key, fetch, fallback)
    return {"draft": draft, "from_template": draft is fallback}


def _save(db, body: RecordRequest, quest: Quest, session_id: str) -> dict:
    final = body.final or {}
    if not _valid_final(final):
        raise _error(400, "VALIDATION", "입력 값을 확인해 주세요")

    has_stamp = db.scalar(select(Stamp).where(Stamp.quest_id == quest.id)) is not None
    no_mission = quest.merchant_id is None
    answered = any(a.strip() for a in body.answers)

    record = Record(
        id=f"rec_{secrets.token_hex(8)}",
        session_id=session_id,
        quest_id=quest.id,
        purpose=body.purpose,
        answers=[a.strip() for a in body.answers],
        title=final["title"],
        body=final["body"],
        tags=final["tags"],
        verified=has_stamp,
        created_at=now_kst(),
    )

    points_added = RECORD_POINTS if answered else 0  # 전부 빈 값이면 40·20 모두 0 (계약 §5)
    completion_bonus = COMPLETION_BONUS if answered and (has_stamp or no_mission) else 0

    try:
        db.add(record)
        quest.status = "recorded"  # 완주 — 이어하기 배너 소멸(25-screens 5장)
        unlocked = None
        balance = balance_of(db, session_id)
        if points_added:
            balance, u1 = add_points(db, session_id, quest.id, points_added, REASON_RECORD)
            unlocked = unlocked or u1
        if completion_bonus:
            balance, u2 = add_points(db, session_id, quest.id, completion_bonus, REASON_COMPLETION)
            unlocked = unlocked or u2
        db.commit()
    except IntegrityError:  # 동시 저장 경합 — records.quest_id unique 백스톱
        db.rollback()
        raise _error(409, "ALREADY_RECORDED", "이미 완주한 퀘스트예요")

    return JSONResponse(
        status_code=201,
        content={
            "record_id": record.id,
            "points_added": points_added,
            "completion_bonus": completion_bonus,
            "balance": balance,
            "title_unlocked": unlocked,
            "verified": has_stamp,
        },
    )


@router.get("/records")
def list_records(current=Depends(get_current_session), db=Depends(get_db)):
    """보관함 — 계약 §5. 재방문 홈의 잔액·칭호도 이 응답을 쓴다(계약 §0)."""
    rows = db.scalars(
        select(Record).where(Record.session_id == current.id).order_by(Record.created_at.desc())
    ).all()
    balance = balance_of(db, current.id)
    return {
        "records": [
            {
                "record_id": r.id,
                "quest_id": r.quest_id,
                "title": r.title,
                "tags": r.tags,
                "created_at": r.created_at.isoformat(timespec="seconds"),
                "verified": r.verified,
            }
            for r in rows
        ],
        "balance": balance,
        "titles": titles_of(balance),
    }
