"""배선용 build_quests 목 — R4 v1(#27) 착륙 전까지만 쓰는 R2 소유 대역.

recommend.py가 `app.services.quest_builder`에서 진짜 build_quests를 import하지 못할 때만
이 목을 쓴다(통합1에서 자동 스왑). 형태는 계약④(33-build-quests-contract.md) 그대로:
입력 dict(interests·origin·time_window·max_budget_krw·exclude_activity_ids) →
(cards 1~6장 QuestCardDraft, relaxed|None). quest_id는 넣지 않는다(R2 발급).

목의 결정적 규칙(검증 스크립트가 의존):
- 기본: 카드 6장(점수 내림차순), relaxed=None
- 예산 하드 필터(계약④ 4-1-3): budget_total_krw ≤ 상한. 3장 미만이 되면 완화 1단계
  (상한 +30%)로 재시도하고 relaxed {"steps":["budget"], ...}
- exclude_activity_ids에 든 활동 제외 — 남은 카드가 3장 미만이면 완화 4단계(revisit)로
  전부 복귀시키고 revisit=true + relaxed {"steps":[..., "revisit"], ...}
- max_budget_krw == 0(무료만): 무료 활동+가게 없는 카드만 → 3장 (more 소진 케이스)
- origin.stop_id가 있으면 basis_note=None, 없으면 카드별 "<승차 정류장> 정류장 기준" (계약 §3)
"""
import copy

RELAXED_MESSAGE = "조건을 조금 넓혀 찾았어요"

# 검증 스크립트(verify_r2_07)가 완화 케이스를 만들 때 쓰는 활동 id 목록
MOCK_ACTIVITY_IDS = [f"a_mock_{i}" for i in range(1, 7)]

_CARDS = [
    {
        "title": "저녁의 필름카메라 입문",
        "activity": {"name": "필름카메라 입문 강좌", "type": "신청형", "place_name": "춘천시평생학습관",
                     "schedule_text": "오늘 19:00–21:00", "price_krw": 10000, "d_day": 5},
        "mission": {"merchant_id": "m_mock_1", "merchant_name": "육림고개 골목카페",
                    "copy": "강좌 끝나고 필름 감성 그대로, 따뜻한 한 잔 어때요?", "expected_spend_krw": 7000},
        "route": {"board_stop_name": "석사동 현진아파트", "route_no": "300", "stops_count": 7,
                  "ride_min": 25, "walk_min": 8, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 20000,
        "score": {"total": 86, "breakdown": {"market": 26, "interest": 22, "access": 17, "time": 13, "budget": 8}},
        "max_points": 100, "revisit": False,
        "refs": {"activity_id": "a_mock_1", "board_stop_id": "stp_1041", "alight_stop_id": "stp_2210"},
    },
    {
        "title": "박물관 상설전 느긋하게 보기",
        "activity": {"name": "국립춘천박물관 상설전 관람", "type": "상시형", "place_name": "국립춘천박물관",
                     "schedule_text": "운영시간 내 자유 관람 (10:00~18:00)", "price_krw": 0, "d_day": None},
        "mission": None,
        "route": {"board_stop_name": "후평동 행정복지센터", "route_no": "12", "stops_count": 5,
                  "ride_min": 18, "walk_min": 6, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 3000,
        "score": {"total": 81, "breakdown": {"market": 0, "interest": 23, "access": 18, "time": 15, "budget": 10}},
        "max_points": 60, "revisit": False,
        "refs": {"activity_id": "a_mock_2", "board_stop_id": "stp_301", "alight_stop_id": "stp_478"},
    },
    {
        "title": "공지천 산책 사진 한 컷",
        "activity": {"name": "공지천 야외 산책", "type": "상시형", "place_name": "공지천 일대",
                     "schedule_text": "상시 개방", "price_krw": 0, "d_day": None},
        "mission": None,
        "route": {"board_stop_name": "석사동 현진아파트", "route_no": "7", "stops_count": 4,
                  "ride_min": 12, "walk_min": 5, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 3000,
        "score": {"total": 77, "breakdown": {"market": 0, "interest": 20, "access": 19, "time": 15, "budget": 10}},
        "max_points": 60, "revisit": False,
        "refs": {"activity_id": "a_mock_3", "board_stop_id": "stp_1041", "alight_stop_id": "stp_520"},
    },
    {
        "title": "원데이 도자기 클래스",
        "activity": {"name": "원데이 도자기 체험", "type": "신청형", "place_name": "근화동 공방거리",
                     "schedule_text": "오늘 15:00–17:00", "price_krw": 15000, "d_day": 2},
        "mission": {"merchant_id": "m_mock_4", "merchant_name": "근화동 동네서점",
                    "copy": "흙 만진 손으로 책 한 권 어때요?", "expected_spend_krw": 5000},
        "route": {"board_stop_name": "석사동 현진아파트", "route_no": "64", "stops_count": 9,
                  "ride_min": 28, "walk_min": 7, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 23000,
        "score": {"total": 74, "breakdown": {"market": 24, "interest": 18, "access": 14, "time": 12, "budget": 6}},
        "max_points": 100, "revisit": False,
        "refs": {"activity_id": "a_mock_4", "board_stop_id": "stp_1041", "alight_stop_id": "stp_733"},
    },
    {
        "title": "무료 전시 보고 시장 구경",
        "activity": {"name": "춘천미술관 기획전", "type": "당일형", "place_name": "춘천미술관",
                     "schedule_text": "오늘 10:00–18:00", "price_krw": 0, "d_day": None},
        "mission": None,
        "route": {"board_stop_name": "석사동 현진아파트", "route_no": "9", "stops_count": 6,
                  "ride_min": 15, "walk_min": 4, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 3000,
        "score": {"total": 69, "breakdown": {"market": 0, "interest": 17, "access": 17, "time": 15, "budget": 10}},
        "max_points": 60, "revisit": False,
        "refs": {"activity_id": "a_mock_5", "board_stop_id": "stp_1041", "alight_stop_id": "stp_610"},
    },
    {
        "title": "향토 요리 클래스 맛보기",
        "activity": {"name": "닭갈비 쿠킹 클래스", "type": "신청형", "place_name": "요선동 쿠킹스튜디오",
                     "schedule_text": "오늘 17:00–19:00", "price_krw": 25000, "d_day": 1},
        "mission": {"merchant_id": "m_mock_6", "merchant_name": "요선동 반찬가게",
                    "copy": "배운 김에 저녁 반찬도 골라볼까요?", "expected_spend_krw": 5000},
        "route": {"board_stop_name": "석사동 현진아파트", "route_no": "150", "stops_count": 11,
                  "ride_min": 32, "walk_min": 9, "no_transfer": True, "basis_note": None},
        "budget_total_krw": 33000,
        "score": {"total": 63, "breakdown": {"market": 22, "interest": 14, "access": 11, "time": 10, "budget": 6}},
        "max_points": 100, "revisit": False,
        "refs": {"activity_id": "a_mock_6", "board_stop_id": "stp_1041", "alight_stop_id": "stp_812"},
    },
]


def build_quests(user_input: dict) -> tuple[list[dict], dict | None]:
    cards = copy.deepcopy(_CARDS)
    steps: list[str] = []

    stop_chosen = bool(user_input["origin"].get("stop_id"))
    for c in cards:
        # 미선택 시 기준 정류장 = 그 카드의 승차 정류장 (계약 §3 예시와 동일 규칙)
        c["route"]["basis_note"] = None if stop_chosen else f"{c['route']['board_stop_name']} 정류장 기준"

    budget = user_input.get("max_budget_krw")
    if budget == 0:  # 무료 모드 — 무료 활동 + 가게 없는 카드만
        cards = [c for c in cards if c["activity"]["price_krw"] == 0 and c["mission"] is None]
    elif budget is not None:  # 하드 필터 3(예산 내) — 부족하면 완화 1단계(+30%)
        within = [c for c in cards if c["budget_total_krw"] <= budget]
        if len(within) < 3:
            within = [c for c in cards if c["budget_total_krw"] <= budget * 1.3]
            steps.append("budget")
        cards = within

    excluded = set(user_input.get("exclude_activity_ids") or [])
    remaining = [c for c in cards if c["refs"]["activity_id"] not in excluded]
    if len(remaining) >= 3 or not excluded:
        cards = remaining
    else:  # 완화 4단계(revisit): 필터⑤ 해제 — 복귀 카드에 revisit=true
        for c in cards:
            if c["refs"]["activity_id"] in excluded:
                c["revisit"] = True
        steps.append("revisit")

    relaxed = {"steps": steps, "message": RELAXED_MESSAGE} if steps else None
    return cards[:6], relaxed
