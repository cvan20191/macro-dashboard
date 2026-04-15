from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_three_month_legacy_noise_is_not_the_public_doctrine_driver() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        rate_trend_1m="flat",
        rate_trend_3m="down",
        balance_sheet_assets=6_700_000.0,
        balance_sheet_trend_1m="down",
        balance_sheet_trend_3m="down",
        rate_cycle_position=0.70,
        rate_direction_medium_term="easing",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_same_or_faster",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.rate_direction_medium_term == "easing"
    assert result.chessboard.balance_sheet_direction_medium_term == "contracting"


def test_qt_slowing_stays_c_and_marks_improving() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        rate_direction_medium_term="easing",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.transition_tag == "Improving"
    assert result.chessboard.balance_sheet_pace == "contracting_slower"


def test_unknown_when_medium_term_path_is_not_clean() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        rate_direction_medium_term="stable",
        rate_impulse_short="mixed",
        balance_sheet_direction_medium_term="flat_or_mixed",
        balance_sheet_pace="flat_or_mixed",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "Unknown"
    assert result.chessboard.label == "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"
