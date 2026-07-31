"""#128 활동 표시 품질 — venue_name 주소 정제 + 공고성(비활동) 항목 필터.

모아봄 원본은 장소 칸에 도로명 주소 전문이 오는 경우가 있어("(24368) 강원특별자치도 춘천시
영서로 2260 1층 문화공간 역") 카드 히어로가 주소로 도배된다. 괄호 안 마지막 그룹이 실제
장소명이라는 원본 규칙을 이용해 명칭만 남긴다. 제목이 모집·공고·대관인 항목은 "오늘 가서
할 수 있는 활동"이 아니므로 적재에서 뺀다.
"""
import html
import re

NON_ACTIVITY = re.compile(r"모집|공고|대관")
_POSTAL = re.compile(r"\(\s*\d{5}\s*\)")
_FLOOR = re.compile(r"^\d+층$")
_ADDR_TOKEN = re.compile(r"^(강원특별자치도|강원도|춘천시)$|^\S+(?:로|길)\d*(?:번길)?$|^\d+(?:-\d+)?$")


def is_non_activity(title: str | None) -> bool:
    return bool(NON_ACTIVITY.search(title or ""))


def clean_venue_name(raw: str | None) -> str | None:
    if not raw:
        return raw
    text = _POSTAL.sub(" ", html.unescape(raw)).strip()
    groups = re.findall(r"\(([^()]+)\)", text)
    if groups:
        base = groups[-1].strip()
        tail = text.rsplit(")", 1)[-1].strip()
        tail = " ".join(token for token in tail.split() if not _FLOOR.match(token))
        if not tail or tail in base or base in tail:
            return base if len(base) >= len(tail) else tail
        return f"{base} {tail}"
    tokens = [t for t in text.split() if not _ADDR_TOKEN.match(t) and not _FLOOR.match(t)]
    return " ".join(tokens).strip() or text
