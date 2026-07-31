# 소상공인365 리포트 수집

## 상권분석 리포트 (현재 사용)

대상: `https://bigdata.sbiz.or.kr/gis/bizonAnls/report/sg/sang_gwon1.sg?...`

사용자가 포털에서 정상적으로 만든 상권분석 리포트 URL을 CSV에 넣으면, 공개 조회
페이지의 원본 HTML과 요약 수치(업소 수·전월 대비·월평균 매출액)를 저장한다. 이 URL은
이미 만들어진 `analyNo`를 **조회**하는 용도다. 수집기는 로그인·캡차 우회나 분석번호
생성을 하지 않는다.

`targets.csv` 예시(UTF-8 또는 UTF-8 BOM):

```csv
region,report_url
춘천시 소양동,https://bigdata.sbiz.or.kr/gis/bizonAnls/report/sg/sang_gwon1.sg?analyNo=116078798&upjongCd=I21201&xcnts=264239&ydnts=487069&center_x=264239&center_y=487069&analyDate=20260731&a=01&b=01&c=01
```

실행:

```powershell
cd pipeline
py -3.11 -m crawl.sbiz_bizon_analysis --targets snapshots/sbiz_bizon_analysis/targets.csv --snapshot-date 2026-07-31
```

- 원본: `snapshots/sbiz_bizon_analysis/raw/*.html`
- CSV: `snapshots/sbiz_bizon_analysis/commercial_area_reports_chuncheon.csv`
- `snapshot_date`는 실행 시각을 코드가 읽지 않도록, 수집자가 명시한다.

### 춘천 25개 행정동 유동인구

`sbiz_bizon_population`은 소상공인365가 제공하는 공식 행정동 중심점으로 동별
리포트를 한 번씩 생성한 뒤, 인구분석의 **행정동 행**만 수집한다. 포털 특성상 업종
값은 리포트 생성에 필요하지만, 추출하는 유동인구는 업종이 아닌 행정동 기준이다.

```powershell
cd pipeline
py -3.11 -m crawl.sbiz_bizon_population --snapshot-date 2026-07-31
```

- 결과: `snapshots/sbiz_bizon_population/chuncheon_dong_floating_population_202504_202604.csv`
- 범위: 25.04~26.04의 월별 일평균 유동인구, 25개 춘천 행정동
- 원본 인구분석 탭: `snapshots/sbiz_bizon_population/raw/*.html`

## 춘천문화예술정보 모아봄 행사 수집

대상: <https://cccf.or.kr/moa>. 카드에 포함된 제목·기간·주소·행정동·연령·분류·요금·상태를
수집하며, 기존 문화재단 `ongoing_events.csv`와 제목 정규화 및 행사기간 겹침 기준으로 중복을
제외한다.

```powershell
cd pipeline
py -3.11 -m crawl.cccf_moabom --existing ..\dataset\ongoing_events.csv --start 2026-08-01 --end 2026-12-31 --snapshot-date 2026-07-31
```

- 전체 모아봄 카드: `snapshots/cccf_moabom/moabom_events_all.csv`
- 기존 문화재단 행사와 중복 제거한 모아봄 신규분: `snapshots/cccf_moabom/moabom_events_new_excluding_existing.csv`
- 기존 + 신규 통합본: `snapshots/cccf_moabom/events_merged_deduplicated.csv`
- 원본 목록 페이지: `snapshots/cccf_moabom/raw/*.html`

## 핫플레이스 리포트 (별도)

대상: <https://bigdata.sbiz.or.kr/#/hotplace/gisDetail>

이 수집기는 자동 로그인·캡차 우회·지도 화면 스크래핑을 하지 않는다. 브라우저에서
`춘천시`로 범위를 선택한 뒤 확인한 보고서 식별자만 `targets.csv`에 넣어, 공식 보고서
응답을 JSON 스냅샷과 CSV로 보관한다.

`targets.csv` 예시(UTF-8 BOM 가능):

```csv
region,theme,mjr_bzznno,anls_no,anls_dt,rptp_info_tpcd
춘천시,MZ,상권번호,분석번호,기준일자,보고서유형
```

실행:

```powershell
cd pipeline
python -m crawl.sbiz_hotplace --targets snapshots/sbiz_hotplace/targets.csv
```

- 응답 원본: `snapshots/sbiz_hotplace/raw/*.json`
- 요약 CSV: `snapshots/sbiz_hotplace/hotplace_reports_chuncheon.csv`
- 지표 CSV: `snapshots/sbiz_hotplace/hotplace_metrics_chuncheon.csv`
- 결과는 모두 Git 제외 경로에 생성한다.
- 사이트가 정상 로그인 세션을 요구하면, 로그인 우회 대신 사용자가 자신의 로컬 환경에만
  `SBIZ_AUTHORIZATION` 값을 설정해 사용한다. 이 값은 코드·CSV·커밋에 넣지 않는다.
