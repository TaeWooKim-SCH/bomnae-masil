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

현재는 버스 정류장·노선, 춘천문화재단 활동 크롤링본을 정제한다. 출력의
`quality_report.json`에서 원본/출력/제외 행 수를 확인한다.
