from app.schemas.dashboard_state import (
    CohortRotationGuidance,
    CohortRotationItem,
    ExposureGuidance,
    FedChessboard,
    MarketEasingExpectations,
)
from app.services.rules.allocation_plan import compute_allocation_plan


def test_d_regime_can_allow_defensive_only_deployment_within_cap() -> None:
    fed = FedChessboard(
        quadrant="D",
        liquidity_transition_path="none",
        transition_tag="Deteriorating",
    )
    exposure = ExposureGuidance(
        deployment_style="defensive",
        max_cash_deployment_pct=20,
        leverage_allowed=False,
    )
    cohort = CohortRotationGuidance(
        defensive_anchor_code="non_ai_low_valuation_defensive",
        items=[
            CohortRotationItem(
                cohort_code="non_ai_low_valuation_defensive",
                label="Defensive",
                stance="overweight",
                signal_mode="directional_only",
                reason="Defensive anchor in trapped or defensive regime.",
            ),
            CohortRotationItem(
                cohort_code="mag7",
                label="Mag 7",
                stance="underweight",
                signal_mode="actionable",
                reason="Macro backdrop does not justify leaning into Mag 7.",
            ),
        ],
    )

    result = compute_allocation_plan(
        fed_chessboard=fed,
        exposure_guidance=exposure,
        cohort_rotation_guidance=cohort,
    )

    assert result.plan.portfolio_action == "defensive_only"
    assert result.plan.total_cash_cap_pct == 20
    lane_map = {lane.cohort_code: lane for lane in result.plan.lanes}
    assert lane_map["non_ai_low_valuation_defensive"].permission == "allowed"
    assert lane_map["mag7"].permission == "blocked"


def test_d_to_c_can_allow_only_transition_lanes() -> None:
    fed = FedChessboard(
        quadrant="D",
        liquidity_transition_path="D_to_C",
        transition_tag="Improving",
    )
    exposure = ExposureGuidance(
        deployment_style="defensive",
        max_cash_deployment_pct=20,
        leverage_allowed=False,
    )
    cohort = CohortRotationGuidance(
        defensive_anchor_code="non_ai_low_valuation_defensive",
        items=[
            CohortRotationItem(
                cohort_code="mag7",
                label="Mag 7",
                stance="accumulate_slowly",
                signal_mode="actionable",
                reason="Emerging transition trade.",
            ),
            CohortRotationItem(
                cohort_code="non_ai_high_valuation",
                label="High Valuation Non-AI",
                stance="avoid",
                signal_mode="actionable",
                reason="Stretched.",
            ),
        ],
    )

    result = compute_allocation_plan(
        fed_chessboard=fed,
        exposure_guidance=exposure,
        cohort_rotation_guidance=cohort,
    )

    assert result.plan.portfolio_action == "defensive_only"
    lane_map = {lane.cohort_code: lane for lane in result.plan.lanes}
    assert lane_map["mag7"].permission == "allowed"
    assert lane_map["non_ai_high_valuation"].permission == "blocked"


def test_no_allowed_lanes_means_pause_or_wait() -> None:
    fed = FedChessboard(
        quadrant="C",
        liquidity_transition_path="none",
        transition_tag="Stable",
    )
    exposure = ExposureGuidance(
        deployment_style="selective",
        max_cash_deployment_pct=50,
        leverage_allowed=False,
    )
    cohort = CohortRotationGuidance(
        items=[
            CohortRotationItem(
                cohort_code="mag7",
                label="Mag 7",
                stance="watch",
                signal_mode="directional_only",
                reason="Directional only.",
            ),
            CohortRotationItem(
                cohort_code="non_mag7_ai",
                label="Non-Mag7 AI",
                stance="underweight",
                signal_mode="actionable",
                reason="Backdrop not clean.",
            ),
        ],
    )

    result = compute_allocation_plan(
        fed_chessboard=fed,
        exposure_guidance=exposure,
        cohort_rotation_guidance=cohort,
    )

    assert result.plan.portfolio_action == "pause_broad_market_adds"


def test_pricing_stretch_downgrades_transition_mag7_lane_to_watch_only() -> None:
    fed = FedChessboard(
        quadrant="D",
        liquidity_transition_path="D_to_C",
        transition_tag="Improving",
    )
    exposure = ExposureGuidance(
        deployment_style="defensive",
        max_cash_deployment_pct=20,
        leverage_allowed=False,
    )
    cohort = CohortRotationGuidance(
        items=[
            CohortRotationItem(
                cohort_code="mag7",
                label="Mag 7",
                stance="accumulate_slowly",
                signal_mode="actionable",
                reason="Emerging transition trade.",
            ),
            CohortRotationItem(
                cohort_code="non_ai_low_valuation_defensive",
                label="Defensive",
                stance="watch",
                signal_mode="directional_only",
                reason="Fallback anchor.",
            ),
        ],
        defensive_anchor_code="non_ai_low_valuation_defensive",
    )
    market_priced_easing = MarketEasingExpectations(
        expected_cut_bps_12m=50.0,
        expected_cut_count_12m=2.0,
        pricing_stretch_active=True,
        freshness_status="fresh",
        hard_actionable=True,
    )

    result = compute_allocation_plan(
        fed_chessboard=fed,
        exposure_guidance=exposure,
        cohort_rotation_guidance=cohort,
        market_priced_easing=market_priced_easing,
    )

    lane_map = {lane.cohort_code: lane for lane in result.plan.lanes}
    assert lane_map["mag7"].permission == "watch_only"
    assert result.plan.portfolio_action == "pause_broad_market_adds"
