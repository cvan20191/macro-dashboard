from app.schemas.dashboard_state import FedChessboard, MarketEasingExpectations
from app.services.rules.market_pricing_guard import pricing_stretch_blocks_new_buys


def test_fresh_stretch_blocks_new_buys() -> None:
    fed_chessboard = FedChessboard(
        quadrant="C",
        liquidity_transition_path="none",
        transition_tag="Improving",
    )
    market_priced_easing = MarketEasingExpectations(
        expected_cut_bps_rest_of_year=50.0,
        expected_cut_count_rest_of_year=2.0,
        pricing_horizon_label="rest_of_calendar_year",
        pricing_stretch_active=True,
        freshness_status="fresh",
        hard_actionable=True,
    )

    assert pricing_stretch_blocks_new_buys(
        fed_chessboard=fed_chessboard,
        market_priced_easing=market_priced_easing,
    ) is True


def test_stale_stretch_does_not_block_new_buys() -> None:
    fed_chessboard = FedChessboard(
        quadrant="C",
        liquidity_transition_path="none",
        transition_tag="Improving",
    )
    market_priced_easing = MarketEasingExpectations(
        expected_cut_bps_rest_of_year=50.0,
        expected_cut_count_rest_of_year=2.0,
        pricing_horizon_label="rest_of_calendar_year",
        pricing_stretch_active=True,
        freshness_status="stale",
        hard_actionable=False,
    )

    assert pricing_stretch_blocks_new_buys(
        fed_chessboard=fed_chessboard,
        market_priced_easing=market_priced_easing,
    ) is False


def test_pricing_stretch_does_not_change_true_defensive_d() -> None:
    fed_chessboard = FedChessboard(
        quadrant="D",
        liquidity_transition_path="none",
        transition_tag="Deteriorating",
    )
    market_priced_easing = MarketEasingExpectations(
        expected_cut_bps_rest_of_year=50.0,
        expected_cut_count_rest_of_year=2.0,
        pricing_horizon_label="rest_of_calendar_year",
        pricing_stretch_active=True,
        freshness_status="fresh",
        hard_actionable=True,
    )

    assert pricing_stretch_blocks_new_buys(
        fed_chessboard=fed_chessboard,
        market_priced_easing=market_priced_easing,
    ) is False
