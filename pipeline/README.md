# pipeline (R3)

기본 원본은 Git에서 제외되는 `pipeline/snapshots/`이며, 팀 드라이브의 고정본을
이곳에 복사해 사용한다. 필요하면 `BOMNAE_DATASET_DIR`로 다른 읽기 전용 원본 위치를
지정할 수 있다. 정제 결과는 Git에서 제외되는 `pipeline/output/`에 생성된다. 원본은 절대 수정하지 않는다.
입력은 UTF-8을 먼저 읽고(CP949는 레거시 파일에만 대체 적용), 출력은 Excel
호환 UTF-8 BOM CSV로 생성한다.

```powershell
cd pipeline
python -m load.run_all
```

현재는 버스 정류장·노선·노선별 시간대 승하차, 문화행사, 춘천 상가·춘천사랑상품권 가맹점,
행정동 월별 유동인구를 정제한다. 승하차 정류장 ID는 정류장 위치정보와 다른
체계이므로 `route_hourly.csv`는 노선번호·시간대 집계만 제공한다. 상가 실태와의
매칭 전 모든 상가는 `추정후보`로 표기하며, "확정저유입"으로 단정하지 않는다.
춘천사랑상품권 원본에는 좌표·업종이 없으므로 상가정보와 상호·주소가 **유일하게**
매칭된 행만 `local_currency_merchants.csv`에 적재한다. 불확실하거나 좌표·업종이
없는 행은 제외한다.

필수 원본 파일명은 각 `pipeline/load/*.py`의 `SOURCE` 상수와 같아야 한다.
출력의 `quality_report.json`에서 원본/출력/제외 행 수를 확인한다. 반복 실행은
같은 출력 파일을 재생성하므로 멱등이다. Supabase 적용 전에는
`pipeline/load/schema.sql` 초안을 R2에게 검토받는다.

## 활동 장소 좌표 보강 (#46)

`run_all`은 오프라인 정제만 수행한다. 활동 장소 좌표는 팀 비밀 저장소에서 받은
`KAKAO_REST_API_KEY`를 **로컬 환경변수로만** 넣은 뒤 별도 실행한다. 키와 지오코딩
캐시는 Git에 올리지 않는다.

```powershell
$env:KAKAO_REST_API_KEY = "팀 비밀 저장소의 값"
python -m pipeline.load.geocode_activities
```

성공 행은 `pipeline/output/activities_geocoded.csv`에 WGS84 좌표와 함께 생성된다.
주소를 찾지 못했거나 유효하지 않은 좌표는 적재 대상에서 제외되며,
`activity_geocode_cache.csv`에서 확인할 수 있다.

## 접근성 점수표 (#10)

활동 좌표 보강 후 아래 배치를 실행하면 정류장×활동지 조합의 단일 경로 원천인
`pipeline/output/accessibility_scores.csv`가 생성된다.

```powershell
python -m pipeline.load.accessibility_scores
```

- 활동지 반경 500m 안의 하차 정류장만 후보로 삼고, 같은 `route_id`에서 승차
  순서가 하차 순서보다 앞선 경우만 `no_transfer=true`로 인정한다.
- `ride_min`은 해당 노선 구간의 좌표 누적거리 ÷ **18km/h**로 올림 추정한다.
  `walk_min`은 하차 후 거리 ÷ **80m/분(4.8km/h)** 으로 올림 추정한다. 배차,
  시각표, 실시간, 막차 정보는 저장하거나 사용하지 않는다.
- 경로가 없는 조합도 `no_transfer=false`, `score=0`으로 한 행을 남긴다. 따라서
  정류장 직접 선택과 동 단위 대표 정류장 선택은 이 표를 `SELECT` 한 번으로만
  조회하며, 추천 요청 시 경로를 재계산하지 않는다.
- `score`는 0~100 정규화 값이다. 최단 경로의 하차 도보시간(70%)과 해당 조합의
  직행 노선번호 수(30%, 최대 5개)를 합산한다. 추천 점수의 접근성 20점은 이 값을
  조회해 사용한다.

대표 조회도 경로 계산 없이 아래처럼 표 한 번만 읽는다.

```sql
-- 사용자가 정류장을 직접 선택한 경우
SELECT * FROM accessibility_scores
WHERE activity_id = :activity_id AND board_stop_id = :stop_id AND no_transfer = true;

-- 동만 선택한 경우: 활동별 최고 점수 정류장 하나를 대표로 선택
SELECT * FROM accessibility_scores
WHERE activity_id = :activity_id AND zone_code = :zone_code AND no_transfer = true
ORDER BY score DESC, duration_min ASC
LIMIT 1;
```

R2가 동결 계약대로 테이블을 만든 뒤에는 아래 명령으로 DB 적재를 실행한다. 적재기는
CSV 계약·복합 키를 먼저 검사하고, 임시 테이블에서 행 수를 검증한 뒤 한 트랜잭션으로
기존 점수표를 교체한다.

```powershell
python -m pipeline.load.load_accessibility_scores --rebuild
```

`DATABASE_URL`은 `backend/.env` 또는 실행 환경에만 둔다. 실제 접속값·생성된 CSV는
Git에 올리지 않는다.

## 관심사 칩·행정동 정규화 (#48)

`pipeline/seeds/activity_interest_mapping.csv`는 활동 분류·제목 키워드를 API 계약의
고정 7종 칩으로 연결한다. `run_all`은 문화행사에 `interest_tags`를 부여하며, 상시형
씨드는 원본의 같은 컬럼을 검증해 그대로 사용한다. 어느 규칙에도 맞지 않는 활동은
태그를 비워 관심사 점수에서 중간값(기타)으로 처리한다. 새 칩을 만들지 않는다.

행정동 경계와 접근성 점수표는 `42110…` 코드를 기준으로 한다. 인구·유동인구 원본의
이전 춘천 코드 `51110…`은 같은 읍·면·동 접미사를 보존한 채 `42110…`으로 정규화해
`GET /zones`의 이름·인구 조인이 일치하도록 한다.

동 이름과 정류장명 조회에 필요한 원천 테이블은 아래 명령으로 실제 DB에 적재한다.

```powershell
python -m pipeline.load.load_zone_reference
```
