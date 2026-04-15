from app.schemas.dashboard_state import LiquidityPlumbing
from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard
from app.services.rules.exit_discipline import compute_exit_discipline_signal


def test_clean_a_regime_has_no_exit_signal() -> None:
    liq = LiquidityInput(
        fed_funds_rate=3.50,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
    )
    cb = compute_chessboard(liq, plumbing=LiquidityPlumbing())

    result = compute_exit_discipline_signal(cb)

    assert cb.quadrant == "A"
    assert result.active is False
    assert result.signal.scope == "stock_d_type_a_regime"
    assert result.signal.rate_reversal_watch_active is False
    assert result.signal.qe_fade_watch_active is False


def test_a_regime_mixed_rate_impulse_activates_rate_reversal_watch() -> None:
    liq = LiquidityInput(
        fed_funds_rate=3.50,
        rate_direction_medium_term="easing",
        rate_impulse_short="mixed",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
    )
    cb = compute_chessboard(liq, plumbing=LiquidityPlumbing())

    result = compute_exit_discipline_signal(cb)

    assert cb.quadrant == "A"
    assert result.active is True
    assert result.signal.rate_reversal_watch_active is True
    assert result.signal.qe_fade_watch_active is False


def test_a_regime_expanding_slower_activates_qe_fade_watch() -> None:
    liq = LiquidityInput(
        fed_funds_rate=3.50,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_slower",
    )
    cb = compute_chessboard(liq, plumbing=LiquidityPlumbing())

    result = compute_exit_discipline_signal(cb)

    assert cb.quadrant == "A"
    assert result.active is True
    assert result.signal.rate_reversal_watch_active is False
    assert result.signal.qe_fade_watch_active is True


def test_non_a_regime_never_surfaces_a_regime_exit_signal() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.75,
        rate_direction_medium_term="tightening",
        rate_impulse_short="confirming_tightening",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_same_or_faster",
    )
    cb = compute_chessboard(liq, plumbing=LiquidityPlumbing())

    result = compute_exit_discipline_signal(cb)

    assert cb.quadrant == "D"
    assert result.active is False
    assert result.signal.scope == "none"
