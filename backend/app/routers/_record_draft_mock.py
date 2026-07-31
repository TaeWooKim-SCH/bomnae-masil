"""활동 기록 초안 생성의 배선용 목 — R4 #38(프롬프트·페르소나·폴백) 착륙 전까지만.

records.py가 `app.services.llm`에서 공개 함수(generate_record_draft·template_draft)를 import하지
못할 때만 이 목을 쓴다(착륙 시 자동 스왑). 프롬프트 내용·대체 문구는 R4 소유 — 이 목은
실제 LLM을 부르지 않고 결정적 의사 초안을 만든다(배선·캐시·폴백 경로 검증용).

반환 형태(계약 §5 draft): {"title": str, "body": str(300~500자), "tags": [str, str, str]}
"""
CALLS = {"n": 0}  # 검증 스크립트가 "같은 answers 2회 → 호출 1회"를 세는 카운터


def generate_record_draft(payload: dict) -> dict:
    """의사 LLM 초안 — 같은 payload면 항상 같은 결과(캐시 재생 검증 가능)."""
    CALLS["n"] += 1
    activity = payload["activity_name"]
    place = payload.get("place_name") or "춘천"
    answered = [a for a in payload["answers"] if a.strip()]
    seed = answered[0] if answered else "오늘의 활동"
    body = (
        f"오늘 {place}에서 '{activity}'을(를) 다녀왔다. {seed}라는 말이 가장 먼저 떠오른다. "
        f"떠나기 전엔 크게 기대하지 않았는데, 막상 도착해 보니 공간의 분위기부터 달랐다. "
        f"입구에서부터 느껴지는 낯선 설렘이 있었고, 프로그램을 따라가는 동안 시간이 금방 흘렀다. "
        f"중간중간 휴대폰에 적어둔 메모를 지금 다시 읽어 보니 그때의 기분이 그대로 살아난다. "
        f"함께한 사람들의 표정, 창밖으로 보이던 풍경, 사소한 대화 한 줄까지 오늘을 이루는 "
        f"조각들이 생각보다 많았다는 걸 기록을 쓰며 깨닫는다. 끝나고 나오는 길에는 골목의 "
        f"가게들을 천천히 지나며 다음에 또 와야겠다고 생각했다. 춘천에서 보낸 오늘 하루가 "
        f"이렇게 기록으로 남아서 좋다. 다음 마실이 벌써 기다려진다."
    )
    return {
        "title": f"{place}에서 만난 {activity}",
        "body": body,
        "tags": [activity[:6], place[:6], payload.get("purpose", "hobby")],
    }


def template_draft(payload: dict) -> dict:
    """대체 초안(실패 사다리 최종 단계) — 문구는 R4 #38이 확정, 이건 배선용 기본값."""
    activity = payload["activity_name"]
    place = payload.get("place_name") or "춘천"
    body = (
        f"오늘 {place}에서 '{activity}' 활동에 다녀왔다. 집을 나서기 전 준비하며 기대했던 것, "
        f"현장에 도착해서 처음 느낀 공기, 프로그램을 하나씩 따라가며 들었던 생각, 그리고 "
        f"돌아오는 길에 곱씹었던 마음까지 차근차근 남겨 본다. 특별할 것 없어 보이는 하루도 "
        f"이렇게 적어 두면 나중에 다시 꺼내 볼 수 있는 이야기가 된다. 짧은 기록이지만 오늘의 "
        f"나에게는 분명 의미 있는 한 걸음이었다. 활동이 끝나고 지나친 동네 골목의 풍경도 "
        f"오래 기억에 남을 것 같다. 다음에는 조금 더 여유를 갖고, 주변의 가게들도 들르며 "
        f"천천히 즐겨 보고 싶다. 춘천에서의 다음 마실을 벌써 계획하게 된다."
    )
    return {"title": f"{activity} 기록", "body": body, "tags": [activity[:6], "춘천", "기록"]}
