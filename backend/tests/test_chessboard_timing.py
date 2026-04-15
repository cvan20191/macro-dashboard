from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_actual_d_can_transition_toward_c_when_qt_is_slowing() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.50,
        rate_direction_medium_term="tightening",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "D"
    assert result.chessboard.liquidity_transition_path == "D_to_C"
    assert result.chessboard.transition_tag == "Improving"
    assert result.liquidity_improving is True
    assert result.liquidity_tight is False


def test_actual_c_after_policy_path_turns_easing() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.liquidity_transition_path == "none"
    assert result.chessboard.transition_tag == "Improving"
    assert result.chessboard.policy_stance is None


def test_qt_slowing_never_counts_as_expansion() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.50,
        rate_direction_medium_term="tightening",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.chessboard.balance_sheet_direction_medium_term == "contracting"
    assert result.quadrant not in {"A", "B"}


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
    assert result.chessboard.liquidity_transition_path == "none"
    assert result.chessboard.label == "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"
