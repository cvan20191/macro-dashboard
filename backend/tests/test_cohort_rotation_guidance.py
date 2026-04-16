from app.schemas.dashboard_state import (
    CohortValuation,
    FedChessboard,
    PolicyOptionality,
    Valuation,
)
from app.services.rules.cohort_rotation import compute_cohort_rotation_guidance


def _valuation(
    *,
    mag7_signal_mode: str = "actionable",
    high_val_signal_mode: str = "directional_only",
) -> Valuation:
    return Valuation(
        forward_pe=24.0,
        cohort_valuations=[
            CohortValuation(
                cohort_code="mag7",
                label="Mag 7",
                forward_pe=24.0,
                signal_mode=mag7_signal_mode,
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
                signal_mode=high_val_signal_mode,
            ),
            CohortValuation(
                cohort_code="non_ai_low_valuation_defensive",
                label="Defensive",
                forward_pe=18.0,
                signal_mode="directional_only",
            ),
        ],
    )


def test_free_backdrop_favors_mag7_only_when_mag7_is_actionable() -> None:
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


def test_directional_only_mag7_cannot_be_overweight_or_accumulate_slowly() -> None:
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
        valuation=_valuation(mag7_signal_mode="directional_only"),
    )

    item_map = {item.cohort_code: item for item in result.guidance.items}
    assert item_map["mag7"].stance == "watch"
    assert "mag7" not in result.guidance.favored_cohort_codes


def test_directional_only_high_valuation_cohort_cannot_hard_avoid() -> None:
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
        valuation=_valuation(high_val_signal_mode="directional_only"),
    )

    item_map = {item.cohort_code: item for item in result.guidance.items}
    assert item_map["non_ai_high_valuation"].stance == "watch"


def test_defensive_anchor_can_still_overweight_in_trapped_backdrop() -> None:
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
    assert item_map["non_ai_low_valuation_defensive"].stance == "overweight"
    assert result.guidance.defensive_anchor_code == "non_ai_low_valuation_defensive"
