from app.schemas.dashboard_state import LiquidityPlumbing
from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_missing_doctrine_inputs_resolve_to_unknown() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.25,
        balance_sheet_assets=6_700_000.0,
        rate_direction_medium_term=None,
        rate_impulse_short=None,
        balance_sheet_direction_medium_term=None,
        balance_sheet_pace=None,
    )

    result = compute_chessboard(liq, plumbing=LiquidityPlumbing())

    assert result.quadrant == "Unknown"
    assert result.chessboard.label == "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"


def test_actual_d_can_transition_toward_c_when_qt_is_slowing() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.50,
        balance_sheet_assets=6_700_000.0,
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
        balance_sheet_assets=6_700_000.0,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "C"
    assert result.chessboard.liquidity_transition_path == "none"
    assert result.chessboard.transition_tag == "Improving"


def test_qt_slowing_never_counts_as_expansion() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.50,
        balance_sheet_assets=6_700_000.0,
        rate_direction_medium_term="tightening",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
    )

    result = compute_chessboard(liq)

    assert result.chessboard.balance_sheet_direction_medium_term == "contracting"
    assert result.quadrant not in {"A", "B"}


def test_qt_slowing_stays_c_without_any_legacy_window_fields() -> None:
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
    assert result.chessboard.transition_tag == "Improving"
    assert result.chessboard.balance_sheet_direction_medium_term == "contracting"
