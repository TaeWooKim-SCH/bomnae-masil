"""활동×가게 미션 문구를 사전 생성하는 배치 핵심 로직.

실제 PostgreSQL 저장소는 R2가 원천·사전계산 테이블 스키마를 확정한 뒤
``MissionCopyStore`` 규약을 구현해 연결한다. 이 모듈은 그 전에도 가짜 조합으로
프롬프트와 중복 방지 동작을 검증할 수 있다.
"""

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
        "출력은 한국어 1~2문장만 사용해. 활동 뒤 가게를 자연스럽게 방문하도록 제안하되, "
        "없는 할인·혜택·이벤트·운영정보를 만들지 말고 과장하거나 구매를 강요하지 마."
    )


def generate_missing_mission_copies(
    pairs: Iterable[ActivityMerchantPair],
    store: MissionCopyStore,
    generator: Generator = generate,
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
        if not copy:
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
