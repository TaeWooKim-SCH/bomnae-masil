import pytest

from app.services.scoring import calculate_score, classify_inflow_status, normalize_merchant_name
from app.services.scoring.constants import BUS_ROUND_TRIP_KRW, budget_total_krw, mission_spend_krw


def score_input(**overrides):
    value = {
        "activity_id": "activity-1", "interests": ["문화·공연", "사진·미디어"],
        "activity_interest_tags": ["문화·공연", "사진·미디어"], "merchant_inflow_status": "확정저유입",
        "access_score": 85, "time_fit_ratio": 0.8, "budget_fit_ratio": 0.8,
    }
    value.update(overrides)
    return value


def test_score_uses_all_five_contract_component_names_and_weights():
    result = calculate_score(score_input())

    assert result == {"total": 92, "breakdown": {"market": 30, "interest": 25, "access": 17, "time": 12, "budget": 8}}


def test_unmatched_merchant_is_midpoint_not_confirmed_low_inflow():
    result = calculate_score(score_input(merchant_inflow_status=None))
    assert result["breakdown"]["market"] == 15


def test_extreme_inputs_keep_score_in_contract_range():
    result = calculate_score(score_input(access_score=0, time_fit_ratio=0, budget_fit_ratio=0, merchant_inflow_status="붐빔"))
    assert result["total"] == 25
    assert result["breakdown"] == {"market": 0, "interest": 25, "access": 0, "time": 0, "budget": 0}


def test_interest_match_can_change_ranking_without_changing_other_components():
    matching = calculate_score(score_input())
    non_matching = calculate_score(score_input(activity_interest_tags=["요리·먹거리"]))
    assert matching["total"] > non_matching["total"]


def test_inflow_classifier_and_name_normalizer_are_single_frozen_rule_primitives():
    peers = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert classify_inflow_status(10, peers) == "확정저유입"
    assert classify_inflow_status(50, peers) == "일반"
    assert classify_inflow_status(90, peers) == "붐빔"
    assert normalize_merchant_name("(주) 봄내 카페") == normalize_merchant_name("주식회사 봄내카페")


def test_budget_constants_are_shared_and_category_based():
    assert mission_spend_krw("카페") == 7_000
    assert mission_spend_krw("일반음식점") == 12_000
    assert mission_spend_krw("소매") == 5_000
    assert budget_total_krw(10_000, "카페") == 10_000 + 7_000 + BUS_ROUND_TRIP_KRW
    with pytest.raises(ValueError):
        budget_total_krw(-1, "카페")
