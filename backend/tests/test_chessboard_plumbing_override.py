from app.schemas.dashboard_state import LiquidityPlumbing
from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_plumbing_support_not_qe_blocks_quadrant_a() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.00,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
    )
    plumbing = LiquidityPlumbing(
        state="severe",
        state_label="Funding stress",
        balance_sheet_expansion_not_qe=True,
    )

    result = compute_chessboard(liq, plumbing=plumbing)

    assert result.quadrant == "Unknown"
    assert result.chessboard.balance_sheet_direction_medium_term == "expanding"
    assert result.chessboard.effective_balance_sheet_direction == "flat_or_mixed"
    assert result.chessboard.balance_sheet_liquidity_interpretation == "plumbing_support_not_qe"


def test_plumbing_support_not_qe_blocks_quadrant_b() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.75,
        rate_direction_medium_term="tightening",
        rate_impulse_short="confirming_tightening",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
    )
    plumbing = LiquidityPlumbing(
        state="elevated",
        state_label="Plumbing stress",
        balance_sheet_expansion_not_qe=True,
    )

    result = compute_chessboard(liq, plumbing=plumbing)

    assert result.quadrant == "Unknown"
    assert result.chessboard.effective_balance_sheet_direction == "flat_or_mixed"
    assert result.chessboard.balance_sheet_liquidity_interpretation == "plumbing_support_not_qe"


def test_supportive_expansion_still_allows_quadrant_a_without_plumbing_stress() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.00,
        rate_direction_medium_term="easing",
        rate_impulse_short="confirming_easing",
        balance_sheet_direction_medium_term="expanding",
        balance_sheet_pace="expanding_same_or_faster",
    )
    plumbing = LiquidityPlumbing(
        state="normal",
        state_label="Normal",
        balance_sheet_expansion_not_qe=False,
    )

    result = compute_chessboard(liq, plumbing=plumbing)

    assert result.quadrant == "A"
    assert result.chessboard.effective_balance_sheet_direction == "expanding"
    assert result.chessboard.balance_sheet_liquidity_interpretation == "supportive_expansion"
