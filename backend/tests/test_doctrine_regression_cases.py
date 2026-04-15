from __future__ import annotations

from app.schemas.indicator_snapshot import (
    DataFreshnessInput,
    DollarContextInput,
    GrowthInput,
    IndicatorSnapshot,
    InflationInput,
    LiquidityInput,
    PlumbingInput,
    PolicySupportInput,
    SystemicStressInput,
    ValuationInput,
)
from app.services.rules.dashboard_state_builder import build_dashboard_state_with_conclusion


def _legacy_rate_trends(rate_direction_medium_term: str, rate_impulse_short: str) -> tuple[str, str]:
    if rate_direction_medium_term == "easing":
        rate_trend_3m = "down"
        rate_trend_1m = "down" if rate_impulse_short == "confirming_easing" else "flat"
    elif rate_direction_medium_term == "tightening":
        rate_trend_3m = "up"
        rate_trend_1m = "up" if rate_impulse_short == "confirming_tightening" else "flat"
    else:
        rate_trend_3m = "flat"
        rate_trend_1m = "flat"
    return rate_trend_1m, rate_trend_3m


def _legacy_bs_trends(
    balance_sheet_direction_medium_term: str,
    balance_sheet_pace: str,
) -> tuple[str, str]:
    if balance_sheet_direction_medium_term == "contracting":
        balance_sheet_trend_3m = "down"
        balance_sheet_trend_1m = "flat" if balance_sheet_pace == "contracting_slower" else "down"
    elif balance_sheet_direction_medium_term == "expanding":
        balance_sheet_trend_3m = "up"
        balance_sheet_trend_1m = "flat" if balance_sheet_pace == "expanding_slower" else "up"
    else:
        balance_sheet_trend_3m = "flat"
        balance_sheet_trend_1m = "flat"
    return balance_sheet_trend_1m, balance_sheet_trend_3m


def make_snapshot(
    *,
    as_of: str,
    fed_funds_rate: float,
    rate_direction_medium_term: str,
    rate_impulse_short: str,
    balance_sheet_direction_medium_term: str,
    balance_sheet_pace: str,
    forward_pe: float,
    current_year_forward_pe: float,
    next_year_forward_pe: float,
    selected_year: int,
    signal_mode: str = "actionable",
    coverage_count: int = 7,
    coverage_ratio: float = 1.0,
    basis_confidence: float = 1.0,
    core_cpi_yoy: float = 3.0,
    unemployment_rate: float = 4.2,
    pmi_manufacturing: float = 49.0,
    pmi_services: float = 52.0,
    fed_put: bool = False,
    treasury_put: bool = False,
    political_put: bool = False,
    plumbing_state: str = "normal",
    walcl_trend_1m: str = "down",
    reserves_trend_1m: str = "flat",
    repo_trend_1m: str = "flat",
    reverse_repo_trend_1m: str = "flat",
    repo_spike_ratio: float = 1.0,
    reverse_repo_buffer_ratio: float = 1.0,
    stress_warning_npl: float = 0.9,
) -> IndicatorSnapshot:
    rate_trend_1m, rate_trend_3m = _legacy_rate_trends(rate_direction_medium_term, rate_impulse_short)
    balance_sheet_trend_1m, balance_sheet_trend_3m = _legacy_bs_trends(
        balance_sheet_direction_medium_term,
        balance_sheet_pace,
    )

    total_reserves = 3000.0
    repo_total = 5.0
    reverse_repo_total = 100.0

    if plumbing_state == "elevated":
        total_reserves = 2920.0
        repo_total = 20.0
        reverse_repo_total = 70.0
    elif plumbing_state == "severe":
        total_reserves = 2875.0
        repo_total = 35.0
        reverse_repo_total = 35.0

    return IndicatorSnapshot(
        as_of=as_of,
        data_freshness=DataFreshnessInput(
            overall_status="fresh",
            stale_series=[],
        ),
        liquidity=LiquidityInput(
            fed_funds_rate=fed_funds_rate,
            rate_trend_1m=rate_trend_1m,
            rate_trend_3m=rate_trend_3m,
            balance_sheet_assets=6_700_000.0,
            balance_sheet_trend_1m=balance_sheet_trend_1m,
            balance_sheet_trend_3m=balance_sheet_trend_3m,
            rate_cycle_position=0.75,
            rate_direction_medium_term=rate_direction_medium_term,
            rate_impulse_short=rate_impulse_short,
            balance_sheet_direction_medium_term=balance_sheet_direction_medium_term,
            balance_sheet_pace=balance_sheet_pace,
            quadrant_basis_note=(
                "Quadrant uses medium-term Fed rate direction plus medium-term Fed balance-sheet direction; "
                "short impulse and pace only modify transition."
            ),
        ),
        plumbing=PlumbingInput(
            total_reserves=total_reserves,
            reserves_trend_1m=reserves_trend_1m,
            reserves_buffer_ratio=0.95 if plumbing_state != "severe" else 0.75,
            repo_total=repo_total,
            repo_trend_1m=repo_trend_1m,
            repo_spike_ratio=repo_spike_ratio,
            reverse_repo_total=reverse_repo_total,
            reverse_repo_trend_1m=reverse_repo_trend_1m,
            reverse_repo_buffer_ratio=reverse_repo_buffer_ratio,
            walcl_trend_1m=walcl_trend_1m,
        ),
        growth=GrowthInput(
            pmi_manufacturing=pmi_manufacturing,
            pmi_services=pmi_services,
            unemployment_rate=unemployment_rate,
            unemployment_trend="flat",
            initial_claims_trend="flat",
            payrolls_trend="flat",
        ),
        inflation=InflationInput(
            core_cpi_yoy=core_cpi_yoy,
            core_cpi_mom=0.2,
            shelter_status="sticky",
            services_ex_energy_status="sticky",
            wti_oil=80.0,
            oil_risk_active=False,
        ),
        valuation=ValuationInput(
            forward_pe=forward_pe,
            current_year_forward_pe=current_year_forward_pe,
            next_year_forward_pe=next_year_forward_pe,
            selected_year=selected_year,
            pe_basis="forward",
            pe_source_note="speaker_forward_pe doctrine regression fixture",
            metric_name="Mag 7 Forward P/E",
            object_label="Mag 7 Basket",
            pe_provider="fmp",
            coverage_count=coverage_count,
            coverage_ratio=coverage_ratio,
            signal_mode=signal_mode,
            basis_confidence=basis_confidence,
            estimate_as_of=as_of[:10],
            horizon_label=(
                "speaker_calendar_current_year"
                if selected_year == int(as_of[:4])
                else "speaker_calendar_next_year"
            ),
            horizon_coverage_ratio=coverage_ratio,
            constituents=[],
        ),
        systemic_stress=SystemicStressInput(
            yield_curve_10y_2y=-0.25,
            npl_ratio=stress_warning_npl,
            cre_delinquency_rate=1.5,
            credit_card_chargeoff_rate=3.0,
            market_cap_m2_ratio=2.2,
            corporate_equities_m2_ratio=5.4,
            equity_m2_ratio_source="fred_z1",
            corporate_equities_m2_source="fred_z1",
            equity_m2_numerator_as_of=as_of[:10],
            corporate_equities_m2_numerator_as_of=as_of[:10],
            equity_m2_numerator_freshness="fresh",
            corporate_equities_m2_numerator_freshness="fresh",
        ),
        dollar_context=DollarContextInput(dxy=100.0),
        policy_support=PolicySupportInput(
            fed_put=fed_put,
            treasury_put=treasury_put,
            political_put=political_put,
        ),
    )


def test_april_2025_d_to_c_transition_starts_buying_slowly() -> None:
    snapshot = make_snapshot(
        as_of="2025-04-10T00:00:00Z",
        fed_funds_rate=4.50,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
        forward_pe=23.0,
        current_year_forward_pe=23.0,
        next_year_forward_pe=21.0,
        selected_year=2025,
        signal_mode="actionable",
        coverage_count=7,
        coverage_ratio=1.0,
        basis_confidence=1.0,
        core_cpi_yoy=2.8,
        unemployment_rate=4.1,
        fed_put=True,
    )

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.primary_regime.startswith("Quadrant C")
    assert state.tactical_state == "Start buying very slowly"
    assert conclusion.new_cash_action == "accumulate_selectively"


def test_late_september_2025_high_valuation_pauses_new_buying_but_keeps_c() -> None:
    snapshot = make_snapshot(
        as_of="2025-09-30T00:00:00Z",
        fed_funds_rate=4.25,
        rate_direction_medium_term="easing",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
        forward_pe=30.2,
        current_year_forward_pe=30.2,
        next_year_forward_pe=28.8,
        selected_year=2025,
        signal_mode="actionable",
        coverage_count=7,
        coverage_ratio=1.0,
        basis_confidence=1.0,
        core_cpi_yoy=3.0,
        unemployment_rate=4.3,
        fed_put=True,
        treasury_put=True,
        political_put=True,
    )

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.primary_regime.startswith("Quadrant C")
    assert state.tactical_state == "Hold / no new buying"
    assert conclusion.new_cash_action == "pause_new_buying"


def test_quadrant_b_supportive_valuation_stays_selective_and_blocks_new_cash() -> None:
    snapshot = make_snapshot(
        as_of="2025-02-15T00:00:00Z",
        fed_funds_rate=4.75,
        rate_direction_medium_term="tightening",
        rate_impulse_short="confirming_tightening",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
        forward_pe=23.5,
        current_year_forward_pe=23.5,
        next_year_forward_pe=22.0,
        selected_year=2025,
        signal_mode="actionable",
        coverage_count=7,
        coverage_ratio=1.0,
        basis_confidence=1.0,
        core_cpi_yoy=2.9,
        unemployment_rate=4.0,
        pmi_manufacturing=52.0,
        pmi_services=53.0,
    )

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.primary_regime.startswith("Quadrant B")
    assert state.tactical_state == "Selective accumulation"
    assert conclusion.new_cash_action == "hold_and_wait"


def test_2026_plumbing_stress_marks_walcl_uptick_as_not_qe_in_integrated_state() -> None:
    snapshot = make_snapshot(
        as_of="2026-01-15T00:00:00Z",
        fed_funds_rate=4.00,
        rate_direction_medium_term="stable",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="flat_or_mixed",
        balance_sheet_pace="flat_or_mixed",
        forward_pe=26.0,
        current_year_forward_pe=26.0,
        next_year_forward_pe=24.0,
        selected_year=2026,
        signal_mode="directional_only",
        coverage_count=5,
        coverage_ratio=0.71,
        basis_confidence=0.71,
        core_cpi_yoy=2.7,
        unemployment_rate=4.6,
        plumbing_state="severe",
        walcl_trend_1m="up",
        reserves_trend_1m="down",
        repo_trend_1m="up",
        reverse_repo_trend_1m="down",
        repo_spike_ratio=3.0,
        reverse_repo_buffer_ratio=0.25,
        fed_put=False,
    )

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.liquidity_plumbing is not None
    assert state.liquidity_plumbing.state == "severe"
    assert state.liquidity_plumbing.balance_sheet_expansion_not_qe is True
    assert conclusion is not None
