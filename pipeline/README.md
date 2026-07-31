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
