from __future__ import annotations

from app.schemas.dashboard_state import FedChessboard, MarketEasingExpectations


def pricing_stretch_blocks_new_buys(
    *,
    fed_chessboard: FedChessboard | None,
    market_priced_easing: MarketEasingExpectations | None,
) -> bool:
    if market_priced_easing is None or not market_priced_easing.pricing_stretch_active:
        return False

    if fed_chessboard is None:
        return False

    quadrant = fed_chessboard.quadrant or "Unknown"
    transition_path = fed_chessboard.liquidity_transition_path or "none"

    if quadrant in {"A", "B", "C"}:
        return True

    if quadrant == "D" and transition_path == "D_to_C":
        return True

    return False
