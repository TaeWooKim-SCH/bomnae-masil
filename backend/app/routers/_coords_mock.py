"""상세 coords 조인의 모의 리졸버 — ①원천 테이블(activities·merchants·bus_stops) 적재 전까지만.

R3의 #9 적재 + R2의 ①모델 후속 커밋(#11 트리거) 뒤에는 resolve_coords 내부를 실제 조인으로
교체한다 — 호출부(quests.py)는 이 함수 하나만 쓰므로 교체 지점은 여기 한 곳이다.

모르는 id도 죽지 않는다: 춘천 중심 좌표에 id 해시 기반 소량 오프셋을 더해 결정적 모의 좌표를
만든다(같은 id → 항상 같은 좌표). 데모 파손 방지가 목적이며, 실데이터 적재 후엔 실좌표가 우선.
"""
import hashlib

# 춘천 시청 부근 기준점
_BASE_LAT, _BASE_LNG = 37.8813, 127.7298

# 목 카드(_quest_builder_mock)의 id들 — 그럴듯한 실제 지점 좌표
_KNOWN: dict[str, tuple[float, float]] = {
    "a_mock_1": (37.8791, 127.7292),  # 춘천시평생학습관 인근
    "a_mock_2": (37.8778, 127.7444),  # 국립춘천박물관
    "a_mock_3": (37.8685, 127.7192),  # 공지천
    "a_mock_4": (37.8843, 127.7169),  # 근화동 공방거리
    "a_mock_5": (37.8862, 127.7205),  # 춘천미술관 인근
    "a_mock_6": (37.8815, 127.7240),  # 요선동
    "m_mock_1": (37.8801, 127.7269),  # 육림고개
    "m_mock_4": (37.8846, 127.7181),
    "m_mock_6": (37.8818, 127.7247),
    "stp_1041": (37.8672, 127.7211),  # 석사동 현진아파트
    "stp_301": (37.8757, 127.7412),   # 후평동 행정복지센터
    "stp_2210": (37.8794, 127.7281),
    "stp_478": (37.8781, 127.7439),
    "stp_520": (37.8689, 127.7199),
    "stp_610": (37.8858, 127.7211),
    "stp_733": (37.8840, 127.7175),
    "stp_812": (37.8812, 127.7251),
}


def _coords_for(ref_id: str) -> dict:
    if ref_id in _KNOWN:
        lat, lng = _KNOWN[ref_id]
    else:  # 결정적 모의 좌표 — 어떤 id가 와도 죽지 않게
        h = int(hashlib.sha256(ref_id.encode()).hexdigest()[:8], 16)
        lat = round(_BASE_LAT + ((h % 200) - 100) / 10000, 4)
        lng = round(_BASE_LNG + (((h // 200) % 200) - 100) / 10000, 4)
    return {"lat": lat, "lng": lng}


def resolve_coords(card: dict) -> dict:
    """계약 §4 coords — activity·mission(null 가능)·board_stop·alight_stop·path(경로선)."""
    refs = card["refs"]
    board = _coords_for(refs["board_stop_id"])
    alight = _coords_for(refs["alight_stop_id"])
    mission = card.get("mission")
    return {
        "activity": _coords_for(refs["activity_id"]),
        "mission": _coords_for(mission["merchant_id"]) if mission else None,
        "board_stop": board,
        "alight_stop": alight,
        "path": [[board["lat"], board["lng"]], [alight["lat"], alight["lng"]]],  # 버스 구간 단순 연결
    }
