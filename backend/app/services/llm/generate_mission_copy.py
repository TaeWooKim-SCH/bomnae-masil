"""활동×가게 미션 문구를 사전 생성하는 배치 핵심 로직.

실제 PostgreSQL 저장소는 R2가 원천·사전계산 테이블 스키마를 확정한 뒤
``MissionCopyStore`` 규약을 구현해 연결한다. 이 모듈은 그 전에도 가짜 조합으로
프롬프트와 중복 방지 동작을 검증할 수 있다.
"""

import argparse
import os
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from app.services.llm.adapter import generate


PairKey = tuple[str, str]
Generator = Callable[[str], str | None]


@dataclass(frozen=True)
class ActivityMerchantPair:
    """AI에 전달 가능한 활동·가게 조합. 개인정보 필드는 포함하지 않는다."""

    activity_id: str
    activity_name: str
    merchant_id: str
    merchant_name: str
    merchant_category: str

    @property
    def key(self) -> PairKey:
        return (self.activity_id, self.merchant_id)


@dataclass(frozen=True)
class MissionCopy:
    activity_id: str
    merchant_id: str
    copy: str


@dataclass(frozen=True)
class BatchResult:
    created_count: int
    skipped_count: int
    failed_count: int


class MissionCopyStore(Protocol):
    """mission_copy 테이블 어댑터가 구현할 최소 저장소 규약."""

    def has_pair(self, key: PairKey) -> bool:
        """이미 문구가 저장된 활동×가게 조합인지 반환한다."""

    def save(self, mission_copy: MissionCopy) -> None:
        """새 문구를 영속 저장한다."""


class DatabaseCursor(Protocol):
    def __enter__(self) -> "DatabaseCursor": ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None: ...

    def fetchone(self) -> tuple[bool] | None: ...

    def fetchall(self) -> list[tuple[str, str, str, str, str]]: ...


class DatabaseConnection(Protocol):
    def cursor(self) -> DatabaseCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


def connect_database(database_url: str) -> DatabaseConnection:
    """Open a PostgreSQL connection only for real batch execution."""

    import psycopg2

    return psycopg2.connect(database_url, connect_timeout=10)


class PostgresMissionCopyStore:
    """실제 mission_copy 테이블용, 조합 키 기준 멱등 저장소."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def has_pair(self, key: PairKey) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM mission_copy
                    WHERE activity_id = %s AND merchant_id = %s
                )
                """,
                key,
            )
            row = cursor.fetchone()
        return bool(row and row[0])

    def save(self, mission_copy: MissionCopy) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO mission_copy (activity_id, merchant_id, copy)
                VALUES (%s, %s, %s)
                ON CONFLICT (activity_id, merchant_id) DO NOTHING
                """,
                (
                    mission_copy.activity_id,
                    mission_copy.merchant_id,
                    mission_copy.copy,
                ),
            )


def load_nearby_activity_merchant_pairs(
    connection: DatabaseConnection,
    *,
    limit_per_activity: int = 10,
    total_limit: int = 20,
) -> list[ActivityMerchantPair]:
    """활동별 반경 500m~1km 내 최근접 가게 후보를 제한 수만큼 읽는다."""

    if limit_per_activity < 1 or total_limit < 1:
        raise ValueError("candidate limits must be positive")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH distances AS (
                SELECT
                    a.activity_id,
                    a.name AS activity_name,
                    m.merchant_id,
                    m.name AS merchant_name,
                    m.category AS merchant_category,
                    6371000 * acos(least(1.0, greatest(-1.0,
                        cos(radians(a.latitude)) * cos(radians(m.latitude)) *
                        cos(radians(m.longitude) - radians(a.longitude)) +
                        sin(radians(a.latitude)) * sin(radians(m.latitude))
                    ))) AS distance_m
                FROM activities AS a
                CROSS JOIN merchants AS m
                WHERE a.latitude IS NOT NULL
                  AND a.longitude IS NOT NULL
            ),
            nearby AS (
                SELECT *
                FROM distances
                WHERE distance_m BETWEEN %s AND %s
            ),
            ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY activity_id
                    ORDER BY distance_m, merchant_id
                ) AS candidate_rank
                FROM nearby
            )
            SELECT activity_id, activity_name, merchant_id, merchant_name, merchant_category
            FROM ranked
            WHERE candidate_rank <= %s
            ORDER BY random()
            LIMIT %s
            """,
            (500, 1000, limit_per_activity, total_limit),
        )
        rows = cursor.fetchall()

    return [ActivityMerchantPair(*row) for row in rows]


@dataclass
class InMemoryMissionCopyStore:
    """실DB 테이블 준비 전 테스트·드라이런용 저장소."""

    existing_keys: set[PairKey] = field(default_factory=set)
    saved_copies: list[MissionCopy] = field(default_factory=list)

    def has_pair(self, key: PairKey) -> bool:
        return key in self.existing_keys

    def save(self, mission_copy: MissionCopy) -> None:
        self.existing_keys.add((mission_copy.activity_id, mission_copy.merchant_id))
        self.saved_copies.append(mission_copy)


def build_mission_prompt(pair: ActivityMerchantPair) -> str:
    """활동·가게의 공개 정보만 사용해 1~2문장 미션 문구를 요청한다."""

    return (
        "봄내마실의 지역 방문 퀘스트에 넣을 자연스러운 미션 문구를 작성해줘.\n"
        f"활동명: {pair.activity_name}\n"
        f"가게명: {pair.merchant_name}\n"
        f"가게 업종: {pair.merchant_category}\n\n"
        "출력은 한국어 평문 정확히 한 문장만 사용해. 제목·마크다운·따옴표 없이 문구만 출력해. "
        "반드시 활동명과 가게명을 각각 그대로 한 번씩 포함하고, 활동을 먼저 한 뒤 가게를 방문하는 "
        "순서로 자연스럽게 제안해. 사실로 사용할 수 있는 정보는 활동명·가게명·업종뿐이야. "
        "입력에 없는 위치·상품·역사·관계·운영정보·이벤트·할인·혜택을 만들지 말고, "
        "과장하거나 구매를 강요하지 마. "
        "활동명·가게명·업종 외의 사실을 절대 덧붙이지 마. "
        "활동을 마친 뒤 가게에 들러 오늘의 경험을 한 줄로 기록하는 일반적인 제안만 작성해."
    )


def generate_mission_copy_text(prompt: str) -> str | None:
    """미션 문구는 비용 예측을 위해 200토큰 이하로 생성한다."""

    return generate(prompt, max_tokens=200)


def is_plain_mission_copy(copy: str) -> bool:
    """카드에 그대로 넣기 어려운 Markdown 형식은 저장하지 않는다."""

    return not copy.startswith("#") and "**" not in copy


def is_usable_mission_copy(pair: ActivityMerchantPair, copy: str) -> bool:
    """카드 문구에는 활동·가게 식별을 위한 두 이름이 모두 있어야 한다."""

    normalized_copy = unicodedata.normalize("NFKC", copy)
    normalized_activity_name = unicodedata.normalize("NFKC", pair.activity_name)
    normalized_merchant_name = unicodedata.normalize("NFKC", pair.merchant_name)
    return (
        is_plain_mission_copy(copy)
        and normalized_activity_name in normalized_copy
        and normalized_merchant_name in normalized_copy
    )


def build_exact_name_fallback(pair: ActivityMerchantPair) -> str:
    """모델이 원본 이름을 바꾼 경우에만 사용하는 안전한 한 문장 문구."""

    return (
        f"{pair.activity_name} 활동을 마친 뒤 {pair.merchant_name}에 들러 "
        "오늘의 경험을 한 줄로 기록해보세요."
    )


def generate_missing_mission_copies(
    pairs: Iterable[ActivityMerchantPair],
    store: MissionCopyStore,
    generator: Generator = generate_mission_copy_text,
) -> BatchResult:
    """이미 저장된 조합을 건너뛰고, 유효한 새 문구만 저장한다."""

    created_count = 0
    skipped_count = 0
    failed_count = 0

    for pair in pairs:
        if store.has_pair(pair.key):
            skipped_count += 1
            continue

        try:
            generated = generator(build_mission_prompt(pair))
        except Exception:
            failed_count += 1
            continue

        copy = (generated or "").strip()
        if not copy or not is_plain_mission_copy(copy):
            failed_count += 1
            continue

        if not is_usable_mission_copy(pair, copy):
            copy = build_exact_name_fallback(pair)

        store.save(
            MissionCopy(
                activity_id=pair.activity_id,
                merchant_id=pair.merchant_id,
                copy=copy,
            )
        )
        created_count += 1

    return BatchResult(
        created_count=created_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )


def demo_pairs() -> tuple[ActivityMerchantPair, ...]:
    """실데이터 적재 전 배치 동작을 확인하는 가짜 10개 조합."""

    return (
        ActivityMerchantPair("demo-a-01", "드라이런 전시 관람", "demo-m-01", "드라이런 카페", "카페"),
        ActivityMerchantPair("demo-a-02", "드라이런 공원 산책", "demo-m-02", "드라이런 서점", "소매"),
        ActivityMerchantPair("demo-a-03", "드라이런 사진 전시", "demo-m-03", "드라이런 식당", "음식점"),
        ActivityMerchantPair("demo-a-04", "드라이런 공방 체험", "demo-m-04", "드라이런 공방 상점", "소매"),
        ActivityMerchantPair("demo-a-05", "드라이런 문화 해설", "demo-m-05", "드라이런 찻집", "카페"),
        ActivityMerchantPair("demo-a-06", "드라이런 강변 걷기", "demo-m-06", "드라이런 빵집", "음식점"),
        ActivityMerchantPair("demo-a-07", "드라이런 미술 감상", "demo-m-07", "드라이런 문구점", "소매"),
        ActivityMerchantPair("demo-a-08", "드라이런 지역사 탐방", "demo-m-08", "드라이런 식료품점", "기타"),
        ActivityMerchantPair("demo-a-09", "드라이런 소규모 공연", "demo-m-09", "드라이런 디저트 카페", "카페"),
        ActivityMerchantPair("demo-a-10", "드라이런 도서관 방문", "demo-m-10", "드라이런 독립서점", "소매"),
    )


def run_demo_dry_run(
    generator: Generator = generate_mission_copy_text,
) -> tuple[BatchResult, tuple[MissionCopy, ...]]:
    """가짜 10조합을 DB에 쓰지 않고 메모리에서 끝까지 생성한다."""

    store = InMemoryMissionCopyStore()
    result = generate_missing_mission_copies(demo_pairs(), store, generator)
    return result, tuple(store.saved_copies)


def run_real_batch(
    *,
    limit: int,
    generator: Generator = generate_mission_copy_text,
) -> BatchResult:
    """Generate and store a limited number of real database pairs."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for real mode")

    connection = connect_database(database_url)
    try:
        pairs = load_nearby_activity_merchant_pairs(
            connection, limit_per_activity=10, total_limit=limit
        )
        result = generate_missing_mission_copies(
            pairs, PostgresMissionCopyStore(connection), generator
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(
    argv: list[str] | None = None,
    generator: Generator = generate_mission_copy_text,
) -> int:
    """가짜 10개 조합을 DB 저장 없이 실행하는 명령 진입점."""

    parser = argparse.ArgumentParser(description="mission_copy 사전 생성 배치")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="가짜 활동·가게 10개 조합을 메모리에서 생성합니다.",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="실제 DB의 활동·가게 조합을 mission_copy에 저장합니다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="실데이터 모드의 최대 처리 조합 수입니다. 기본값은 20입니다.",
    )
    args = parser.parse_args(argv)
    if args.demo == args.real:
        parser.error("--demo 또는 --real 중 하나를 선택해야 합니다.")
    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")

    if args.real:
        try:
            result = run_real_batch(limit=args.limit, generator=generator)
        except Exception:
            print("SUMMARY mode=real created=0 skipped=0 failed=1")
            return 1
        print(
            "SUMMARY mode=real "
            f"created={result.created_count} "
            f"skipped={result.skipped_count} "
            f"failed={result.failed_count}"
        )
        return 0 if result.failed_count == 0 else 1

    result, copies = run_demo_dry_run(generator)
    print(
        "SUMMARY "
        f"created={result.created_count} "
        f"skipped={result.skipped_count} "
        f"failed={result.failed_count}"
    )
    for copy in copies:
        print(f"{copy.activity_id}/{copy.merchant_id}: {copy.copy}")
    return 0 if result.failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
