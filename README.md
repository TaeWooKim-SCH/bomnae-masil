# 봄내마실 (Bomnae Masil)

> 시민 활동과 골목상권을 연결하는 생활권 미션 매칭 서비스
> 팀 마사모 · 2026 춘천시 데이터 활용 해커톤 「춘천해답」 본선 (7.31~8.1, 춘천 ICT벤처센터)

## 문서 — 이 순서로 읽으세요

| 순서 | 문서 | 내용 | 대상 |
|---|---|---|---|
| 1 | [docs/00-overview.md](docs/00-overview.md) | 우리가 뭘 만드는가 (기획 요약) | 전원 필독 |
| 2 | [docs/20-team.md](docs/20-team.md) | 누가 뭘 하고, 어떻게 협업하는가 | 전원 필독 |
| 3 | [docs/10-architecture.md](docs/10-architecture.md) | 어떻게 만드는가 (시스템 설계) | 개발 착수 전 |
| 3.5 | [docs/15-data.md](docs/15-data.md) | 공공데이터 10종 상세 목록 (수집 기준) | R3 필독 |
| 3.7 | [docs/25-screens.md](docs/25-screens.md) | 페이지별 기능 정의서 (화면 6종 요소·상태·문구) | R1 필독 |
| 4 | docs/30-api-contract.md | 화면↔서버 약속 (작성 예정 — Day 0 동결) | R1·R2·R4 |
| 5 | docs/40-demo.md | 데모 대본 (작성 예정) | R4 주관 |

공식 제출 기획서(PDF)는 대회 제출본이며, 내용 요약은 00-overview에 있다.

## 구조

```
frontend/   R1 — React + 카카오맵 (화면 6종)
backend/    R2 — FastAPI (services/scoring은 R3, quest_builder·llm은 R4 소유)
pipeline/   R3 — 공공데이터 10종 수집·정리·적재
docs/       설계 문서
```

## 부팅 (각 폴더 README에 1줄씩 유지 — 백업 페어 인수 조건)

- frontend: `cd frontend && npm i && npm run dev`
- backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- pipeline: `cd pipeline && python -m load.run_all`
- 오프라인 스택: `docker compose up`
