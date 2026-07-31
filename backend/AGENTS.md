# backend/ — 소유권이 셋으로 나뉜다

- `app/routers/`·`app/models/`·인프라 = **R2(김태우)**. 특히 `models/`는 R2만 수정
- `app/services/scoring/` = **R3(최우혁)** — 순수 함수, FastAPI import 금지
- `app/services/quest_builder/`·`app/services/llm/` = **R4(최서준)** — scoring은 호출만, 무환승·경로는 접근성 점수표 조회만
- import 방향: routers → quest_builder → scoring (역방향 금지)
- API 요청·응답 형식은 `docs/30-api-contract.md` 동결본과 글자 단위로 일치해야 한다. 잔액은 별도 API 없이 세션·인증·기록 응답의 `balance` 필드
- 포인트 적립은 상태 전이에서만: stamped +40 / recorded +40(문답 1개 이상) / 완주 +20 → point_ledger 기록
- 인증은 멱등(재인증=성공 응답), 영수증 사진은 저장하지 않는다, 시각은 기준 시각 유틸(DEMO_NOW)만
- DB 접속은 Supabase Session pooler URI. LLM에 이름·소속 등 식별정보 전송 금지
- **파이썬은 반드시 루트 `.venv` 가상환경에서 실행** — 시스템 파이썬에 pip install 금지. 패키지 추가는 `backend/requirements.txt` 기록+단톡 공지, lock 파일(`requirements.lock.txt`)이 있으면 그것으로 설치

## 환경 (전원 공통)

- 파이썬 **3.11**(`.python-version`) + 각자 로컬 `backend/.venv` 가상환경 — 셋업 절차는 `README.md`. 가상환경·캐시는 커밋하지 않는다
- 의존성의 진실은 `requirements.txt` 하나, 전부 정확 버전 고정(`==`) — **직접 추가·변경 금지.** 패키지가 필요하면 R2(태우)에게 이슈·단톡으로 요청하고, 파일이 바뀌면 각자 `pip install -r requirements.txt` 재실행
- `.env`는 `.env.example`을 복사해 만들고 실제 값(DATABASE_URL·API 키)은 팀 비밀 저장소에서 받는다 — 커밋 절대 금지(공개 레포)
