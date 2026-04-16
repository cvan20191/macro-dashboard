from __future__ import annotations

from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_ambiguous_liquidity_does_not_default_to_c() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.5,
        balance_sheet_assets=6_800_000.0,
        rate_direction_medium_term=None,
        rate_impulse_short=None,
        balance_sheet_direction_medium_term=None,
        balance_sheet_pace=None,
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "Unknown"
    assert result.chessboard.label == "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"
    assert result.liquidity_improving is False
    assert result.liquidity_tight is False


def test_one_month_noise_does_not_create_new_quadrant_by_itself() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        balance_sheet_assets=6_800_000.0,
        rate_direction_medium_term="easing",
        rate_impulse_short="mixed",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_same_or_faster",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.rate_direction_medium_term == "easing"
    assert result.chessboard.rate_impulse_short == "mixed"
    assert result.chessboard.balance_sheet_direction_medium_term == "contracting"


def test_contracting_but_slowing_qt_stays_c_not_expanding() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        balance_sheet_assets=6_700_000.0,
        rate_direction_medium_term="easing",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.effective_balance_sheet_direction == "contracting"
    assert result.chessboard.balance_sheet_pace == "contracting_slower"
    assert result.chessboard.transition_tag == "Improving"
