#!/usr/bin/env python3
"""R2-04(#7) 완료 조건 검증 — cached_call·CACHE_ONLY·키 규칙.

사용법: cd backend && python scripts/verify_r2_04.py  (backend/.env의 DATABASE_URL 사용)
여러 번 실행해도 안전하다(검증 키는 record:q_r2_04_verify* 만 쓰고 시작·종료 시 정리).
"""
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from app.core.cache import build_record_cache_key, cached_call  # noqa: E402
from app.db import get_engine  # noqa: E402

PREFIX = "record:q_r2_04_verify"
fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def cleanup() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("delete from api_cache where cache_key like :p"), {"p": PREFIX + "%"})


def main() -> None:
    os.environ["CACHE_ONLY"] = "0"
    cleanup()

    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"draft": {"title": "검증", "body": "본문", "tags": ["검증"]}}

    fallback = {"draft": {"title": "템플릿", "body": "기본", "tags": []}, "from_template": True}
    key = build_record_cache_key("q_r2_04_verify", "hobby", ["새로웠어요", "", ""], 0)

    # 1. 미스 → 외부 호출 1회 + 저장
    v1 = cached_call(key, fetch, fallback)
    check("미스 시 외부 호출 1회 + 원본 반환", calls["n"] == 1 and v1["draft"]["title"] == "검증")

    # 2. 히트 → 외부 호출 0회, 저장분 반환
    v2 = cached_call(key, fetch, fallback)
    check("히트 시 외부 호출 0회 + 저장분 반환", calls["n"] == 1 and v2["draft"]["title"] == "검증")

    # 3. CACHE_ONLY=1 + 빈 캐시 → 외부 호출 0회, fallback, 예외 없음
    os.environ["CACHE_ONLY"] = "1"
    key_miss = build_record_cache_key("q_r2_04_verify", "hobby", ["다른답"], 0)
    v3 = cached_call(key_miss, fetch, fallback)
    check("CACHE_ONLY=1 미스 → fallback (호출 0회)", calls["n"] == 1 and v3 is fallback)

    # 4. CACHE_ONLY=1 + 캐시 있음 → 저장분 반환 (여전히 호출 0회)
    v4 = cached_call(key, fetch, fallback)
    check("CACHE_ONLY=1 히트 → 저장분 반환", calls["n"] == 1 and v4["draft"]["title"] == "검증")

    # 5. 외부 호출 실패 → fallback (죽지 않음)
    os.environ["CACHE_ONLY"] = "0"

    def boom():
        calls["n"] += 1
        raise RuntimeError("LLM down")

    v5 = cached_call(build_record_cache_key("q_r2_04_verify", "hobby", ["실패"], 0), boom, fallback)
    check("외부 호출 예외 → fallback (죽지 않음)", v5 is fallback and calls["n"] == 2)

    # 6. 키 규칙(#38): 같은 입력=같은 키, 구성 요소 4개 각각 하나만 달라도 다른 키, 공백 정규화
    k = build_record_cache_key("q_r2_04_verify", "hobby", ["a", "", ""], 0)
    check(
        "키 규칙 — 결정성·구성 요소 4개 반영·공백 정규화",
        k == build_record_cache_key("q_r2_04_verify", "hobby", [" a ", "", ""], 0)
        and k != build_record_cache_key("q_r2_04_verify", "hobby", ["b", "", ""], 0)
        and k != build_record_cache_key("q_r2_04_verify", "hobby", ["a", "", ""], 1)
        and k != build_record_cache_key("q_r2_04_verify", "portfolio", ["a", "", ""], 0)
        and k != build_record_cache_key("q_other", "hobby", ["a", "", ""], 0),
    )

    # 7. fetch가 None 반환 → fallback + 캐시 미저장 (재호출 시 또 미스)
    def none_fetch():
        calls["n"] += 1
        return None

    key_none = build_record_cache_key("q_r2_04_verify", "hobby", ["없음"], 0)
    v7a = cached_call(key_none, none_fetch, fallback)
    v7b = cached_call(key_none, none_fetch, fallback)
    check("None 반환 → fallback + 미저장", v7a is fallback and v7b is fallback and calls["n"] == 4)

    # 8. fetch가 fallback 자체를 반환 → 저장 안 함 (캐시 오염 방지)
    def fb_fetch():
        calls["n"] += 1
        return fallback

    key_fb = build_record_cache_key("q_r2_04_verify", "hobby", ["폴백"], 0)
    v8 = cached_call(key_fb, fb_fetch, fallback)
    with get_engine().connect() as conn:
        polluted = conn.execute(
            text("select 1 from api_cache where cache_key in (:a, :b)"),
            {"a": key_fb, "b": key_none},
        ).first()
    check("fallback 반환 → fallback + 캐시 오염 없음", v8 is fallback and polluted is None)

    # 9. 미스·히트 반환 형태 동일 (JSON 왕복 — int 키는 str로 통일)
    key_shape = build_record_cache_key("q_r2_04_verify", "hobby", ["형태"], 0)
    m = cached_call(key_shape, lambda: {1: "x"}, fallback)
    h = cached_call(key_shape, lambda: {1: "x"}, fallback)
    check("미스·히트 반환 형태 동일(JSON 왕복)", m == h == {"1": "x"})

    # 10. 직렬화 불가 payload → 죽지 않고 원본 반환 + 미저장
    marker = object()
    key_bad = build_record_cache_key("q_r2_04_verify", "hobby", ["직렬화"], 0)
    v10 = cached_call(key_bad, lambda: {"t": marker}, fallback)
    check("직렬화 불가 → 죽지 않고 원본 반환", isinstance(v10, dict) and v10.get("t") is marker)

    cleanup()
    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("R2-04 검증 전부 통과 — #7 완료 조건 충족 (get_db 통일은 #5의 app/db.py)")


if __name__ == "__main__":
    main()
