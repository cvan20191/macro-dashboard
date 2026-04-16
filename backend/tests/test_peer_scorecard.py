from datetime import date

from app.services.rules.peer_scorecard import PeerRaw, build_peer_scorecard


def _raw(
    ticker: str,
    *,
    sector: str = "Technology",
    industry: str | None = "Software",
    revenue_growth_yoy: float | None = 0.10,
    earnings_growth_yoy: float | None = 0.12,
    debt_to_ebitda: float | None = 1.5,
    current_eps: float = 5.0,
    next_eps: float = 6.0,
    current_revenue: float = 1000.0,
    next_revenue: float = 1100.0,
    current_fye: str = "2026-12-31",
    next_fye: str = "2027-12-31",
    price: float = 100.0,
    shares: float = 10.0,
) -> PeerRaw:
    return PeerRaw(
        ticker=ticker,
        sector=sector,
        industry=industry,
        annual_eps_by_year={2026: current_eps, 2027: next_eps},
        annual_revenue_by_year={2026: current_revenue, 2027: next_revenue},
        estimate_dates_by_year={2026: current_fye, 2027: next_fye},
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


def test_directional_only_forward_pe_is_excluded_from_hard_peer_verdict():
    target = _raw("TGT")
    peers = [
        _raw("P1"),
        _raw("P2"),
        _raw("P3"),
        _raw("P4"),
        _raw("P5"),
    ]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 8, 15))

    assert card.forward_pe.signal_mode == "directional_only"
    assert card.forward_pe.hard_actionable is False
    assert card.forward_pe.signal == "unknown"
    assert card.valuation_vs_growth_fit.fit_signal == "insufficient"
    assert "directional-only" in (card.note or "")


def test_high_r_squared_cheap_vs_growth_upgrades_only_when_forward_pe_is_actionable():
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

    assert card.forward_pe.signal_mode == "actionable"
    assert card.forward_pe.hard_actionable is True
    assert card.valuation_vs_growth_fit.weighting_active is True
    assert card.valuation_vs_growth_fit.fit_signal == "undervalued_vs_growth"
    assert card.verdict == "leader"


def test_low_confidence_fit_does_not_override_core_verdict():
    peers = [
        _raw("P1", current_eps=4.0, next_eps=4.2, price=150.0, shares=10.0),
        _raw("P2", current_eps=4.0, next_eps=5.0, price=90.0, shares=10.0),
        _raw("P3", current_eps=4.0, next_eps=4.4, price=170.0, shares=10.0),
        _raw("P4", current_eps=4.0, next_eps=5.6, price=95.0, shares=10.0),
        _raw("P5", current_eps=4.0, next_eps=4.8, price=160.0, shares=10.0),
    ]
    target = _raw("TGT", current_eps=4.0, next_eps=5.2, price=110.0, shares=10.0)

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.valuation_vs_growth_fit.weighting_active is False


def test_insufficient_peer_coverage_yields_insufficient():
    target = _raw("AAA")
    peers = [_raw("BBB")]

    card = build_peer_scorecard(target=target, peers=peers, as_of=date(2026, 6, 1))

    assert card.verdict == "insufficient"
