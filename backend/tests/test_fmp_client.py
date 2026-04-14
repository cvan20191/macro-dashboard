from __future__ import annotations

from app.services.providers import fmp_client
from app.services.providers.fmp_client import _annual_eps_by_year, _get_price, fetch_mag7_constituent_payloads


def test_get_price_does_not_use_last_annual_dividend() -> None:
    assert _get_price({"lastAnnualDividend": 4.25}) is None


def test_annual_eps_by_year_extracts_raw_year_buckets() -> None:
    estimates = [
        {"date": "2026-12-31", "epsAvg": 10.0},
        {"date": "2027-12-31", "epsAvg": 12.0},
        {"date": "bad-date", "epsAvg": 99.0},
    ]

    assert _annual_eps_by_year(estimates) == {2026: 10.0, 2027: 12.0}


def test_fetch_mag7_constituent_payloads_returns_raw_annual_estimate_payloads(monkeypatch) -> None:
    monkeypatch.setattr(
        fmp_client,
        "fetch_profiles_batch",
        lambda tickers, api_key, timeout: {
            "AAPL": {
                "price": 200.0,
                "sharesOutstanding": 100.0,
                "mktCap": 20_000.0,
            }
        },
    )
    monkeypatch.setattr(
        fmp_client,
        "fetch_analyst_estimates",
        lambda ticker, api_key, timeout: [
            {"date": "2026-12-31", "epsAvg": 10.0},
            {"date": "2027-12-31", "epsAvg": 12.0},
        ],
    )

    payloads = fetch_mag7_constituent_payloads(api_key="demo", timeout=5, tickers=["AAPL"])

    assert payloads == [
        {
            "ticker": "AAPL",
            "price": 200.0,
            "shares": 100.0,
            "market_cap": 20_000.0,
            "annual_eps_by_year": {2026: 10.0, 2027: 12.0},
            "estimate_as_of": payloads[0]["estimate_as_of"],
        }
    ]
