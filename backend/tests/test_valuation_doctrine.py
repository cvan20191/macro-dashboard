from __future__ import annotations

from app.schemas.indicator_snapshot import (
    CohortValuationInput,
    GrowthInput,
    IndicatorSnapshot,
    InflationInput,
    LiquidityInput,
    SystemicStressInput,
    ValuationInput,
)
from app.services.rules.dashboard_state_builder import build_dashboard_state_with_conclusion
from app.services.rules.valuation import compute_valuation


def _base_snapshot(valuation: ValuationInput) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        liquidity=LiquidityInput(
            fed_funds_rate=4.5,
            balance_sheet_assets=7_000_000,
            rate_direction_medium_term="tightening",
            rate_impulse_short="confirming_tightening",
            balance_sheet_direction_medium_term="expanding",
            balance_sheet_pace="expanding_same_or_faster",
        ),
        growth=GrowthInput(
            pmi_manufacturing=52.0,
            pmi_services=53.0,
            unemployment_rate=4.8,
            unemployment_trend="flat",
            initial_claims_trend="flat",
            payrolls_trend="flat",
        ),
        inflation=InflationInput(
            core_cpi_yoy=2.4,
            core_cpi_mom=0.2,
            shelter_status="easing",
            services_ex_energy_status="easing",
            wti_oil=78.0,
            oil_risk_active=False,
        ),
        valuation=valuation,
        systemic_stress=SystemicStressInput(),
    )


def test_proxy_red_zone_is_directional_only() -> None:
    result = compute_valuation(
        ValuationInput(
            forward_pe=31.0,
            pe_basis="trailing",
            signal_mode="directional_only",
            basis_confidence=0.35,
        )
    )
    assert result.is_stretched is True
    assert result.valuation.zone_label == "Proxy stretched"
    assert result.can_pause_new_buying is False


def test_proxy_red_zone_does_not_drive_hard_action() -> None:
    state, conclusion = build_dashboard_state_with_conclusion(
        _base_snapshot(
            ValuationInput(
                forward_pe=31.0,
                pe_basis="trailing",
                signal_mode="directional_only",
                basis_confidence=0.35,
            )
        )
    )
    assert state.primary_regime == "Quadrant B / Mixed Liquidity"
    assert state.legacy_regime_label == "Mixed / Conflicted Regime"
    assert conclusion.new_cash_action != "pause_new_buying"


def test_true_forward_red_zone_can_pause_new_buying() -> None:
    state, conclusion = build_dashboard_state_with_conclusion(
        _base_snapshot(
            ValuationInput(
                forward_pe=31.0,
                pe_basis="forward",
                signal_mode="actionable",
                basis_confidence=0.95,
            )
        )
    )
    assert state.primary_regime == "Quadrant B / Mixed Liquidity"
    assert state.tactical_state == "Hold / no new buying"
    assert state.legacy_regime_label == "Valuation Stretched"
    assert conclusion.new_cash_action == "pause_new_buying"


def test_buy_zone_does_not_accumulate_when_liquidity_is_unknown() -> None:
    snapshot = _base_snapshot(
        ValuationInput(
            forward_pe=22.0,
            pe_basis="forward",
            signal_mode="actionable",
            basis_confidence=0.95,
        )
    )
    snapshot.liquidity.rate_direction_medium_term = None
    snapshot.liquidity.rate_impulse_short = None
    snapshot.liquidity.balance_sheet_direction_medium_term = None
    snapshot.liquidity.balance_sheet_pace = None

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.fed_chessboard is not None
    assert state.fed_chessboard.quadrant == "Unknown"
    assert state.primary_regime == "Quadrant Unknown / Wait"
    assert conclusion.new_cash_action == "hold_and_wait"


def test_directional_only_forward_pe_does_not_enable_hard_buy_signal() -> None:
    result = compute_valuation(
        ValuationInput(
            forward_pe=23.0,
            current_year_forward_pe=23.0,
            next_year_forward_pe=21.0,
            selected_year=2026,
            pe_basis="forward",
            pe_source_note="speaker forward basket incomplete on selected year",
            signal_mode="directional_only",
            basis_confidence=0.5,
            horizon_label="speaker_fye_proximity_current_year",
            coverage_count=6,
            coverage_ratio=0.84,
            horizon_coverage_ratio=0.72,
        )
    )

    assert result.is_buy_zone is True
    assert result.valuation.signal_mode == "directional_only"
    assert result.can_support_buy_zone is False
    assert result.can_pause_new_buying is False


def test_legacy_forward_pe_remains_mag7_while_multi_cohort_state_is_exposed() -> None:
    result = compute_valuation(
        ValuationInput(
            forward_pe=24.0,
            current_year_forward_pe=24.0,
            next_year_forward_pe=22.0,
            selected_year=2026,
            pe_basis="forward",
            pe_source_note="legacy Mag 7",
            signal_mode="actionable",
            basis_confidence=1.0,
            horizon_label="speaker_fye_proximity_current_year",
            coverage_count=7,
            coverage_ratio=1.0,
            horizon_coverage_ratio=1.0,
            cohort_valuations=[
                CohortValuationInput(
                    cohort_code="mag7",
                    label="Mag 7",
                    forward_pe=24.0,
                    current_year_forward_pe=24.0,
                    next_year_forward_pe=22.0,
                    selected_year=2026,
                    horizon_label="speaker_fye_proximity_current_year",
                    signal_mode="actionable",
                    coverage_count=7,
                    coverage_ratio=1.0,
                    basis_confidence=1.0,
                    tickers=["AAPL", "MSFT"],
                ),
                CohortValuationInput(
                    cohort_code="non_mag7_ai",
                    label="Non-Mag7 AI",
                    forward_pe=27.0,
                    current_year_forward_pe=27.0,
                    next_year_forward_pe=25.0,
                    selected_year=2026,
                    horizon_label="speaker_fye_proximity_current_year",
                    signal_mode="directional_only",
                    coverage_count=4,
                    coverage_ratio=0.78,
                    basis_confidence=0.78,
                    tickers=["ORCL", "PLTR"],
                ),
            ],
        )
    )

    assert result.valuation.forward_pe == 24.0
    assert len(result.valuation.cohort_valuations) == 2
    assert result.valuation.cohort_valuations[0].cohort_code == "mag7"
    assert result.valuation.cohort_valuations[1].cohort_code == "non_mag7_ai"
