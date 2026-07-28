# 봄내마실 (Bomnae Masil)

> 시민 활동과 골목상권을 연결하는 생활권 미션 매칭 서비스
> 팀 마사모 · 2026 춘천시 데이터 활용 해커톤 「춘천해답」 본선 (7.31~8.1, 춘천 ICT벤처센터)

## 문서 (Day 0 필독)

| 문서 | 내용 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 · 데이터 모델 · API · 시연 안정성 |
| [docs/TEAM_ROLES.md](docs/TEAM_ROLES.md) | 4인 역할 분담 · 스윔레인 · 협업 규칙 |
| [docs/REPO_WORKFLOW.md](docs/REPO_WORKFLOW.md) | 브랜치 · 이슈 · 마일스톤 운영 |
| docs/API_CONTRACT.md | (작성 예정 — Day 0 동결 대상) |
| docs/DEMO_SCENARIO.md | (작성 예정 — 데모 대본) |

## 구조

```
frontend/   R1 — React + Kakao Maps (시민 화면 5종 + 정책 대시보드)
backend/    R2 — FastAPI (services/scoring은 R3, quest_builder·llm은 R4 소유)
pipeline/   R3 — 공공데이터 10종 수집·정제·적재 + 파생 테이블 배치
docs/       설계 문서
```

## 부팅 (각 디렉토리 README에 1줄씩 유지할 것 — 백업 페어 인수 조건)

- frontend: `cd frontend && npm i && npm run dev`
- backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- pipeline: `cd pipeline && python -m load.run_all`
- 로컬 폴백 스택: `docker compose up`
