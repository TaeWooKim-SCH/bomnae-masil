# 봄내마실 — API 계약 v1 (동결 후보)

> 화면(R1)↔서버(R2)↔조립(R4)의 약속. **동결 후에는 필드 추가·변경·이름 바꾸기 금지** — 변경은 결정자(태우) 승인 + 단톡 공지 후에만.
> R1의 목 JSON(#17)은 이 문서와 글자 단위로 일치해야 한다.

## 0. 공통 규칙

- **Base**: `/api` · 본문은 JSON · 시각은 ISO 8601(Asia/Seoul). 서버의 "지금"은 기준 시각 유틸(`DEMO_NOW` 지원)
- **인증**: 세션 필요 API는 헤더 `Authorization: Bearer <session_id>`. 세션이 서버에 없으면 → `401 {"error":{"code":"SESSION_NOT_FOUND"}}` → 클라이언트는 로컬 키 폐기 + 첫 방문 모달 (25-screens 0장)
- **에러 형식(공통)**: `{"error":{"code":"<대문자_스네이크>","message":"<사용자에게 그대로 보여줄 한국어>", ...확장 필드}}` — 코드별 확장 필드(예: current_quest_id)는 error 객체 안에 둔다
- **balance**: 별도 조회 API 없음 — 세션 생성·인증·기록 저장·**보관함(GET /records)** 응답에 항상 포함. **재방문 홈의 잔액·칭호는 GET /records 응답을 사용한다**
- **QR 페이로드(#47 동결)**: `<서비스URL>/verify?m=<merchant_id>&c=<4자리코드>` — 클라이언트가 m·c를 파싱해 verify로 전송. **딥링크 규칙**: 이 URL로 직접 진입 시 `active_quest_id` 있으면 그 퀘스트로 인증 시도, 없으면 홈으로 보내며 "봄내마실에서 퀘스트를 시작한 뒤 찍어주세요" 안내

## 1. 세션

### POST /sessions — 세션 만들기 (인증 불필요)
```json
요청  {"nickname": "봄내마실러", "age_confirmed": true}     // nickname 선택(최대 12자), age_confirmed 필수
응답 201 {"session_id": "ses_a1b2c3", "balance": 0}
오류 400 AGE_NOT_CONFIRMED "만 14세 이상만 이용할 수 있어요"
```

### DELETE /sessions/{session_id} — 전체 삭제
퀘스트·스탬프·기록·포인트 연쇄 삭제(익명 집계 통계는 유지). 응답 `204`.

## 2. 출발지 참조 (인증 불필요)

### GET /zones
경로 보유 행정동만, 가나다순. `[{"zone_code":"4211056000","name":"석사동"}]`

### GET /stops?zone={zone_code}
그 동의 정류장 목록, 가나다순. `[{"stop_id":"stp_1041","name":"석사동 현진아파트"}]`

## 3. 추천

### POST /quests/recommend
```json
요청 {
  "interests": ["사진·미디어", "문화·공연"],          // 칩 7종 enum, 1~3개 (§3 하단 목록)
  "origin": {"zone_code": "4211056000", "stop_id": null},  // stop_id: 2단 선택에서 골랐을 때만, 아니면 null
  "time_window": {"start": "2026-08-01T14:00", "end": "2026-08-01T18:00"},  // 최소 60분, MVP는 오늘 날짜 고정(화면이 오늘로 채워 보냄)
  "max_budget_krw": 30000                            // 0(무료만) | 10000 | 30000 | 50000 | null(상관없음)
}
응답 200 {
  "recommendation_id": "rec_x1",
  "quests":  [QuestCard, QuestCard, QuestCard],      // 1~3위
  "more":    [QuestCard],                            // 4~6위 (0~3장) — "다른 추천 보기"가 이걸 표시, 소진 시 버튼 숨김
  "relaxed": null                                    // 자동 완화 시: {"steps":["budget","interest","always_open","revisit"] 중 적용분,
}                                                    //   "message":"조건을 조금 넓혀 찾았어요"}
오류 400 INVALID_TIME_WINDOW "이용 시간을 60분 이상으로 선택해 주세요"
```
- 응답은 서버가 스냅샷 저장 — 뒤로가기는 재호출 없이 클라이언트가 재표시
- **빈 결과 (8/1 결정)**: 완화 4단계 소진 후에도 0건이면 **정상 200**으로 `"quests": [], "more": []` + `relaxed: {"steps": [적용한 전 단계], "message": "지금 조건에 맞는 활동이 없어요"}` — recommendation_id·스냅샷은 그대로 발급(빈 결과율 = 대시보드 KPI 원천). 화면 동작은 25-screens 2장, 조립 규칙은 계약④ §4-2
- 관심사 칩 enum(#48): `운동·건강 / 문화·공연 / 공예·만들기 / 사진·미디어 / 요리·먹거리 / 학습·어학 / 자연·나들이` — **7종 확정** (청소년·진로는 데이터 미확보로 제외, 포털 정상화 후 복원 로드맵)

### QuestCard (카드·목의 기준 스키마)
```json
{
  "quest_id": "q_301",
  "title": "저녁의 필름카메라 입문",
  "activity": {
    "name": "필름카메라 입문 강좌", "type": "신청형",        // 당일형 | 신청형 | 상시형
    "place_name": "춘천시평생학습관", "schedule_text": "오늘 19:00–21:00",
    "price_krw": 10000,
    "d_day": 5                                             // 신청형만: "개강 D-5" (마감 아님). 그 외 null
  },
  "mission": {                                             // 가게 없는 퀘스트면 null → 화면은 "+60점 완주" 문구
    "merchant_id": "m_12", "merchant_name": "육림고개 ○○카페",
    "copy": "강좌 끝나고 필름 감성 그대로, 따뜻한 한 잔 어때요?",   // 사전 생성 문안(#18)
    "expected_spend_krw": 7000
  },
  "route": {
    "board_stop_name": "석사동 현진아파트", "route_no": "300",
    "stops_count": 7,                                      // 승차→하차 정거장 수 (노선정보에서 정확 계산 — 진짜 데이터)
    "ride_min": 25, "walk_min": 8,                          // ride_min = 정류장 구간 거리 기반 추정 (배차·시각표 데이터 미보유 — 표기는 "약")
    "no_transfer": true,                                   // 항상 true (환승 조합은 추천 제외)
    "basis_note": "석사동 현진아파트 정류장 기준"              // 출발 정류장 미선택 시만, 선택했으면 null
  },
  "budget_total_krw": 20000,                               // 활동비 + 미션 단가 + 버스 왕복 3,000
  "score": {"total": 86, "breakdown": {"market": 26, "interest": 22, "access": 17, "time": 13, "budget": 8}},
  "max_points": 100,                                       // 가게 없는 퀘스트는 60
  "revisit": false,                                        // 이 세션이 시작·완주했던 활동의 재추천이면 true → "다시 가기" 뱃지 (필터⑤ 해제 = 완화 4단계)
  "refs": {"activity_id": "a_88", "board_stop_id": "stp_1041", "alight_stop_id": "stp_2210"}
                                                           // 서버·조립 내부 참조 — 화면은 사용 금지 (상세 coords 조인 키)
}
```
- 버스 표기는 화면에서 `"300번 · 7개 정류장 · 약 25분"`으로 조립 — **배차간격·시각표·실시간 필드는 존재하지 않는다** (태우 확정 7/31: 노선·정거장·추정 소요만 안내). 시간 적합 판정의 대기·환승 여유는 **고정 버퍼 10분**
- 빈 결과 완화 4단계(계약④와 동일): ①예산 +30% → ②관심사 확대 → ③상시형 대체 → ④필터⑤(기시작·완주 활동 제외) 해제 — 이동·시간 필터는 절대 완화 금지
- **소유 경계**: quest_id·recommendation_id 발급과 스냅샷 저장은 R2 라우터 소유 — build_quests(계약④)는 [카드 최대 6장 + relaxed]만 반환하고, 필터⑤용 exclude_activity_ids는 R2가 세션에서 조회해 전달한다

## 4. 퀘스트 진행

### GET /quests/{quest_id} — 상세
QuestCard 전체 + 지도용 좌표 + 상태:
```json
{ ...QuestCard,
  "status": "recommended",                     // recommended | started | stamped | recorded | abandoned
  "started_at": null,
  "coords": {
    "activity": {"lat": 37.8791, "lng": 127.7292},
    "mission":  {"lat": 37.8801, "lng": 127.7269},         // mission 없으면 null
    "board_stop": {"lat": 37.8672, "lng": 127.7211},
    "alight_stop": {"lat": 37.8794, "lng": 127.7281},
    "path": [[37.8672,127.7211],[37.8794,127.7281]]        // 경로선용 (버스 구간 단순 연결)
  }
}
```

### POST /quests/{quest_id}/start — 시작 (started 전이)
```json
요청  {"abandon_current": false}
응답 200 {"status": "started", "started_at": "2026-08-01T14:05:00"}
오류 409 {"error":{"code":"QUEST_IN_PROGRESS","message":"진행 중인 퀘스트가 있어요","current_quest_id":"q_299"}}
      // → 클라이언트가 확인 모달 후 {"abandon_current": true}로 재요청 → 기존 건 abandoned
```

### POST /quests/{quest_id}/verify — 미션 인증 (stamped 전이)
전제: 해당 퀘스트가 **이 세션의 started 또는 stamped 상태**여야 한다 (아니면 400 QUEST_NOT_STARTED).
```json
요청 (셋 중 하나)
  {"method": "qr",      "merchant_id": "m_12", "code": "4821"}   // QR 파싱 결과
  {"method": "code",    "code": "4821"}                           // 4자리 수동 입력
  {"method": "receipt", "amount_krw": 8500}                       // 1,000~200,000. 사진은 전송·저장하지 않는다
응답 200 {"stamp_type": "visit",              // qr·code=visit, receipt=spend
         "already": false,                    // 재인증이면 true (에러 아님 — 멱등)
         "points_added": 40, "balance": 40,
         "title_unlocked": null,              // 100점 도달 시 "봄내 첫걸음"
         "message": "스탬프가 적립됐어요!"}
재인증(멱등) 응답 200 {"stamp_type": "visit", "already": true,
         "points_added": 0, "balance": 40,   // 잔액 변동 없음, title_unlocked는 null 고정
         "message": "이미 적립된 퀘스트예요"}
오류 400 WRONG_STORE   "이 퀘스트의 미션 가게는 ○○예요"     // qr의 merchant_id 불일치. 재시도 무제한
     400 INVALID_CODE  "코드를 다시 확인해 주세요"
     400 INVALID_AMOUNT "금액을 확인해 주세요 (1,000~200,000원)"
     400 NO_MISSION    "이 퀘스트는 가게 미션이 없어요 — 기록으로 완주해요"
     400 QUEST_NOT_STARTED "퀘스트를 먼저 시작해 주세요"
```

## 5. 기록

### POST /records — 생성과 저장 (한 창구, action으로 구분)
전제: 해당 퀘스트가 **이 세션의 started 또는 stamped 상태**여야 한다 (recommended → 400 QUEST_NOT_STARTED / 이미 recorded → 409 ALREADY_RECORDED "이미 완주한 퀘스트예요").
```json
생성 요청 {"quest_id": "q_301", "action": "generate",
          "purpose": "hobby",                  // portfolio | hobby | learning (기본 hobby)
          "answers": ["새로웠어요", "", ""],     // 고정 3문항, 각 최대 200자, 빈 값 허용
          "attempt": 0}                        // 다시 생성 최대 2 (0|1|2)
생성 응답 200 {"draft": {"title": "…", "body": "…(300~500자)", "tags": ["사진","육림고개","저녁"]},
             "from_template": false}          // AI 8초 초과·실패 시 true ("연결이 느려 기본 초안을 먼저 드려요")

저장 요청 {"quest_id": "q_301", "action": "save", "purpose": "hobby",
          "answers": ["새로웠어요", "", ""],
          "final": {"title": "…", "body": "…", "tags": ["…","…","…"]}}   // 사용자가 수정한 최종본
저장 응답 201 {"record_id": "rec_77",
             "points_added": 40,              // answers 전부 빈 값이면 0
             "completion_bonus": 20,          // 조건: [스탬프 보유 또는 가게 없는 퀘스트] **그리고 answers 1개 이상**. 아니면 0
                                              // answers 전부 빈 값이면 40·20 모두 0 — 저장 전 화면 안내: "한 가지만 골라주시면 포인트가 적립돼요 (+60점)"
             "balance": 100, "title_unlocked": "봄내 첫걸음",
             "verified": true}                // 스탬프 없이 저장 시 false → "인증 없음" 뱃지
```
- 저장 시 recorded 전이(완주), 저장 후 기록은 읽기 전용
- 오류: 400 QUEST_NOT_STARTED / 409 ALREADY_RECORDED / 400 INVALID_ATTEMPT(attempt>2) / 400 VALIDATION(answers 200자 초과, purpose enum 밖 등)

### GET /records — 보관함
```json
응답 200 {"records": [{"record_id":"rec_77","quest_id":"q_301","title":"…","tags":["…"],
                      "created_at":"2026-08-01T17:40:00","verified":true}],
         "balance": 100, "titles": ["봄내 첫걸음"],
         "zone_map": {"collected": ["4211056000"], "available": ["4211056000", "4211057000"]}}
```

**zone_map** (8/1 동결 후 결정자 승인 추가 — #101 조각지도): `collected` = 완주한 퀘스트 활동지의 행정동, `available` = 활동이 1건 이상 있는 동. 지오메트리는 별도 API 없이 **대시보드 접근성 GeoJSON을 재사용**하고, 잠금 동 = GeoJSON에는 있으나 available에 없는 동. 수집 칭호(5동·10동·전판)는 titles 배열로 합류한다. 구현: #99(서버)·#100(화면).

## 6. 대시보드 (인증 불필요 — 데모 공개)

### GET /dashboard/accessibility — 접근성 히트맵 (GeoJSON, #12 스키마)
FeatureCollection(Polygon). properties: `{"zone_code","name","score","quintile":1~5}` (동별 평균, 5분위)
— **사각지대 레이어**(25-screens 6장 '여유 시')는 별도 필드·API 없이 **quintile=5 구역을 클라이언트가 필터링**해 표시한다

### GET /dashboard/inflow — 저유입 상권 (GeoJSON)
FeatureCollection(Point). properties: `{"name","category","inflow_status":"확정저유입"|"추정후보"|"일반"|"붐빔"}`

### GET /dashboard/kpi — 성과 숫자 (#36 산식)
```json
응답 200 {"conversion_pct": 44.0,        // stamped ÷ 가게 있는 started
         "low_inflow_pct": 52.1,        // 저유입 '확정' 미션 카드 ÷ 가게 미션 있는 노출 카드
         "median_search_min": 2.4,      // 세션 생성→첫 started **중앙값** (화면 라벨: "탐색 시간(중앙값)")
                                        // 위 세 지표 공통: 분모 0이면 null → 화면 "—"
         "feasibility_pct": 100,        // 무환승 경로 보유 비율 (각주: 설계로 보장)
         "spend_total_krw": 187000,     // 영수증 인증 합계
         "seed_included": true}         // 화면 각주 "시범 운영 시뮬레이션 포함"
```

## 7. 운영

### GET /health (인증 불필요)
`{"ok": true, "db": true, "demo_now": "2026-08-01T14:00:00"}` — demo_now는 DEMO_NOW 설정 시 그 값

## 부록 — 에러 코드 전체
`SESSION_NOT_FOUND(401)` `AGE_NOT_CONFIRMED` `INVALID_TIME_WINDOW` `QUEST_IN_PROGRESS(409)` `QUEST_NOT_STARTED` `ALREADY_RECORDED(409)` `INVALID_ATTEMPT` `VALIDATION` `WRONG_STORE` `INVALID_CODE` `INVALID_AMOUNT` `NO_MISSION` `NOT_FOUND(404)` `INTERNAL(500 — 화면은 공통 오류 문구+재시도)`
