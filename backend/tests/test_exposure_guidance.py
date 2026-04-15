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


def test_quadrant_d_exposure_cap_is_20_percent() -> None:
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
    assert result.exposure_guidance.max_cash_deployment_pct == 20
    assert result.exposure_guidance.leverage_allowed is False


def test_quadrant_b_exposure_cap_is_50_percent() -> None:
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
    assert result.exposure_guidance.max_cash_deployment_pct == 50
    assert result.exposure_guidance.leverage_allowed is False


def test_quadrant_a_allows_full_deployment_and_leverage() -> None:
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
    assert result.exposure_guidance.max_cash_deployment_pct == 100
    assert result.exposure_guidance.leverage_allowed is True


def test_unknown_exposure_cap_is_zero() -> None:
    result = _regime_for(
        LiquidityInput(
            fed_funds_rate=4.50,
            rate_direction_medium_term="stable",
            rate_impulse_short="stable",
            balance_sheet_direction_medium_term="flat_or_mixed",
            balance_sheet_pace="flat_or_mixed",
        )
    )

    assert result.primary_regime.startswith("Quadrant Unknown")
    assert result.exposure_guidance.max_cash_deployment_pct == 0
    assert result.exposure_guidance.leverage_allowed is False
