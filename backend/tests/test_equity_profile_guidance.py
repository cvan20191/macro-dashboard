from app.schemas.dashboard_state import (
    DollarContext,
    LiquidityPlumbing,
    PolicyOptionality,
    RallyConditions,
    StagflationTrap,
    SystemicStress,
    Valuation,
)
from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard
from app.services.rules.policy_optionality import PolicyOptionalityResult
from app.services.rules.rally import RallyResult
from app.services.rules.regime import compute_regime
from app.services.rules.stagflation import StagflationResult
from app.services.rules.stress import DollarResult, StressResult
from app.services.rules.valuation import ValuationResult


def _policy_ok() -> PolicyOptionalityResult:
    optionality = PolicyOptionality(
        constraint_level="limited",
        labor_slack_state="mixed",
        labor_balance_state="mixed",
        inflation_state="mixed",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=False,
        note=None,
    )
    return PolicyOptionalityResult(
        optionality=optionality,
        constraint_level="limited",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=False,
    )


def _stag() -> StagflationResult:
    trap = StagflationTrap(
        active=False,
        growth_weakening=False,
        sticky_inflation=False,
    )
    return StagflationResult(
        trap=trap,
        growth_weakening=False,
        sticky_inflation=False,
        oil_risk_active=False,
    )


def _val() -> ValuationResult:
    valuation = Valuation(
        forward_pe=24.0,
        zone="Green",
        zone_label="Buy zone",
        signal_mode="actionable",
    )
    return ValuationResult(
        valuation=valuation,
        zone="Green",
        is_stretched=False,
        is_buy_zone=True,
        can_support_buy_zone=True,
        can_pause_new_buying=False,
    )


def _stress() -> StressResult:
    stress = SystemicStress(
        yield_curve_inverted=True,
        yield_curve_value=-0.25,
        proxy_warning_active=False,
    )
    return StressResult(
        stress=stress,
        stress_warning_active=False,
        stress_severe=False,
    )


def _dollar() -> DollarResult:
    context = DollarContext(dxy=100.0, dxy_pressure=False)
    return DollarResult(dollar=context, dxy_pressure=False)


def _rally() -> RallyResult:
    return RallyResult(
        conditions=RallyConditions(
            rally_fuel_score=0,
            fed_put=False,
            treasury_put=False,
            political_put=False,
            market_ignoring_bad_news=False,
        ),
        rally_fuel_score=0,
    )


def _regime_for(liq: LiquidityInput):
    cb = compute_chessboard(liq, plumbing=LiquidityPlumbing())
    return compute_regime(
        cb=cb,
        stag=_stag(),
        val=_val(),
        stress=_stress(),
        dollar=_dollar(),
        rally=_rally(),
        policy_optionality=_policy_ok(),
    )


def test_quadrant_d_maps_to_stock_a_type() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=4.75,
            rate_direction_medium_term="tightening",
            rate_impulse_short="confirming_tightening",
            balance_sheet_direction_medium_term="contracting",
            balance_sheet_pace="contracting_same_or_faster",
        )
    )

    assert result.primary_regime.startswith("Quadrant D")
    assert result.equity_profile_guidance.primary_profile_code == "stock_a_type"
    assert result.equity_profile_guidance.secondary_profile_code is None
    assert result.equity_profile_guidance.exit_discipline_required is False
    assert result.equity_profile_guidance.same_sector_peer_compare_required is True


def test_quadrant_c_prefers_stock_c_with_stock_b_secondary() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=4.25,
            rate_direction_medium_term="easing",
            rate_impulse_short="confirming_easing",
            balance_sheet_direction_medium_term="contracting",
            balance_sheet_pace="contracting_slower",
        )
    )

    assert result.primary_regime.startswith("Quadrant C")
    assert result.equity_profile_guidance.primary_profile_code == "stock_c_type"
    assert result.equity_profile_guidance.secondary_profile_code == "stock_b_type"


def test_quadrant_b_prefers_stock_b_with_stock_c_secondary() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=4.75,
            rate_direction_medium_term="tightening",
            rate_impulse_short="confirming_tightening",
            balance_sheet_direction_medium_term="expanding",
            balance_sheet_pace="expanding_same_or_faster",
        )
    )

    assert result.primary_regime.startswith("Quadrant B")
    assert result.equity_profile_guidance.primary_profile_code == "stock_b_type"
    assert result.equity_profile_guidance.secondary_profile_code == "stock_c_type"


def test_quadrant_a_maps_to_stock_d_type_with_exit_discipline() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=3.50,
            rate_direction_medium_term="easing",
            rate_impulse_short="confirming_easing",
            balance_sheet_direction_medium_term="expanding",
            balance_sheet_pace="expanding_same_or_faster",
        )
    )

    assert result.primary_regime.startswith("Quadrant A")
    assert result.equity_profile_guidance.primary_profile_code == "stock_d_type"
    assert result.equity_profile_guidance.exit_discipline_required is True


def test_d_to_c_transition_surfaces_emerging_stock_c_type() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=4.50,
            rate_direction_medium_term="tightening",
            rate_impulse_short="stable",
            balance_sheet_direction_medium_term="contracting",
            balance_sheet_pace="contracting_slower",
        )
    )

    assert result.primary_regime.startswith("Quadrant D")
    assert result.equity_profile_guidance.primary_profile_code == "stock_a_type"
    assert result.equity_profile_guidance.emerging_profile_code == "stock_c_type"
