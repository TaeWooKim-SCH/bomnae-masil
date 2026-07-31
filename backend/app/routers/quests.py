"""퀘스트 상세·시작 라우터 — 계약 §4 (#57).

- 상세: 스냅샷 QuestCard 원본 + status·started_at + coords(refs 조인 — R2 소유)
- 시작: recommended|abandoned → started 전이. 동시 진행 1개(진행 중 = started·stamped),
  충돌 시 409 QUEST_IN_PROGRESS(+current_quest_id), abandon_current=true면 기존 건 abandoned
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.coords import resolve_coords
from app.core.kpi import record_first_start, record_quest_started
from app.db import get_db
from app.deps import get_current_session
from app.models import Quest
from app.timebase import now_kst

router = APIRouter(prefix="/quests", tags=["quests"])

# 진행 중 판정 — stamped는 started의 후속 상태(기록 대기 중)라 포함 (5-1 상태 모델)
_IN_PROGRESS = ("started", "stamped")


def _not_found() -> HTTPException:
    return HTTPException(404, detail={"code": "NOT_FOUND", "message": "요청한 주소를 찾을 수 없어요"})


def _get_own_quest(db, quest_id: str, session_id: str, for_update: bool = False) -> Quest:
    quest = db.get(Quest, quest_id, with_for_update=for_update)
    if quest is None or quest.session_id != session_id:  # 남의 퀘스트도 동일 404 — 존재 비노출
        raise _not_found()
    return quest


@router.get("/{quest_id}")
def quest_detail(quest_id: str, current=Depends(get_current_session), db=Depends(get_db)):
    quest = _get_own_quest(db, quest_id, current.id)
    return {
        **quest.card,
        "status": quest.status,
        "started_at": quest.started_at.isoformat(timespec="seconds") if quest.started_at else None,
        "coords": resolve_coords(db, quest.card),
    }


class StartRequest(BaseModel):
    abandon_current: bool = False


@router.post("/{quest_id}/start")
def start_quest(
    quest_id: str,
    body: StartRequest,
    current=Depends(get_current_session),
    db=Depends(get_db),
):
    # 행 잠금 — 같은 퀘스트 동시 start를 직렬화해 KPI 이벤트 중복 적재 방지(검수 반영).
    # 패자는 잠금 해제 후 최신 상태(started)를 읽어 멱등 200으로 빠진다
    quest = _get_own_quest(db, quest_id, current.id, for_update=True)

    if quest.status in _IN_PROGRESS:
        # 자기 재진입은 멱등 200 — stamped를 409로 막으면 계약의 복구 경로(abandon 재요청)가
        # 자기 자신에겐 영원히 실패하는 막다른 길이 된다(검수 반영). 진행을 되돌리지 않는다.
        if quest.started_at is None:  # 데이터 이상 자가치유 (status·started_at 짝 깨짐 방어)
            quest.started_at = now_kst()
            db.commit()
        return {"status": "started", "started_at": quest.started_at.isoformat(timespec="seconds")}
    if quest.status == "recorded":
        raise HTTPException(409, detail={"code": "ALREADY_RECORDED", "message": "이미 완주한 퀘스트예요"})

    in_progress = list(
        db.scalars(
            select(Quest)
            .where(
                Quest.session_id == current.id, Quest.status.in_(_IN_PROGRESS), Quest.id != quest.id
            )
            .order_by(Quest.started_at.desc())  # current = 가장 최근 시작 건 (이어하기 정의와 동일)
        )
    )
    if in_progress:
        if not body.abandon_current:
            raise HTTPException(
                409,
                detail={
                    "code": "QUEST_IN_PROGRESS",
                    "message": "진행 중인 퀘스트가 있어요",
                    "current_quest_id": in_progress[0].id,
                },
            )
        for q in in_progress:  # 확인 모달 후 재요청 — 기존 건 중단 처리
            q.status = "abandoned"
        db.flush()  # 중단을 먼저 반영 — 부분 유니크 인덱스(진행 중 1건)의 일시 위반 방지

    first_ever_start = quest.started_at is None  # abandoned 재시작은 이미 센 퀘스트 — 중복 집계 방지
    # 조회는 변이 전에 — 변이 후 SELECT는 autoflush로 유니크 위반을 try 밖에서 터뜨린다(검수 반영)
    session_first = first_ever_start and (
        db.scalar(
            select(func.count())
            .select_from(Quest)
            .where(
                Quest.session_id == current.id,
                Quest.started_at.is_not(None),
                Quest.id != quest.id,
            )
        )
        == 0
    )
    quest.status = "started"
    quest.started_at = now_kst()
    if first_ever_start:
        # 익명 KPI(#36): started 이벤트 + 세션의 첫 시작이면 탐색 시간(간격만 저장 — 익명)
        record_quest_started(db, has_mission=quest.merchant_id is not None)
        search_min = (quest.started_at - current.created_at).total_seconds() / 60
        if session_first and search_min > 0:
            # 간격 0 = DEMO_NOW 고정 상태의 산출물 — 실측이 아니므로 중앙값에 넣지 않는다(검수 반영)
            record_first_start(db, search_min)
    try:
        db.commit()
    except IntegrityError:
        # 동시 start 경합 — DB 백스톱(uq_quests_one_in_progress)이 승자를 정한다. 패자는 409
        db.rollback()
        winner = db.scalars(
            select(Quest)
            .where(
                Quest.session_id == current.id, Quest.status.in_(_IN_PROGRESS), Quest.id != quest_id
            )
            .order_by(Quest.started_at.desc())
        ).first()
        detail = {"code": "QUEST_IN_PROGRESS", "message": "진행 중인 퀘스트가 있어요"}
        if winner is not None:
            detail["current_quest_id"] = winner.id
        raise HTTPException(409, detail=detail)
    return {"status": "started", "started_at": quest.started_at.isoformat(timespec="seconds")}
