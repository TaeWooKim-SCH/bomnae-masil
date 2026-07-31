#!/usr/bin/env python3
"""실조인 교체 검증 (#9 적재 후) — coords·가게 코드가 실데이터를 읽는지 + 폴백 생존.

사용법: cd backend && python scripts/verify_real_joins.py
임시 시드는 verify_code가 비어 있는 가게만 골라서 쓰고, 원래 값(null)을 캡처해 그대로 원복한다
— #47 시드(인쇄 코드·ID 동결)를 절대 건드리지 않는다.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session as OrmSession  # noqa: E402

from app.core.coords import resolve_coords  # noqa: E402
from app.core.merchant_codes import merchant_verify_code  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.core.merchant_codes import derived_code  # noqa: E402

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        act = conn.execute(
            text("select activity_id, latitude, longitude from activities where latitude is not null limit 1")
        ).first()
        stop_a, stop_b = conn.execute(
            text("select stop_id, latitude, longitude from bus_stops limit 2")
        ).fetchall()
        # 시드된 데모 가게(#47 — 인쇄 코드·ID 동결)를 건드리지 않도록 미시드 행만 선택
        mer = conn.execute(
            text(
                "select merchant_id, latitude, longitude, verify_code from merchants "
                "where verify_code is null limit 1"
            )
        ).first()
    original_code = mer[3]  # 원값 캡처(선택 조건상 null) — finally에서 이 값 그대로 원복

    card = {
        "refs": {"activity_id": act[0], "board_stop_id": stop_a[0], "alight_stop_id": stop_b[0]},
        "mission": {"merchant_id": mer[0]},
    }
    with OrmSession(engine) as db:
        # 1. 실좌표 조인 — DB 값 그대로 반환
        c = resolve_coords(db, card)
        check(
            "coords 실조인 — activity·stops·merchant DB 좌표 일치",
            c["activity"] == {"lat": float(act[1]), "lng": float(act[2])}
            and c["board_stop"] == {"lat": float(stop_a[1]), "lng": float(stop_a[2])}
            and c["alight_stop"] == {"lat": float(stop_b[1]), "lng": float(stop_b[2])}
            and c["mission"] == {"lat": float(mer[1]), "lng": float(mer[2])}
            and c["path"] == [[c["board_stop"]["lat"], c["board_stop"]["lng"]], [c["alight_stop"]["lat"], c["alight_stop"]["lng"]]],
            str(c),
        )

        # 2. 모르는 id(목 카드) → 결정적 폴백, 죽지 않음
        mock_card = {
            "refs": {"activity_id": "a_mock_1", "board_stop_id": "stp_none_x", "alight_stop_id": "stp_none_y"},
            "mission": None,
        }
        f1 = resolve_coords(db, mock_card)
        f2 = resolve_coords(db, mock_card)
        check(
            "모르는 id → 결정적 폴백 좌표 (mission null 유지)",
            f1 == f2 and f1["mission"] is None and all(isinstance(f1[k]["lat"], float) for k in ("activity", "board_stop", "alight_stop")),
        )

        # 3. 가게 코드 — 시드 전 폴백(유도 코드) / 시드 후 DB 우선
        code_before = merchant_verify_code(db, mer[0])
        check("verify_code 미시드 → 유도 코드 폴백", code_before == derived_code(mer[0]))

    with engine.begin() as conn:  # 임시 시드 → DB 우선 확인 → 원복
        conn.execute(text("update merchants set verify_code = '9999' where merchant_id = :m"), {"m": mer[0]})
    try:
        with OrmSession(engine) as db:
            check("verify_code 시드 → DB 코드 우선", merchant_verify_code(db, mer[0]) == "9999")
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("update merchants set verify_code = :c where merchant_id = :m"),
                {"c": original_code, "m": mer[0]},
            )

    with OrmSession(engine) as db:
        check("원복 후 다시 폴백", merchant_verify_code(db, mer[0]) == derived_code(mer[0]))

    print()
    if fails:
        print(f"FAIL: {fails}")
        sys.exit(1)
    print("실조인 교체 검증 전부 통과 — #47 시드가 들어오면 코드 수정 없이 실코드 사용")


if __name__ == "__main__":
    main()
