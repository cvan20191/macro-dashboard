from app.schemas.dashboard_state import (
    CohortRotationGuidance,
    DashboardState,
    EquityProfileGuidance,
    ExitDisciplineSignal,
    ExposureGuidance,
    FedChessboard,
    LiquidityPlumbing,
    MarketEasingExpectations,
    PeerScorecard,
)
from app.schemas.playbook_conclusion import PlaybookConclusion
from app.services.rules.deterministic_summary import build_deterministic_summary


def test_d_to_c_summary_keeps_actual_d_but_mentions_transition() -> None:
    state = DashboardState(
        primary_regime="Quadrant D / Illiquid Regime",
        current_posture="defensive",
        fed_chessboard=FedChessboard(
            quadrant="D",
            liquidity_transition_path="D_to_C",
            transition_tag="Improving",
        ),
        exposure_guidance=ExposureGuidance(
            deployment_style="defensive",
            max_cash_deployment_pct=20,
            leverage_allowed=False,
        ),
        cohort_rotation_guidance=CohortRotationGuidance(
            favored_cohort_codes=["mag7"],
            defensive_anchor_code="non_ai_low_valuation_defensive",
            items=[],
        ),
    )
    conclusion = PlaybookConclusion(
        conclusion_label="Transition regime",
        new_cash_action="accumulate_selectively",
        warning_urgency="cautionary",
        why_now="liquidity_quadrant_d_tight",
    )

    summary = build_deterministic_summary(state, conclusion)

    assert summary.headline == "Quadrant D / Illiquid Regime"
    assert summary.subheadline == "Actual quadrant is still D, but liquidity is transitioning toward C."
    assert summary.action_line == "Action: accumulate selectively."
    assert summary.deployment_line == "Deployment: up to 20% cash; leverage allowed = no."


def test_a_regime_exit_signal_is_rendered_deterministically() -> None:
    state = DashboardState(
        primary_regime="Quadrant A / Max Liquidity",
        current_posture="aggressive",
        fed_chessboard=FedChessboard(
            quadrant="A",
            liquidity_transition_path="none",
            transition_tag="Improving",
        ),
        exposure_guidance=ExposureGuidance(
            deployment_style="aggressive",
            max_cash_deployment_pct=100,
            leverage_allowed=True,
        ),
        exit_discipline_signal=ExitDisciplineSignal(
            active=True,
            scope="stock_d_type_a_regime",
            rate_reversal_watch_active=True,
            qe_fade_watch_active=False,
        ),
    )

    summary = build_deterministic_summary(state, None)

    assert summary.headline == "Quadrant A / Max Liquidity"
    assert "Exit discipline is active for the A-regime growth profile." in (summary.caution_line or "")


def test_plumbing_not_qe_is_rendered_deterministically() -> None:
    state = DashboardState(
        primary_regime="Quadrant Unknown / Wait",
        current_posture="wait",
        fed_chessboard=FedChessboard(
            quadrant="Unknown",
            liquidity_transition_path="none",
            transition_tag="Stable",
        ),
        liquidity_plumbing=LiquidityPlumbing(
            state="severe",
            state_label="Funding stress",
            balance_sheet_expansion_not_qe=True,
        ),
    )

    summary = build_deterministic_summary(state, None)

    assert "Balance-sheet support is plumbing support, not QE." in (summary.caution_line or "")


def test_profile_and_peer_lines_are_rendered_from_existing_state() -> None:
    state = DashboardState(
        primary_regime="Quadrant D / Illiquid Regime",
        current_posture="defensive",
        fed_chessboard=FedChessboard(
            quadrant="D",
            liquidity_transition_path="D_to_C",
            transition_tag="Improving",
        ),
        equity_profile_guidance=EquityProfileGuidance(
            primary_profile_code="stock_a_type",
            primary_profile_label="Stable / low valuation / low leverage / solvent",
            emerging_profile_code="stock_c_type",
            emerging_profile_label="Emerging C-type: high growth / refinancing beneficiary",
            exit_discipline_required=False,
        ),
        peer_scorecards=[
            PeerScorecard(ticker="NVDA", verdict="leader"),
            PeerScorecard(ticker="MSFT", verdict="leader"),
            PeerScorecard(ticker="ORCL", verdict="balanced"),
        ],
    )

    summary = build_deterministic_summary(state, None)

    assert summary.profile_line == (
        "Primary stock profile: Stable / low valuation / low leverage / solvent. "
        "Emerging profile: Emerging C-type: high growth / refinancing beneficiary."
    )
    assert summary.peer_line == "Peer check: current leaders versus same-sector peers = NVDA, MSFT."


def test_pricing_line_and_stretch_caution_render_from_existing_state() -> None:
    state = DashboardState(
        primary_regime="Quadrant C / Liquidity Transition",
        current_posture="selective",
        fed_chessboard=FedChessboard(
            quadrant="C",
            liquidity_transition_path="none",
            transition_tag="Improving",
        ),
        market_priced_easing=MarketEasingExpectations(
            source_mode="manual_snapshot",
            as_of="2026-01-10",
            current_target_mid=4.375,
            expected_cut_bps_rest_of_year=100.0,
            expected_cut_count_rest_of_year=4.0,
            pricing_horizon_label="rest_of_calendar_year",
            pricing_stretch_active=True,
            freshness_status="fresh",
            hard_actionable=True,
        ),
    )

    summary = build_deterministic_summary(state, None)

    assert summary.pricing_line == "Market pricing: about 4.0 more cuts (100 bps) by year-end."
    assert "Market is already pricing aggressive easing, which looks stretched." in (
        summary.caution_line or ""
    )


def test_stale_pricing_stretch_renders_descriptive_only_caution() -> None:
    state = DashboardState(
        primary_regime="Quadrant C / Liquidity Transition",
        current_posture="selective",
        fed_chessboard=FedChessboard(
            quadrant="C",
            liquidity_transition_path="none",
            transition_tag="Improving",
        ),
        market_priced_easing=MarketEasingExpectations(
            source_mode="manual_snapshot",
            as_of="2026-01-01",
            current_target_mid=4.375,
            expected_cut_bps_rest_of_year=100.0,
            expected_cut_count_rest_of_year=4.0,
            pricing_horizon_label="rest_of_calendar_year",
            pricing_stretch_active=True,
            freshness_status="stale",
            data_age_days=20,
            hard_actionable=False,
        ),
    )

    summary = build_deterministic_summary(state, None)

    assert "Market-priced easing snapshot is stale; stretch read is descriptive only." in (
        summary.caution_line or ""
    )
