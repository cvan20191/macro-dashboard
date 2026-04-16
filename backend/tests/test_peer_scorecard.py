from datetime import date

from app.services.rules.peer_scorecard import PeerRaw, build_peer_scorecard


def _raw(
    ticker: str,
    *,
    sector: str = "Technology",
    industry: str | None = "Semiconductors",
    revenue_growth_yoy: float | None = 0.10,
    earnings_growth_yoy: float | None = 0.12,
    debt_to_ebitda: float | None = 1.5,
    current_eps: float = 5.0,
    next_eps: float = 6.0,
    current_revenue: float = 1000.0,
    next_revenue: float = 1100.0,
    price: float = 100.0,
    shares: float = 10.0,
) -> PeerRaw:
    return PeerRaw(
        ticker=ticker,
        sector=sector,
        industry=industry,
        annual_eps_by_year={2026: current_eps, 2027: next_eps},
        annual_revenue_by_year={2026: current_revenue, 2027: next_revenue},
        estimate_dates_by_year={2026: "2026-12-31", 2027: "2027-12-31"},
        price=price,
        shares=shares,
        revenue_growth_yoy=revenue_growth_yoy,
        earnings_growth_yoy=earnings_growth_yoy,
        debt_to_ebitda=debt_to_ebitda,
    )


def test_peer_scorecard_uses_same_industry_peers_first():
    target = _raw("AAA", industry="Software")
    peers = [
        _raw("BBB", industry="Software"),
        _raw("CCC", industry="Software"),
        _raw("DDD", industry="Software"),
        _raw("EEE", industry="Hardware"),
    ]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert "BBB" in card.peer_tickers
    assert "CCC" in card.peer_tickers
    assert "DDD" in card.peer_tickers
    assert "EEE" not in card.peer_tickers


def test_peer_scorecard_falls_back_to_same_sector_when_industry_missing():
    target = _raw("AAA", sector="Healthcare", industry=None)
    peers = [
        _raw("BBB", sector="Healthcare", industry="Biotech"),
        _raw("CCC", sector="Healthcare", industry="Pharma"),
        _raw("DDD", sector="Healthcare", industry="Devices"),
        _raw("EEE", sector="Technology", industry="Software"),
    ]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert "BBB" in card.peer_tickers
    assert "CCC" in card.peer_tickers
    assert "DDD" in card.peer_tickers
    assert "EEE" not in card.peer_tickers


def test_lower_forward_pe_and_lower_debt_to_ebitda_are_more_favorable():
    target = _raw("AAA", current_eps=10.0, next_eps=12.0, price=100.0, debt_to_ebitda=1.0)
    peers = [
        _raw("BBB", current_eps=5.0, next_eps=6.0, price=100.0, debt_to_ebitda=3.0),
        _raw("CCC", current_eps=4.0, next_eps=5.0, price=100.0, debt_to_ebitda=4.0),
        _raw("DDD", current_eps=3.0, next_eps=4.0, price=100.0, debt_to_ebitda=5.0),
    ]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.forward_pe.favorable_percentile is not None
    assert card.debt_to_ebitda.favorable_percentile is not None
    assert card.forward_pe.signal == "better_than_peers"
    assert card.debt_to_ebitda.signal == "better_than_peers"


def test_higher_growth_is_more_favorable():
    target = _raw("AAA", revenue_growth_yoy=0.25, earnings_growth_yoy=0.30)
    peers = [
        _raw("BBB", revenue_growth_yoy=0.10, earnings_growth_yoy=0.12),
        _raw("CCC", revenue_growth_yoy=0.08, earnings_growth_yoy=0.10),
        _raw("DDD", revenue_growth_yoy=0.05, earnings_growth_yoy=0.07),
    ]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.revenue_growth.signal == "better_than_peers"
    assert card.earnings_growth.signal == "better_than_peers"


def test_high_r_squared_cheap_vs_growth_upgrades_balanced_name():
    peers = [
        _raw("P1", current_eps=4.0, next_eps=4.4, price=80.0, shares=10.0, revenue_growth_yoy=0.12, earnings_growth_yoy=0.12, debt_to_ebitda=1.2),
        _raw("P2", current_eps=4.0, next_eps=4.8, price=96.0, shares=10.0, revenue_growth_yoy=0.16, earnings_growth_yoy=0.16, debt_to_ebitda=1.4),
        _raw("P3", current_eps=4.0, next_eps=5.2, price=114.4, shares=10.0, revenue_growth_yoy=0.20, earnings_growth_yoy=0.20, debt_to_ebitda=1.6),
        _raw("P4", current_eps=4.0, next_eps=5.6, price=134.4, shares=10.0, revenue_growth_yoy=0.24, earnings_growth_yoy=0.24, debt_to_ebitda=1.8),
        _raw("P5", current_eps=4.0, next_eps=6.0, price=156.0, shares=10.0, revenue_growth_yoy=0.28, earnings_growth_yoy=0.28, debt_to_ebitda=2.0),
    ]
    target = _raw(
        "TGT",
        current_eps=4.0,
        next_eps=5.4,
        price=102.6,
        shares=10.0,
        revenue_growth_yoy=0.21,
        earnings_growth_yoy=0.21,
        debt_to_ebitda=1.7,
    )

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.valuation_vs_growth_fit.weighting_active is True
    assert card.valuation_vs_growth_fit.fit_signal == "undervalued_vs_growth"
    assert card.verdict == "leader"


def test_high_r_squared_rich_vs_growth_downgrades_name():
    peers = [
        _raw("P1", current_eps=4.0, next_eps=4.4, price=80.0, shares=10.0, revenue_growth_yoy=0.12, earnings_growth_yoy=0.12, debt_to_ebitda=1.2),
        _raw("P2", current_eps=4.0, next_eps=4.8, price=96.0, shares=10.0, revenue_growth_yoy=0.16, earnings_growth_yoy=0.16, debt_to_ebitda=1.4),
        _raw("P3", current_eps=4.0, next_eps=5.2, price=114.4, shares=10.0, revenue_growth_yoy=0.20, earnings_growth_yoy=0.20, debt_to_ebitda=1.6),
        _raw("P4", current_eps=4.0, next_eps=5.6, price=134.4, shares=10.0, revenue_growth_yoy=0.24, earnings_growth_yoy=0.24, debt_to_ebitda=1.8),
        _raw("P5", current_eps=4.0, next_eps=6.0, price=156.0, shares=10.0, revenue_growth_yoy=0.28, earnings_growth_yoy=0.28, debt_to_ebitda=2.0),
    ]
    target = _raw(
        "TGT",
        current_eps=4.0,
        next_eps=4.8,
        price=163.2,
        shares=10.0,
        revenue_growth_yoy=0.20,
        earnings_growth_yoy=0.20,
        debt_to_ebitda=1.8,
    )

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.valuation_vs_growth_fit.weighting_active is True
    assert card.valuation_vs_growth_fit.fit_signal == "overvalued_vs_growth"
    assert card.verdict == "fragile"


def test_low_r_squared_fit_does_not_override_core_verdict():
    peers = [
        _raw("P1", current_eps=4.0, next_eps=4.2, price=150.0, shares=10.0, revenue_growth_yoy=0.15, earnings_growth_yoy=0.15, debt_to_ebitda=1.4),
        _raw("P2", current_eps=4.0, next_eps=5.0, price=90.0, shares=10.0, revenue_growth_yoy=0.16, earnings_growth_yoy=0.16, debt_to_ebitda=1.5),
        _raw("P3", current_eps=4.0, next_eps=4.4, price=170.0, shares=10.0, revenue_growth_yoy=0.17, earnings_growth_yoy=0.17, debt_to_ebitda=1.6),
        _raw("P4", current_eps=4.0, next_eps=5.6, price=95.0, shares=10.0, revenue_growth_yoy=0.18, earnings_growth_yoy=0.18, debt_to_ebitda=1.7),
        _raw("P5", current_eps=4.0, next_eps=4.8, price=160.0, shares=10.0, revenue_growth_yoy=0.19, earnings_growth_yoy=0.19, debt_to_ebitda=1.8),
    ]
    target = _raw(
        "TGT",
        current_eps=4.0,
        next_eps=5.2,
        price=110.0,
        shares=10.0,
        revenue_growth_yoy=0.17,
        earnings_growth_yoy=0.17,
        debt_to_ebitda=1.6,
    )

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.valuation_vs_growth_fit.weighting_active is False
    assert card.verdict == "balanced"


def test_insufficient_peer_coverage_yields_insufficient():
    target = _raw("AAA")
    peers = [_raw("BBB")]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.verdict == "insufficient"
