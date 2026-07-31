"""DB 접속 통로 — 서버 전체가 이 파일 하나로 Supabase에 붙는다. 캐시 프록시는 #7에서 추가.

DATABASE_URL은 반드시 Session pooler URI (Direct connection은 배포 서버에서 IPv6 문제).
"""
import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@lru_cache(maxsize=1)
def get_engine():
    url = os.environ["DATABASE_URL"]
    # pool_pre_ping: 죽은 pooler 접속 자동 감지(#7 지정), connect_timeout: health가 매달리지 않게
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@lru_cache(maxsize=1)
def _session_factory():
    return sessionmaker(bind=get_engine())


def get_db():
    """FastAPI 의존성 — 요청마다 세션 하나. 라우터는 전부 이걸 통해서만 DB를 쓴다."""
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()
