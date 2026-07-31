# backend (R2 — services/scoring은 R3, quest_builder·llm은 R4 소유)

## 셋업 (전원 공통 — 처음 1회)

파이썬 **3.11** 기준 (팀 표준 — `.python-version`). 가상환경은 각자 로컬에 만들고 커밋하지 않는다(.gitignore 처리됨).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # DATABASE_URL 실제 값은 팀 비밀 저장소에서 (커밋 금지)
```

- 의존성은 `requirements.txt` 정확 버전 고정(==)으로만 관리 — 추가·변경은 R2에게 요청
- requirements.txt가 바뀌면 각자 `pip install -r requirements.txt` 재실행

## 확인

```bash
python scripts/verify_r2_01.py   # DB 접속·PostGIS·테이블·연쇄 삭제 검증 (#4)
```

## 부팅 (스켈레톤 #5 이후)

```bash
uvicorn app.main:app --reload
```
