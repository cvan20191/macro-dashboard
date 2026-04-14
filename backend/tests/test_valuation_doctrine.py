from __future__ import annotations

from app.schemas.indicator_snapshot import (
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
            rate_trend_1m="up",
            rate_trend_3m="up",
            balance_sheet_assets=7_000_000,
            balance_sheet_trend_1m="up",
            balance_sheet_trend_3m="up",
            rate_cycle_position=0.8,
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
    assert state.primary_regime != "Valuation Stretched"
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
    assert state.primary_regime == "Valuation Stretched"
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
    snapshot.liquidity.rate_trend_1m = "flat"
    snapshot.liquidity.rate_trend_3m = "flat"
    snapshot.liquidity.balance_sheet_trend_1m = "flat"
    snapshot.liquidity.balance_sheet_trend_3m = "down"

    state, conclusion = build_dashboard_state_with_conclusion(snapshot)

    assert state.fed_chessboard is not None
    assert state.fed_chessboard.quadrant == "Unknown"
    assert state.primary_regime != "Buy-the-Dip Window"
    assert conclusion.new_cash_action == "hold_and_wait"
