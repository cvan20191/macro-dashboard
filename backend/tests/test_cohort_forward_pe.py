from datetime import date

from app.services.rules.cohort_forward_pe import compute_cohort_forward_pe_baskets


def _payload(
    ticker: str,
    *,
    price: float = 100.0,
    shares: float = 10.0,
    current_eps: float | None = 5.0,
    next_eps: float | None = 6.0,
) -> dict:
    annual_eps_by_year = {}
    estimate_dates_by_year = {}
    if current_eps is not None:
        annual_eps_by_year[2026] = current_eps
        estimate_dates_by_year[2026] = "2026-12-31"
    if next_eps is not None:
        annual_eps_by_year[2027] = next_eps
        estimate_dates_by_year[2027] = "2027-12-31"

    return {
        "ticker": ticker,
        "price": price,
        "shares": shares,
        "annual_eps_by_year": annual_eps_by_year,
        "estimate_dates_by_year": estimate_dates_by_year,
        "estimate_as_of": "2026-04-15",
    }


def test_all_transcript_cohorts_are_surfaced_from_registry() -> None:
    registry = {
        "mag7": {"label": "Mag 7", "tickers": ["AAPL", "MSFT"], "note": "A"},
        "non_mag7_ai": {"label": "Non-Mag7 AI", "tickers": ["ORCL", "PLTR"], "note": "B"},
        "non_ai_high_valuation": {"label": "High Valuation Non-AI", "tickers": ["COST"], "note": "C"},
        "non_ai_low_valuation_defensive": {"label": "Defensive", "tickers": ["BMY", "PFE"], "note": "D"},
    }
    payloads = [
        _payload("AAPL"),
        _payload("MSFT"),
        _payload("ORCL"),
        _payload("PLTR"),
        _payload("COST"),
        _payload("BMY"),
        _payload("PFE"),
    ]

    baskets = compute_cohort_forward_pe_baskets(
        payloads=payloads,
        as_of=date(2026, 6, 1),
        registry=registry,
    )

    assert [basket.cohort_code for basket in baskets] == [
        "mag7",
        "non_mag7_ai",
        "non_ai_high_valuation",
        "non_ai_low_valuation_defensive",
    ]


def test_incomplete_cohort_stays_directional_only() -> None:
    registry = {
        "non_mag7_ai": {"label": "Non-Mag7 AI", "tickers": ["ORCL", "PLTR"], "note": "B"},
    }
    payloads = [
        _payload("ORCL"),
        _payload("PLTR", next_eps=None),
    ]

    baskets = compute_cohort_forward_pe_baskets(
        payloads=payloads,
        as_of=date(2026, 11, 15),
        registry=registry,
    )

    basket = baskets[0]
    assert basket.cohort_code == "non_mag7_ai"
    assert basket.signal_mode == "directional_only"
    assert basket.coverage_ratio < 1.0
