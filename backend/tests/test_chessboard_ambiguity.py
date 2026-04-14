from __future__ import annotations

from app.schemas.indicator_snapshot import LiquidityInput
from app.services.rules.chessboard import compute_chessboard


def test_ambiguous_liquidity_does_not_default_to_c() -> None:
    liq = LiquidityInput(
        fed_funds_rate=4.5,
        rate_trend_1m="flat",
        rate_trend_3m="flat",
        balance_sheet_assets=6_800_000.0,
        balance_sheet_trend_1m="flat",
        balance_sheet_trend_3m="down",
        rate_cycle_position=0.65,
    )

    result = compute_chessboard(liq)

    assert result.quadrant == "Unknown"
    assert result.chessboard.label == "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"
    assert result.liquidity_improving is False
    assert result.liquidity_tight is False
