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


def _snapshot(*, quadrant: str, buy_zone: bool = False, stretched: bool = False, trap: bool = False) -> IndicatorSnapshot:
    if quadrant == "A":
        liquidity = LiquidityInput(
            fed_funds_rate=4.0,
            balance_sheet_assets=7_000_000,
            rate_direction_medium_term="easing",
            rate_impulse_short="confirming_easing",
            balance_sheet_direction_medium_term="expanding",
            balance_sheet_pace="expanding_same_or_faster",
        )
    elif quadrant == "B":
        liquidity = LiquidityInput(
            fed_funds_rate=4.5,
            balance_sheet_assets=7_000_000,
            rate_direction_medium_term="tightening",
            rate_impulse_short="confirming_tightening",
            balance_sheet_direction_medium_term="expanding",
            balance_sheet_pace="expanding_same_or_faster",
        )
    elif quadrant == "C":
        liquidity = LiquidityInput(
            fed_funds_rate=4.25,
            balance_sheet_assets=6_800_000,
            rate_direction_medium_term="easing",
            rate_impulse_short="stable",
            balance_sheet_direction_medium_term="contracting",
            balance_sheet_pace="contracting_slower",
        )
    else:
        liquidity = LiquidityInput(
            fed_funds_rate=4.75,
            balance_sheet_assets=6_700_000,
            rate_direction_medium_term="tightening",
            rate_impulse_short="confirming_tightening",
            balance_sheet_direction_medium_term="contracting",
            balance_sheet_pace="contracting_same_or_faster",
        )

    forward_pe = 22.0 if buy_zone else 31.0 if stretched else 27.0
    return IndicatorSnapshot(
        liquidity=liquidity,
        growth=GrowthInput(
            pmi_manufacturing=48.0 if trap else 52.0,
            pmi_services=51.0,
            unemployment_rate=4.2,
            unemployment_trend="flat",
            initial_claims_trend="flat",
            payrolls_trend="flat",
        ),
        inflation=InflationInput(
            core_cpi_yoy=3.2 if trap else 2.4,
            core_cpi_mom=0.2,
            shelter_status="sticky" if trap else "easing",
            services_ex_energy_status="sticky" if trap else "easing",
            wti_oil=78.0,
            oil_risk_active=False,
        ),
        valuation=ValuationInput(
            forward_pe=forward_pe,
            pe_basis="forward",
            signal_mode="actionable",
            basis_confidence=0.95,
        ),
        systemic_stress=SystemicStressInput(),
    )


def test_quadrant_b_green_does_not_turn_into_buy_the_dip() -> None:
    state, conclusion = build_dashboard_state_with_conclusion(_snapshot(quadrant="B", buy_zone=True))

    assert state.primary_regime == "Quadrant B / Mixed Liquidity"
    assert state.tactical_state == "Selective accumulation"
    assert conclusion.new_cash_action == "hold_and_wait"


def test_quadrant_c_buy_zone_accumulates_only_in_transition() -> None:
    state, conclusion = build_dashboard_state_with_conclusion(_snapshot(quadrant="C", buy_zone=True))

    assert state.primary_regime == "Quadrant C / Liquidity Transition"
    assert state.tactical_state == "Start buying very slowly"
    assert conclusion.new_cash_action == "accumulate_selectively"


def test_d_to_c_transition_keeps_top_level_quadrant_d_semantics() -> None:
    liquidity = LiquidityInput(
        fed_funds_rate=4.50,
        balance_sheet_assets=6_700_000,
        rate_direction_medium_term="tightening",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    state, conclusion = build_dashboard_state_with_conclusion(
        _snapshot(quadrant="D", buy_zone=True).model_copy(update={"liquidity": liquidity})
    )

    assert state.primary_regime == "Quadrant D / Illiquid Regime"
    assert state.fed_chessboard is not None
    assert state.fed_chessboard.liquidity_transition_path == "D_to_C"
    assert state.tactical_state == "Defensive preservation"
    assert conclusion.new_cash_action == "hold_and_wait"
