"""가게 4자리 인증코드의 모의 리졸버 — merchants 테이블(①원천)·코드 시드(#47·R3-10) 전까지만.

실데이터가 적재되면 merchant_code()를 merchants.verify_code 조회로 교체한다 — 호출부(verify.py)는
이 함수 하나만 쓰므로 교체 지점은 여기 한 곳이다. 코드는 merchant_id에서 결정적으로 유도되어
(같은 가게 → 항상 같은 4자리) 검증 스크립트·화면 테스트가 예측 가능하다.
"""
import hashlib


def merchant_code(merchant_id: str) -> str:
    """가게별 4자리 코드 (문자열 — 앞자리 0 보존)."""
    n = int(hashlib.sha256(merchant_id.encode()).hexdigest()[:8], 16) % 10000
    return f"{n:04d}"
