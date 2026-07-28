# 봄내마실 레포 운영·이슈 관리 v1.0

> 전제: 무박 2일(30시간), 4명 전원이 한 공간에 모여 진행.
> 이 문서는 `TEAM_ROLES.md`의 역할 경계를 Git·GitHub 위에서 기계적으로 강제하는 방법이다.

---

## 1. 왜 모노레포 하나인가 (멀티레포를 쓰지 않는 이유)

"AI(R3·R4)가 백엔드의 서비스 계층에 접근해야 하니 레포를 나눠야 하나?"라는 고민은 자연스럽지만, 답은 반대다:

| 선택지 | 30시간 해커톤에서의 실제 비용 |
|---|---|
| 멀티레포 (frontend / backend / pipeline 분리) | scoring·quest_builder를 백엔드가 쓰려면 패키지 배포 또는 `pip install git+...` — **버전 동기화 지옥**. "R3가 푸시했는데 백엔드는 옛날 버전" 문제가 통합 1·2마다 재발. 해커톤이 무너지는 지점은 통합인데, 레포 경계가 늘수록 통합 지점이 늘어난다 |
| **모노레포 (채택)** | R3·R4의 코드가 `backend/app/services/` 안에 살아도 문제없음 — **소유권은 디렉토리 단위로, 경계는 import 방향 규칙으로** 지킨다 (아래 2장). 클론 하나, 브랜치 하나, 통합은 머지 한 번 |

핵심 인식: R3·R4가 백엔드 *레포*에 접근하는 게 아니라, 백엔드 *프로세스 안에서 실행되는 자기 소유 패키지*를 개발하는 것이다. 경계는 저장소가 아니라 패키지 경계다.

## 2. 백엔드 내부의 경계 — import 방향 규칙

```
routers (R2)  →  quest_builder (R4)  →  scoring (R3)
     │                  │                    │
     └── models/ (R2 단일 관리) ── DB 헬퍼·캐시 프록시 (R2 제공)
```

**규칙 (Day 0 전원 합의):**

1. 의존은 **한 방향**: `routers → services`, `quest_builder → scoring`. 역방향 import 금지
2. `services/` 하위 패키지는 **FastAPI를 import하지 않는다** (순수 Python — 이미 ARCHITECTURE 원칙 3)
3. 각 서비스 패키지의 공개 인터페이스는 `__init__.py`에 노출된 함수뿐 — 남의 패키지 내부 모듈을 직접 import하지 않는다 (`from app.services.scoring import score` ⭕ / `from app.services.scoring.impl.walk import ...` ❌)
4. `models/`(스키마)와 `requirements.txt` 추가는 R2 창구 — 의존성 추가는 한 줄 PR로 즉시, 스키마 변경은 계약 절차로

이 4줄이 지켜지면 R2·R3·R4가 같은 `backend/` 안에서 일해도 파일 충돌이 구조적으로 안 난다.

## 3. CODEOWNERS — 소유권의 기계적 강제

`.github/CODEOWNERS` (GitHub ID는 실제 계정으로 교체):

```
# 기본: 팀장 확인
*                                       @seojun-choi

/frontend/                              @woohyuk-choi
/backend/                               @taewoo-kim
/backend/app/services/scoring/          @seojun-choi
/backend/app/services/quest_builder/    @youngchan-woo
/backend/app/services/llm/              @youngchan-woo
/pipeline/                              @seojun-choi
/docs/API_CONTRACT.md                   @taewoo-kim
/docs/                                  @seojun-choi
```

효과: PR을 열면 해당 디렉토리 소유자가 자동으로 리뷰어 지정됨 — "누구한테 물어봐야 하지"가 사라진다. 브랜치 보호에서 CODEOWNERS 리뷰 필수는 **켜지 않는다** (30시간에 전건 필수 리뷰는 병목 — TEAM_ROLES 5장 규칙과 일치: 계약 4종·models/만 리뷰 필수, 자기 디렉토리는 셀프 머지).

## 4. 브랜치 전략 — 트렁크 기반, 수명 반나절

- `main` 하나만 보호 (force-push 금지, 삭제 금지 정도의 가벼운 보호)
- 작업은 `feat/<이슈번호>-<역할>-<요약>` (예: `feat/23-r4-quest-builder-v1`) — **수명 반나절 이하**
- 머지는 **squash merge** 통일: 히스토리가 이슈 단위로 남고, 문제 시 revert 단위가 명확
- PR은 작업 시작하자마자 **Draft로 즉시 오픈** — 보드 없이도 "누가 뭘 하는 중인지" 코드로 보임
- **3시간 넘게 머지 안 된 브랜치는 위험 신호** — 통합 게이트를 가볍게 만드는 유일한 방법은 자주 합치는 것
- 통합 게이트(H10·H20) **1시간 전 "머지 마감" 콜** — 게이트는 머지가 아니라 검증에 쓴다
- 충돌 해결 원칙: 먼저 푸시한 사람이 이기는 게 아니라 **해당 디렉토리 소유자가 해결**
- 커밋 메시지: `[R4] quest_builder: 하드 필터 4종` 수준이면 충분 — 컨벤션에 시간 쓰지 않는다

## 5. 마일스톤 — 통합 게이트가 곧 마일스톤

마일스톤은 날짜가 아니라 **통합 게이트**로 정의한다 (ARCHITECTURE 10장과 1:1):

| 마일스톤 | 완료 기준 | 시점 |
|---|---|---|
| **M0 통합 0 — 배선** | 스켈레톤 배포: Vercel↔Cloudtype↔Supabase(Session pooler) 연결 + CORS 통과 + 파이프라인 완주 1회 + 계약 4종 동결 + 스파이크 검증 | ~7.30 (본선 전) |
| **M1 통합 1 — recommend E2E** | 실데이터로 퀘스트 카드 3장이 화면에 뜬다 | 본선 H12 |
| **M2 통합 2 — 전체 E2E** | 입력→추천→상세→인증→기록 저장 완주 + 로컬 미러 동기화 | 본선 H24 |
| **M3 제출·발표** | 리허설 2회(라이브+폴백) + 발표 연습 1회 완료 | 본선 H30 |

운영 규칙: **모든 이슈는 마일스톤 필수.** 마일스톤에 안 붙는 작업은 "지금 할 일이 아니라는 뜻"이다. M1이 늦어지면 M2 이슈를 시작하는 게 아니라 M1 이슈를 나눠 든다.

## 6. 이슈 운영 — 본선 당일에 이슈 쓰느라 시간 쓰지 않기

**원칙: 이슈는 사전 준비 기간에 전부 만들어 둔다.** 스윔레인(TEAM_ROLES 4장)의 각 칸이 이슈 1~3개가 된다. 본선 당일 새로 만드는 이슈는 버그·차단 상황뿐.

- **1이슈 = 1담당 = 2~4시간 분량.** 그보다 크면 쪼갠다 (진행률이 보이는 유일한 단위)
- 라벨은 4종만: `R1`~`R4`(역할), `P0`(데모 크리티컬)/`P1`/`P2`, `blocked`, `bug`
- **blocked 운영 = 30분 룰의 기록판**: 30분 막히면 단톡 공유(기존 규칙) + 이슈에 `blocked` 라벨 + 뭐에 막혔는지 한 줄. 게이트 판정 때 blocked 목록부터 본다
- 이슈 본문은 3줄이면 충분: 할 일 / 완료 기준(DoD) / 의존하는 계약·이슈

### 6-1. 영역에 걸치는 기능은 어떻게 자르나 — "공유 트래커 ≠ 공유 이슈"

트래커는 하나지만 **담당자가 2명 이상인 이슈는 금지**다. 여러 명이 걸린 이슈는 책임이 증발하는 지점이다("셋 다 남의 일인 줄 아는 상태"). 기능이 자연스럽게 여러 영역에 걸치면, 그건 이슈가 아니라 **기능 목표**이고 — Day 0에 동결한 계약 경계선을 따라 역할별 이슈로 쪼갠다:

```
기능 "퀘스트 추천" (이슈가 아님 — 마일스톤 M1 그 자체)
 ├─ #12 [R3] scoring v1          DoD: 계약 시그니처대로 단위 테스트 통과
 ├─ #13 [R4] build_quests v1     DoD: 목 scoring으로 QuestCard 3장 JSON 반환
 ├─ #14 [R2] recommend 라우터     DoD: 목 build_quests로 200 응답
 └─ #15 [R1] 추천 화면            DoD: 목 JSON으로 카드 3장 렌더
```

포인트: 4개 이슈는 서로를 **기다리지 않는다.** 각자 계약 기반 목(mock)으로 병렬 완료하고, 실물 결합은 이슈 안이 아니라 **통합 게이트(M1)에서** 일어난다. 계약 4종을 Day 0에 동결한 이유가 바로 이것 — 계약이 없으면 기능을 1담당 이슈로 자를 수 없고, 그때는 정말로 "이슈 하나에 세 명" 사태가 난다.

**통합 중 걸친 버그**("카드가 안 뜬다" — 원인이 FE인지 API인지 데이터인지 모름): 발견자가 버그 이슈 1개를 만들고, 담당은 **증상이 보이는 지점의 소유자**(화면이면 R1)로 시작 → 원인 규명되면 실제 소유자로 **재할당**한다. 담당이 바뀔 뿐 1담당 원칙은 유지된다. 이때 원인 추적이 쉬우려면 전체 그림이 한 보드에 있어야 하고 — 이것이 트래커를 하나로 쓰는 이유다. 영역별로 트래커를 나누면 "추천 기능"이 세 보드에 세 조각으로 흩어져 연결 상태를 아무도 못 본다.

**GitHub Projects 보드 1개**: `Todo / Doing / Blocked / Done`, WIP 제한 1인 1개.

> **같은 방에 있는 4명에게 보드는 소통 수단이 아니라 기록 수단이다.** 말로 정하고, 보드는 그 결과를 남긴다. 보드 업데이트를 소통으로 착각하면("이슈에 써놨는데요") 무박 현장에서 반드시 사고가 난다. 소통은 입으로, 상태는 보드로.

**스탠드업: 4시간마다 5분, 서서.** 각자 ①직전 4시간 결과 ②다음 4시간 목표 ③blocked 여부만. H10·H20 게이트 직전 스탠드업은 팀장의 진입 기준 체크(TEAM_ROLES 2-2)와 겸한다.

## 7. 사전 세팅 스크립트 (레포 만드는 날 한 번에)

```bash
# 레포 생성 후 (gh CLI 로그인 상태에서)
gh label create R1 -c "#1f77b4"; gh label create R2 -c "#2ca02c"
gh label create R3 -c "#ff7f0e"; gh label create R4 -c "#9467bd"
gh label create P0 -c "#d62728" -d "데모 크리티컬"; gh label create P1 -c "#e377c2"; gh label create P2 -c "#7f7f7f"
gh label create blocked -c "#000000"; gh label create bug -c "#8c564b"

gh api repos/{owner}/{repo}/milestones -f title="M0 통합0 — 배선" -f description="스켈레톤 배포+파이프라인 완주+계약 동결+스파이크"
gh api repos/{owner}/{repo}/milestones -f title="M1 통합1 — recommend E2E"
gh api repos/{owner}/{repo}/milestones -f title="M2 통합2 — 전체 E2E"
gh api repos/{owner}/{repo}/milestones -f title="M3 제출·발표"

# 이슈 일괄 등록 예시 (스윔레인 → 이슈, 사전 준비 기간에 전부)
gh issue create -t "[R2] 스켈레톤 배포 — Supabase pooler 연결+CORS" -l R2,P0 -m "M0 통합0 — 배선" \
  -b "DoD: Cloudtype의 FastAPI가 Session pooler URI로 쿼리 성공, Vercel에서 /api/health 200"
gh issue create -t "[R3] 파이프라인 완주 1회 + accessibility_scores 소요 실측" -l R3,P0 -m "M0 통합0 — 배선" \
  -b "DoD: 10종 적재 + 파생 3종 생성, 배치 소요시간 기록"
# ... (TEAM_ROLES 4장 스윔레인의 나머지 칸들을 같은 형식으로)
```

## 8. 한 장 요약

| 질문 | 답 |
|---|---|
| 레포 몇 개? | **1개 (모노레포)** — AI 코드가 backend 안에 있어도 경계는 패키지+CODEOWNERS로 |
| AI가 백엔드를 만져도 되나? | 자기 소유 패키지(`services/scoring`, `quest_builder`, `llm`)만. import는 한 방향, 공개 인터페이스만 사용 |
| 브랜치? | 트렁크 기반, 이슈번호 브랜치, squash merge, 수명 반나절, 게이트 1시간 전 머지 마감 |
| 리뷰? | 계약 4종+models/만 필수, 나머지는 셀프 머지 (CODEOWNERS는 리뷰어 자동 지정용) |
| 마일스톤? | 통합 게이트 4개(M0 배선, M1 recommend E2E, M2 전체 E2E, M3 제출) — 모든 이슈는 마일스톤 필수 |
| 이슈? | 사전에 전부 등록, 1이슈=1담당=2~4h, 라벨 4종, blocked는 30분 룰의 기록 |
| 소통? | 입으로 (같은 방이다). 보드는 기록. 스탠드업 4시간마다 5분 |
