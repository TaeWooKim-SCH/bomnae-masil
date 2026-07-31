# build_quests 계약 — R4 → R2

> 상태: **R2 리뷰 대기**. R2 승인 후 이 문서 상단에 `동결됨(YYYY-MM-DD)`을 기록한다.
>
> 정본: API 카드 필드는 [`30-api-contract.md` §3](30-api-contract.md#3-추천)의 `QuestCard`다. 이 문서는 그 카드를 만드는 `build_quests`의 입력·반환·빈 결과 규칙만 고정한다.

## 1. 역할과 소유 경계

`build_quests`는 R4 소유 조립 함수다. R2 라우터가 입력과 R3의 사전 계산 결과를 전달하면, 이 함수는 순위가 매겨진 카드 **최대 6장**과 완화 정보를 반환한다.

| 책임 | 소유자 |
|---|---|
| 후보 걸러내기, 활동·미션·경로·점수 결과를 카드로 조립, 4단계 완화 | R4 `build_quests` |
| 점수 산식과 무환승 접근성·경로 결과 계산 | R3 (`scoring` 공개 함수·접근성 점수표) |
| `quest_id`·`recommendation_id` 발급, 카드 스냅샷 저장, API 응답의 `quests`(1~3위)·`more`(4~6위) 분리 | R2 라우터 |

- `build_quests`는 DB·FastAPI를 import하지 않는다.
- `quest_id`는 이 함수가 만들지 않는다. 반환 카드에는 API `QuestCard`의 필드를 같은 이름으로 담되, R2가 `quest_id`를 붙여 API 응답으로 확정한다.
- R3가 제공한 `route`·`score` 값은 조회·전달만 한다. 무환승 여부·소요시간·점수 산식은 다시 계산하지 않는다.

## 2. 입력 모델

아래는 Pydantic 모델로 구현할 때의 고정 필드다. HTTP 요청의 앞 다섯 필드는 API 계약 §3과 동일하며, `exclude_activity_ids`는 R2가 세션에서 조회해 내부 호출에 추가한다.

```python
class OriginInput(BaseModel):
    zone_code: str
    stop_id: str | None


class TimeWindowInput(BaseModel):
    start: datetime
    end: datetime


class BuildQuestsInput(BaseModel):
    interests: list[InterestChip]
    origin: OriginInput
    time_window: TimeWindowInput
    max_budget_krw: int | None
    exclude_activity_ids: list[str]
```

| 필드 | 타입 | 규칙 | 예시 |
|---|---|---|---|
| `interests` | `list[InterestChip]` | 1~3개. 아래 7종 enum만 사용 | `["사진·미디어", "문화·공연"]` |
| `origin.zone_code` | `str` | 행정동 필수 | `"4211056000"` |
| `origin.stop_id` | `str \| None` | 사용자가 2단 선택에서 정류장을 고른 경우만 값. `null`이면 활동지별 최적 정류장을 접근성 점수표에서 조회 | `null` / `"stp_1041"` |
| `time_window.start` | ISO 8601 `datetime` | 오늘 날짜의 이용 시작 | `"2026-08-01T14:00"` |
| `time_window.end` | ISO 8601 `datetime` | 시작보다 60분 이상 뒤인 이용 종료 | `"2026-08-01T18:00"` |
| `max_budget_krw` | `int \| None` | `0` 무료만 / `10000` / `30000` / `50000` / `null` 상관없음 | `30000` |
| `exclude_activity_ids` | `list[str]` | 이 세션에서 이미 `started` 또는 `recorded`인 활동 ID. R2가 세션에서 조회해 전달 | `["a_12", "a_88"]` |

`InterestChip` enum은 아래 7개로 고정한다.

```text
운동·건강 / 문화·공연 / 공예·만들기 / 사진·미디어 /
요리·먹거리 / 학습·어학 / 자연·나들이
```

## 3. 반환 모델

```python
class RelaxedInfo(BaseModel):
    steps: list[Literal["budget", "interest", "always_open", "revisit"]]
    message: str  # 항상 "조건을 조금 넓혀 찾았어요"


class BuildQuestsResult(BaseModel):
    cards: list[QuestCardDraft]  # 1~6장, 점수 내림차순
    relaxed: RelaxedInfo | None
```

- `cards`의 1~3번째는 R2가 API 응답 `quests`로, 4~6번째는 `more`로 분리한다.
- `cards`는 3장(최대 6장)을 목표로 조립하고, 4단계 완화 후에도 활동 주변 가게가 없으면 `mission: null`인 가게 없는 퀘스트를 만든다. **완화를 모두 소진해도 후보가 0이면 `cards: []`가 정상 반환이다** (8/1 ②급 결정 — §4-2 빈 결과 규약·30-계약 §3 참조).
- `QuestCardDraft`는 API `QuestCard`에서 `quest_id`를 제외한 같은 필드·같은 타입이다. R2가 ID를 주입한 뒤 API `QuestCard`가 된다.
- `relaxed`가 `null`이면 최초 조건으로 찾은 결과다. 하나라도 완화했으면 적용한 모든 단계를 순서대로 기록한다.
- 네 단계가 모두 적용된 경우는 `{"steps": ["budget", "interest", "always_open", "revisit"], "message": "조건을 조금 넓혀 찾았어요"}`로 반환한다.

### 카드 조립 규칙

| 영역 | 고정 규칙 |
|---|---|
| `activity` | `name`, `type`, `place_name`, `schedule_text`, `price_krw`, `d_day`를 API 정본과 같은 이름으로 사용. `d_day`는 신청형만 값이 있고, 화면 문구는 **개강 D-n**이며 마감일이 아니다. |
| `mission` | 가게가 있으면 `merchant_id`, `merchant_name`, 사전 생성 `copy`, `expected_spend_krw`. 가게가 없으면 `null`. |
| `route` | R3 접근성 점수표의 `board_stop_name`, `route_no`, `stops_count`, `ride_min`, `walk_min`, `no_transfer`, `basis_note`를 그대로 사용. 배차간격·시각표·실시간·막차 필드는 만들지 않는다. |
| `budget_total_krw` | 활동비 + 미션 예상 소비 + 버스 왕복 3,000원. 미션 예상 소비: 카페 7,000원 / 음식점 12,000원 / 소매 5,000원 / 기타 8,000원. 가게 없는 퀘스트는 활동비 + 3,000원. |
| `score.breakdown` | `market` 최대 30, `interest` 최대 25, `access` 최대 20, `time` 최대 15, `budget` 최대 10. `total`은 R3 공개 점수 결과를 사용한다. |
| `max_points` | 가게 미션이 있으면 `100`, 없으면 기록 40 + 완주 20의 `60`. |
| `revisit` | 완화 4단계에서만 `true`; 그 외 `false`. |

### 반환 예시 1 — 선택 정류장이 없는 일반 퀘스트

```json
{
  "cards": [
    {
      "title": "저녁의 필름카메라 입문",
      "activity": {
        "name": "필름카메라 입문 강좌",
        "type": "신청형",
        "place_name": "춘천시평생학습관",
        "schedule_text": "오늘 19:00–21:00",
        "price_krw": 10000,
        "d_day": 5
      },
      "mission": {
        "merchant_id": "m_12",
        "merchant_name": "육림고개 ○○카페",
        "copy": "강좌 끝나고 필름 감성 그대로, 따뜻한 한 잔 어때요?",
        "expected_spend_krw": 7000
      },
      "route": {
        "board_stop_name": "석사동 현진아파트",
        "route_no": "300",
        "stops_count": 7,
        "ride_min": 25,
        "walk_min": 8,
        "no_transfer": true,
        "basis_note": "석사동 현진아파트 정류장 기준"
      },
      "budget_total_krw": 20000,
      "score": {
        "total": 86,
        "breakdown": {"market": 26, "interest": 22, "access": 17, "time": 13, "budget": 8}
      },
      "max_points": 100,
      "revisit": false,
      "refs": {"activity_id": "a_88", "board_stop_id": "stp_1041", "alight_stop_id": "stp_2210"}
    }
  ],
  "relaxed": null
}
```

### 반환 예시 2 — 주변 가게가 없는 퀘스트

```json
{
  "cards": [
    {
      "title": "박물관 상설전 느긋하게 보기",
      "activity": {
        "name": "국립춘천박물관 상설전 관람",
        "type": "상시형",
        "place_name": "국립춘천박물관",
        "schedule_text": "운영시간 내 자유 관람 (10:00~18:00)",
        "price_krw": 0,
        "d_day": null
      },
      "mission": null,
      "route": {
        "board_stop_name": "후평동 행정복지센터",
        "route_no": "12",
        "stops_count": 5,
        "ride_min": 18,
        "walk_min": 6,
        "no_transfer": true,
        "basis_note": null
      },
      "budget_total_krw": 3000,
      "score": {
        "total": 72,
        "breakdown": {"market": 0, "interest": 23, "access": 18, "time": 15, "budget": 10}
      },
      "max_points": 60,
      "revisit": false,
      "refs": {"activity_id": "a_112", "board_stop_id": "stp_301", "alight_stop_id": "stp_478"}
    }
  ],
  "relaxed": {"steps": ["always_open"], "message": "조건을 조금 넓혀 찾았어요"}
}
```

## 4. 후보·빈 결과 규칙

### 4-1. 하드 필터 — 순위를 매기기 전에 모두 적용

1. **이동 가능**: R3 접근성 점수표에 무환승 경로가 있어야 한다 (`no_transfer: true`).
2. **시간 내 가능**: `[도보 + 고정 버퍼 10분 + 승차 + 활동 시간]` 전체가 사용자의 이용 시간 창 안에 들어와야 한다. 시작 시각이 정해진 활동은 시작 10분 전까지 도착 가능해야 하며, 상시·기간형도 실제 이용 가능한 활동 시간을 확보해야 한다. 막차는 검증하지 않는다.
3. **예산 내**: `budget_total_krw`가 현재 예산 상한 이하여야 한다. `0`은 무료 활동만, `null`은 예산 필터를 적용하지 않는다.
4. **접수 가능**: 신청형은 접수 마감 전이어야 한다.
5. **기존 활동 제외**: `exclude_activity_ids`에 든, 이 세션에서 이미 시작·완주한 활동은 제외한다.

### 4-2. 카드가 부족할 때의 완화 — 반드시 이 순서

완화는 카드가 3장에 못 미칠 때 다음 순서로 누적 적용한다. 적용한 단계는 `relaxed.steps`에 순서대로 넣는다.

1. `budget`: 예산 상한을 30% 올린다.
2. `interest`: 관심사 조건을 확대한다.
3. `always_open`: 상시 개방 활동을 대체 후보로 넣는다.
4. `revisit`: 필터 ⑤만 해제한다. 이 단계로 다시 들어온 카드에는 `revisit: true`를 설정한다.

**이동 가능·시간 필터는 어떤 단계에서도 완화하지 않는다.** 따라서 추천된 버스 경로는 항상 무환승으로 실행 가능해야 한다.

4단계 후에도 활동 주변에 가게가 없으면 가게를 억지로 붙이지 않는다. `mission: null`, `max_points: 60`인 가게 없는 퀘스트로 반환한다.

**빈 결과 (8/1 ②급 결정, 태우)**: 4단계를 모두 소진해도 후보가 0이면 `cards: []`를 반환한다 — `relaxed.steps`에 적용한 전 단계, `relaxed.message`에 "지금 조건에 맞는 활동이 없어요". 원칙: **서버는 이동·시간을 몰래 완화하지 않는다 — 대신 화면이 사용자에게 조건 변경을 제안한다** (심야 시간 창처럼 후보 0이 정답인 입력이 실존하므로, 억지 추천이 아니라 정직한 빈 상태가 맞다). 시연 입력에서 빈 결과 0건 보장은 #13 검증이 담당한다.

## 5. R2 연결 절차

1. R2는 홈 입력을 `BuildQuestsInput` 형태로 검증하고, 세션에서 `exclude_activity_ids`를 조회해 전달한다.
2. R4는 카드 최대 6장과 `relaxed`를 반환한다.
3. R2는 카드에 `quest_id`를 발급하고 스냅샷을 저장한 뒤, 1~3위를 `quests`, 4~6위를 `more`에 넣어 API 계약 §3 응답을 만든다.
4. 이 계약 변경은 R2 승인과 단톡 공지 후에만 가능하다.
