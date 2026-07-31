"""활동×가게 미션 문구를 사전 생성하는 배치 핵심 로직.

실제 PostgreSQL 저장소는 R2가 원천·사전계산 테이블 스키마를 확정한 뒤
``MissionCopyStore`` 규약을 구현해 연결한다. 이 모듈은 그 전에도 가짜 조합으로
프롬프트와 중복 방지 동작을 검증할 수 있다.
"""

import argparse
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
        "과장하거나 구매를 강요하지 마."
    )


def generate_mission_copy_text(prompt: str) -> str | None:
    """미션 문구는 비용 예측을 위해 200토큰 이하로 생성한다."""

    return generate(prompt, max_tokens=200)


def is_plain_mission_copy(copy: str) -> bool:
    """카드에 그대로 넣기 어려운 Markdown 형식은 저장하지 않는다."""

    return not copy.startswith("#") and "**" not in copy


def is_usable_mission_copy(pair: ActivityMerchantPair, copy: str) -> bool:
    """카드 문구에는 활동·가게 식별을 위한 두 이름이 모두 있어야 한다."""

    return (
        is_plain_mission_copy(copy)
        and pair.activity_name in copy
        and pair.merchant_name in copy
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
        if not copy or not is_usable_mission_copy(pair, copy):
            failed_count += 1
            continue

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
    args = parser.parse_args(argv)
    if not args.demo:
        parser.error("실데이터 테이블 준비 전에는 --demo로만 실행할 수 있습니다.")

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
