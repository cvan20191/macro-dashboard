from app.schemas.dashboard_state import (
    CohortValuation,
    FedChessboard,
    PolicyOptionality,
    Valuation,
)
from app.services.rules.cohort_rotation import compute_cohort_rotation_guidance


def _valuation() -> Valuation:
    return Valuation(
        forward_pe=24.0,
        cohort_valuations=[
            CohortValuation(
                cohort_code="mag7",
                label="Mag 7",
                forward_pe=24.0,
                signal_mode="actionable",
            ),
            CohortValuation(
                cohort_code="non_mag7_ai",
                label="Non-Mag7 AI",
                forward_pe=27.0,
                signal_mode="directional_only",
            ),
            CohortValuation(
                cohort_code="non_ai_high_valuation",
                label="High Valuation Non-AI",
                forward_pe=28.0,
                signal_mode="directional_only",
            ),
            CohortValuation(
                cohort_code="non_ai_low_valuation_defensive",
                label="Defensive",
                forward_pe=18.0,
                signal_mode="actionable",
            ),
        ],
    )


def test_free_backdrop_favors_mag7_and_not_stretched_ai() -> None:
    fed = FedChessboard(
        quadrant="C",
        liquidity_transition_path="none",
        transition_tag="Improving",
    )
    policy = PolicyOptionality(
        constraint_level="free",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=True,
        rate_cut_weirdness_active=False,
    )

    result = compute_cohort_rotation_guidance(
        fed_chessboard=fed,
        policy_optionality=policy,
        valuation=_valuation(),
    )

    item_map = {item.cohort_code: item for item in result.guidance.items}
    assert item_map["mag7"].stance == "overweight"
    assert item_map["non_mag7_ai"].stance == "neutral"
    assert item_map["non_ai_high_valuation"].stance == "avoid"


def test_trapped_or_weird_backdrop_favors_defensive_cohort() -> None:
    fed = FedChessboard(
        quadrant="D",
        liquidity_transition_path="none",
        transition_tag="Deteriorating",
    )
    policy = PolicyOptionality(
        constraint_level="trapped",
        fed_can_ease=False,
        fed_trapped=True,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=True,
    )

    result = compute_cohort_rotation_guidance(
        fed_chessboard=fed,
        policy_optionality=policy,
        valuation=_valuation(),
    )

    item_map = {item.cohort_code: item for item in result.guidance.items}
    assert item_map["mag7"].stance == "underweight"
    assert item_map["non_mag7_ai"].stance == "underweight"
    assert item_map["non_ai_low_valuation_defensive"].stance == "overweight"
    assert result.guidance.defensive_anchor_code == "non_ai_low_valuation_defensive"


def test_d_to_c_transition_allows_mag7_accumulate_slowly() -> None:
    fed = FedChessboard(
        quadrant="D",
        liquidity_transition_path="D_to_C",
        transition_tag="Improving",
    )
    policy = PolicyOptionality(
        constraint_level="limited",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=False,
    )

    result = compute_cohort_rotation_guidance(
        fed_chessboard=fed,
        policy_optionality=policy,
        valuation=_valuation(),
    )

    item_map = {item.cohort_code: item for item in result.guidance.items}
    assert item_map["mag7"].stance == "accumulate_slowly"
    assert item_map["non_ai_low_valuation_defensive"].stance in {"neutral", "overweight"}
