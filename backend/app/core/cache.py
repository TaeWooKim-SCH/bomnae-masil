"""캐시 프록시 — 외부 호출 응답을 api_cache에 저장해 재사용한다 (#7).

10-architecture 8장 "데모가 죽지 않게 하는 장치"의 부품이다:
- 이 서비스의 외부 호출은 **LLM 활동 기록 생성 하나뿐** — api_cache에는 그것만 들어간다.
  버스(TAGO)용 캐시는 만들지 않는다(완전 불사용 확정, #39 종결)
- `CACHE_ONLY=1`이면 외부 호출을 절대 하지 않는다 — 캐시 미스면 fallback 반환 (죽지 않는 게 목표)
- 캐시에는 가공 전 원본 응답(JSON)을 저장한다 — 가공 로직이 바뀌어도 캐시가 살아남는다

캐시 키 규칙 (#38 확정, ②급 결정·태우):
  quest_id + 용도(purpose) + 정규화 답변 해시 + 시도 번호(attempt)
  → build_record_cache_key()가 유일한 키 조립 창구다.
  quest_id 없는 순수 내용 해시는 폐기 — 빈 문답을 허용하는 설계라 서로 다른 퀘스트가
  같은(빈) 답변일 때 엉뚱한 초안을 재생하기 때문. 같은 퀘스트·같은 입력 → 같은 키
  = 리허설 때 채운 저장분이 본 시연에서 그대로 재생되는 근거.

호출 시점 주의(#35): cached_call은 get_db 요청 세션과 별개로 같은 풀에서 커넥션을 하나 더
쓴다 — 요청 세션이 트랜잭션(커넥션)을 쥔 채 부르면 동시 요청이 많을 때 풀 고갈 교착이
가능하다. 라우터는 DB 조회를 끝내(커밋/반납) 후 cached_call을 부를 것.
"""
import hashlib
import json
import logging
import os
from typing import Any, Callable

from sqlalchemy import text

from app.db import get_engine
from app.timebase import now_kst

logger = logging.getLogger("bomnae")


def cache_only() -> bool:
    """CACHE_ONLY=1 → 외부 호출 전면 금지 모드 (비상 스위치, #42에서 최종 점검)."""
    return os.environ.get("CACHE_ONLY", "0") == "1"


def build_record_cache_key(quest_id: str, purpose: str, answers: list[str], attempt: int) -> str:
    """LLM 활동 기록 캐시 키 — #38 규칙. answers는 공백 정돈만 하고 빈 값은 빈 값 그대로 둔다."""
    normalized = [(a or "").strip() for a in answers]
    digest = hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()[:16]
    return f"record:{quest_id}:{purpose}:{digest}:{attempt}"


def cached_call(key: str, fetch_fn: Callable[[], Any], fallback: Any) -> Any:
    """키가 있으면 저장분, 없으면 fetch_fn 호출 후 저장. 어떤 실패에도 예외를 밖으로 내지 않는다.

    호출부 계약(#35 from_template의 근거):
    - 반환값이 fallback(동일 객체)이면 폴백이 일어난 것이다. fallback은 불변(읽기 전용)으로
      취급하고, 반환값을 변형해야 하면 복사해서 쓸 것(모듈 상수 오염 방지)
    - fetch_fn이 None이나 fallback 자체를 반환하면 실패로 간주해 저장하지 않는다(캐시 오염 방지)
    - 반환 형태는 미스·히트 모두 JSON 왕복본으로 동일하다(예: int 키 → str) — 첫 요청과
      재요청이 다른 모양을 받는 일이 없다
    - 같은 키 동시 미스는 외부 호출이 중복될 수 있으나, 반환·저장은 먼저 저장된 쪽으로 수렴한다
    """
    engine = get_engine()

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("select payload from api_cache where cache_key = :k"), {"k": key}
            ).first()
        if row is not None and row[0] is not None:
            return row[0]
    except Exception:
        logger.exception("캐시 조회 실패 — 계속 진행: %s", key)

    if cache_only():
        logger.info("cache miss + CACHE_ONLY=1 → fallback: %s", key)
        return fallback

    try:
        payload = fetch_fn()
    except Exception:
        logger.exception("외부 호출 실패 → fallback: %s", key)
        return fallback
    if payload is None or payload is fallback:
        logger.warning("외부 호출이 빈 결과/fallback을 반환 → 저장 안 함: %s", key)
        return fallback

    try:
        serialized = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.exception("payload 직렬화 불가 → 저장 안 함, 원본 반환: %s", key)
        return payload

    try:
        # raw SQL 유지 — ORM(JSONB 컬럼 타입) 경로로 바꾸면 json.dumps와 이중 인코딩되니 주의
        with engine.begin() as conn:
            inserted = conn.execute(
                text(
                    "insert into api_cache (cache_key, payload, created_at) "
                    "values (:k, :p, :t) on conflict (cache_key) do nothing returning payload"
                ),
                {"k": key, "p": serialized, "t": now_kst()},
            ).first()
        if inserted is not None:
            return inserted[0]
        # 경합 패배 — 같은 키는 항상 같은 저장분을 재생해야 하므로 승자 것을 반환
        with engine.connect() as conn:
            row = conn.execute(
                text("select payload from api_cache where cache_key = :k"), {"k": key}
            ).first()
        if row is not None and row[0] is not None:
            return row[0]
    except Exception:
        logger.exception("캐시 저장 실패 — 응답은 유효, 계속 진행: %s", key)

    return json.loads(serialized)
