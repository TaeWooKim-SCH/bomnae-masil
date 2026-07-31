# backend (R2 — services/scoring은 R3, quest_builder·llm은 R4 소유)

## 셋업 (전원 공통 — 처음 1회, 레포 루트에서)

파이썬 **3.11** 기준 (팀 표준 — 루트 `.python-version`). 가상환경은 루트 `.venv` 하나를 backend·pipeline이 같이 쓴다 — 커밋 금지(.gitignore 처리됨).

```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements.lock.txt      # lock이 진실 (없을 때만: -r backend/requirements.txt -r pipeline/requirements.txt)
cp backend/.env.example backend/.env      # DATABASE_URL 실제 값은 팀 비밀 저장소에서 (커밋 금지)
```

- 패키지 추가는 `backend/requirements.txt`(서버 런타임)·`pipeline/requirements.txt`(배치)에 `~=`로 기록 + 단톡 공지 → lock 갱신은 R2가 (`pip freeze > requirements.lock.txt`)
- lock이 바뀌면 각자 `pip install -r requirements.lock.txt` 재실행

## 확인

```bash
cd backend && python scripts/verify_r2_01.py   # DB 접속·PostGIS·테이블·연쇄 삭제 검증 (#4)
```

## 부팅 (스켈레톤 #5 이후)

```bash
cd backend && uvicorn app.main:app --reload
```
