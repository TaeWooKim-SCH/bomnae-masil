# backend/ — 소유권이 셋으로 나뉜다

- `app/routers/`·`app/models/`·인프라 = **R2(김태우)**. 특히 `models/`는 R2만 수정
- `app/services/scoring/` = **R3(최우혁)** — 순수 함수, FastAPI import 금지
- `app/services/quest_builder/`·`app/services/llm/` = **R4(최서준)** — scoring은 호출만, 무환승·경로는 접근성 점수표 조회만
- import 방향: routers → quest_builder → scoring (역방향 금지)
- API 요청·응답 형식은 `docs/30-api-contract.md` 동결본과 글자 단위로 일치해야 한다. 잔액은 별도 API 없이 세션·인증·기록 응답의 `balance` 필드
- 포인트 적립은 상태 전이에서만: stamped +40 / recorded +40(문답 1개 이상) / 완주 +20 → point_ledger 기록
- 인증은 멱등(재인증=성공 응답), 영수증 사진은 저장하지 않는다, 시각은 기준 시각 유틸(DEMO_NOW)만
- DB 접속은 Supabase Session pooler URI. LLM에 이름·소속 등 식별정보 전송 금지
