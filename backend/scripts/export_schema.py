#!/usr/bin/env python3
"""모델 → backend/db/schema.sql 생성 (Supabase SQL Editor 붙여넣기용).

사용법: cd backend && python scripts/export_schema.py
schema.sql은 손으로 고치지 않는다 — 모델 수정 후 이 스크립트로 재생성.
출력은 결정적이다(테이블은 의존성·이름순, 인덱스는 이름순) — 모델이 그대로면 diff 0.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.models import Base  # noqa: E402

HEADER = """\
-- 봄내마실 스키마 (R2-01 #4 — ③사용자 5종 + api_cache)
-- 이 파일은 scripts/export_schema.py 가 app/models/ 에서 생성한다. 손으로 고치지 말 것.
-- 적용: Supabase SQL Editor에 전체 붙여넣기 (또는 scripts/verify_r2_01.py 가 create_all로 동일 스키마 생성)

create extension if not exists postgis;

"""


def main() -> None:
    dialect = postgresql.dialect()
    statements: list[str] = []
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda i: i.name):
            statements.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")

    out = BACKEND_ROOT / "db" / "schema.sql"
    out.parent.mkdir(exist_ok=True)
    out.write_text(HEADER + "\n\n".join(statements) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(statements)} statements)")


if __name__ == "__main__":
    main()
