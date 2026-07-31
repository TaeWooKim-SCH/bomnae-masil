"""가게 4자리 인증코드 조회 — merchants.verify_code 우선 (#47 시드가 곧 진실).

시드 전(verify_code null)이나 목 카드의 가짜 가게는 결정적 유도 코드로 폴백한다 —
#47 시드가 들어오는 순간 해당 가게는 자동으로 실코드를 쓴다(코드 수정 0줄).
데모 가게 5곳 코드 확정·인쇄 후에는 merchants 재적재 금지(ID 동결 — pipeline/AGENTS.md).
"""
import hashlib
import logging

from sqlalchemy import select

from app.models import Merchant

logger = logging.getLogger("bomnae")


def derived_code(merchant_id: str) -> str:
    """유도 4자리 코드(앞자리 0 보존) — 시드 전·목 가게 전용 폴백. 공개 알고리즘이므로
    실데모 가게는 반드시 #47 시드 코드를 쓴다."""
    n = int(hashlib.sha256(merchant_id.encode()).hexdigest()[:8], 16) % 10000
    return f"{n:04d}"


def merchant_verify_code(db, merchant_id: str) -> str:
    code = db.scalar(select(Merchant.verify_code).where(Merchant.merchant_id == merchant_id))
    if code:
        return code
    if merchant_id.startswith("m_mock_"):  # 목 카드 — 조용히 폴백
        logger.debug("목 가게 유도 코드: %s", merchant_id)
    else:  # 실가게인데 미시드 — 데모 가게라면 인쇄 코드와 어긋나는 사고 신호(#47)
        logger.warning("verify_code 미시드 실가게 — 유도 코드 폴백: %s", merchant_id)
    return derived_code(merchant_id)
