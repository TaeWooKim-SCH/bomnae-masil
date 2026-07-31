"""봄내마실 서버 진입점 — 스켈레톤(#5): health 하나로 화면↔서버↔DB 배선을 검증한다.

부팅(로컬): 레포 루트에서 `source .venv/bin/activate` 후 `cd backend && uvicorn app.main:app --reload`
배포(Cloudtype): `uvicorn app.main:app --host 0.0.0.0 --port 8000`
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 라우터·서비스 import보다 먼저 — DATABASE_URL 등이 이 시점에 준비된다.
# 배포 환경(Cloudtype)은 실제 환경변수 사용 — load_dotenv는 기존 값을 덮어쓰지 않는다.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.errors import ErrorEnvelopeMiddleware, install_error_handlers  # noqa: E402
from app.timebase import now_kst  # noqa: E402

now_kst()  # DEMO_NOW 오타를 부팅 시점에 잡는다 (형식 오류면 여기서 RuntimeError로 즉사)

app = FastAPI(title="봄내마실 API")
install_error_handlers(app)


def _cors_origins() -> list[str]:
    """CORS_ORIGINS: 쉼표 구분. 끝 슬래시는 항상 오류라(#5 함정) 방어적으로 제거한다."""
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


# 순서 중요: ErrorEnvelope를 먼저 추가해야 CORS가 최외곽이 되어 500 응답에도 CORS 헤더가 붙는다
app.add_middleware(ErrorEnvelopeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")  # 계약 0장: Base = /api


@api.get("/health")
def health():
    """계약 §7 — {"ok": true, "db": true, "demo_now": "..."}. demo_now는 DEMO_NOW 설정 시 그 값."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok, "demo_now": now_kst().isoformat(timespec="seconds")}


app.include_router(api)

# 배포 확인·서버 깨우기용 별칭 — 계약 경로는 /api/health 하나다
app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)
