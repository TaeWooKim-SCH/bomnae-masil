"""#128 — 실데이터에서 관찰된 패턴 그대로 검증한다."""
from pipeline.load.venue_quality import clean_venue_name, is_non_activity


def test_parenthesized_venue_is_extracted():
    assert clean_venue_name(
        "(24239) 강원특별자치도 춘천시 스포츠타운길399번길 25 (KT&amp;G상상마당 춘천아트센터)"
    ) == "KT&G상상마당 춘천아트센터"


def test_duplicate_tail_is_deduped():
    assert clean_venue_name(
        "(24336) 강원특별자치도 춘천시 춘천로 112 (축제극장몸짓) 축제극장몸짓"
    ) == "축제극장몸짓"


def test_tail_space_is_appended():
    assert clean_venue_name(
        "(24355) 강원특별자치도 춘천시 춘천로145번길 18 (춘천 꿈꾸는 예술터) 1층 커뮤니티존"
    ) == "춘천 꿈꾸는 예술터 커뮤니티존"


def test_no_paren_address_tokens_are_dropped():
    assert clean_venue_name(
        "(24368) 강원특별자치도 춘천시 영서로 2260 1층 문화공간 역"
    ) == "문화공간 역"
    assert clean_venue_name(
        "(24239) 강원특별자치도 춘천시 스포츠타운길 347 강원권통일플러스센터"
    ) == "강원권통일플러스센터"


def test_clean_names_pass_through():
    assert clean_venue_name("춘천문화예술회관") == "춘천문화예술회관"
    assert clean_venue_name("춘천시립도서관") == "춘천시립도서관"


def test_non_activity_titles():
    assert is_non_activity("2026년 남춘천역 하부 '문화공간 역' 대관신청 공고")
    assert is_non_activity("어린이 뮤지컬반 수강생을 모집합니다")
    assert not is_non_activity("낯,선 풍경전- 춘천")
    assert not is_non_activity("제13회 한여름밤의 아리아")
