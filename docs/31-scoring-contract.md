# 점수·접근성 계약 v1 — R3 → R4

> 상태: **R4 리뷰 대기**. R4 승인 코멘트와 팀 공지 후 `동결됨(YYYY-MM-DD)`으로
> 바꾼다. 동결 후 변경은 R3 승인과 팀 공지가 필요하다.
>
> 정본: 카드 응답의 `score.breakdown` 및 `route` 필드명은
> [`30-api-contract.md`](30-api-contract.md#3-추천)다. 이 문서는 R3 점수 함수와
> 접근성 점수표를 조회하는 방법을 고정한다.

## 1. 소유 경계

- R3는 접근성 표를 배치로 만들고, `calculate_score` 순수 함수를 제공한다.
- R4 `build_quests`는 이 문서의 입력을 전달하고 반환값을 카드에 조립한다. 경로,
  무환승 여부, 접근성 점수는 다시 계산하지 않는다.
- R2는 확정된 테이블을 읽는 모델·저장소와 API를 소유한다. DB 모델 변경은 R2만 한다.

## 2. 점수 함수

```python
def calculate_score(input: ScoreInput) -> ScoreResult:
    """Return the five weighted ranking components for one eligible candidate."""
```

`ScoreInput`은 이미 하드 필터를 통과한 활동·가게 조합 하나를 표현한다. 이동 가능,
시간, 예산, 접수, 기존 활동 제외의 하드 필터는 R4의 책임이며 이 함수는 순위만 만든다.

```python
class ScoreInput(TypedDict):
    activity_id: str
    interests: list[str]                 # API의 고정 7종 칩, 1~3개
    activity_interest_tags: list[str]    # 활동에 부여된 같은 7종 태그
    merchant_inflow_status: str | None   # 확정저유입 | 추정후보 | 일반 | 붐빔 | None
    access_score: float                  # accessibility_scores.score, 0~100
    time_fit_ratio: float                # 이동+활동 뒤 남는 시간의 비율, 0~1
    budget_fit_ratio: float              # 예산 안에서의 적합도, 0~1


class ScoreBreakdown(TypedDict):
    market: int      # 0~30
    interest: int    # 0~25
    access: int      # 0~20
    time: int        # 0~15
    budget: int      # 0~10


class ScoreResult(TypedDict):
    total: int       # breakdown 합계, 0~100
    breakdown: ScoreBreakdown
```

| 구성 | 배점 | 입력·의미 |
|---|---:|---|
| `market` | 0~30 | `확정저유입`을 가장 높게, 측정 이력 없는 `추정후보`는 중간값으로 취급한다. `일반`·`붐빔`은 더 낮다. |
| `interest` | 0~25 | 사용자 칩과 활동 태그의 규칙 매칭 결과다. |
| `access` | 0~20 | `access_score / 100 × 20`을 반올림한다. `no_transfer=false` 행은 하드 필터에서 이미 제외한다. |
| `time` | 0~15 | `time_fit_ratio × 15`를 반올림한다. |
| `budget` | 0~10 | `budget_fit_ratio × 10`을 반올림한다. |

점수는 각 항목을 정수 반올림한 뒤 더한다. 따라서 `total`은 반드시 다섯
`breakdown` 값의 합과 같다.

### 반환 예시

```json
{
  "total": 86,
  "breakdown": {
    "market": 26,
    "interest": 22,
    "access": 17,
    "time": 13,
    "budget": 8
  }
}
```

## 3. `accessibility_scores` 표

행 키는 **`(activity_id, board_stop_id)`**다. 즉 활동 장소 하나와 사용자가 탈 정류장
하나의 조합을 한 행으로 저장한다. 모든 정류장×활동 조합을 저장하며, 경로가 없는
경우에도 행을 생략하지 않는다.

| 컬럼 | 형식 | 규칙 |
|---|---|---|
| `activity_id` | text | 활동 식별자. 복합 기본 키 구성원. |
| `board_stop_id` | text | 승차 정류장 식별자. 복합 기본 키 구성원. |
| `zone_code` | text nullable | 승차 정류장이 속한 행정동. 동 단위 대표 조회에 사용한다. 경계 밖 정류장은 null이다. |
| `score` | numeric | 0~100 접근성 정규화 값. 경로 불가 행은 0. |
| `no_transfer` | boolean | 같은 방향의 한 노선으로 갈 수 있으면 true. |
| `best_route_id` | text nullable | 최단 후보의 내부 노선 식별자. |
| `route_no` | text nullable | 카드에 보일 노선번호. `best_route_id`와 같은 선택 결과다. |
| `alight_stop_id` | text nullable | 최단 후보의 하차 정류장. |
| `stops_count` | integer nullable | 승차→하차 정거장 수. 배차간격 컬럼은 없다. |
| `ride_min` | integer nullable | 좌표 누적거리 기반 추정 승차 시간(분). 화면은 “약”으로 표기한다. |
| `walk_min` | integer nullable | 하차 후 활동지까지 추정 도보 시간(분). |
| `duration_min` | integer nullable | `ride_min + walk_min`. 고정 대기 버퍼 10분은 포함하지 않는다. |

### 경로 불가 행

`no_transfer=false`, `score=0`이며 `best_route_id`, `route_no`, `alight_stop_id`,
`stops_count`, `ride_min`, `walk_min`, `duration_min`은 모두 null이다. 이 행은 “아직
계산하지 않음”이 아니라 “무환승 경로 없음”을 뜻한다.

### 계산 근거

- 활동지 500m 이내 정류장만 하차 후보로 삼는다.
- 같은 `route_id`에서 승차 정류장 순서가 하차 정류장 순서보다 앞설 때만 무환승이다.
- `ride_min`은 노선 구간 좌표 누적거리 ÷ 18km/h, `walk_min`은 도보거리 ÷ 80m/분으로
  올림 추정한다.
- 배차간격·시각표·실시간·막차는 데이터에 없으므로 표에도 저장하지 않는다. 시간
  적합 판정은 R4가 고정 버퍼 10분을 별도로 더한다.

## 4. 조회 규칙

무환승 판별·경로·소요시간은 반드시 이 표를 조회한다. 다른 코드가 재계산하면 안 된다.

```sql
-- 정류장을 직접 선택한 경우
SELECT *
FROM accessibility_scores
WHERE activity_id = :activity_id
  AND board_stop_id = :stop_id
  AND no_transfer = true;

-- 동만 선택한 경우: 해당 활동에 가장 좋은 정류장 한 곳을 대표로 쓴다.
SELECT *
FROM accessibility_scores
WHERE activity_id = :activity_id
  AND zone_code = :zone_code
  AND no_transfer = true
ORDER BY score DESC, duration_min ASC, board_stop_id ASC
LIMIT 1;
```

- 두 조회 모두 표를 한 번만 읽고, 추천 시점의 경로 계산은 없다.
- 동 단위 대표 조회의 `board_stop_id`는 API 카드 `refs.board_stop_id`와 화면의
  “○○ 정류장 기준” 문구 근거다.
- `GET /zones`의 “경로 보유 동”은 `zone_code is not null and no_transfer=true`인
  표 행이 하나 이상인 동만 반환한다.

## 5. R4 리뷰 체크

- `ScoreResult.breakdown` 필드가 API 계약의 `market/interest/access/time/budget`와
  정확히 일치하는지
- `route_no`, `stops_count`, `ride_min`, `walk_min`, `no_transfer`만으로 카드의 버스
  문구를 조립할 수 있는지
- 동 단위·정류장 직접 선택이 모두 표 조회만으로 처리되는지
