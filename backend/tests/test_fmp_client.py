from __future__ import annotations

from app.services.providers import fmp_client
from app.services.providers.fmp_client import (
    _annual_dates_by_year,
    _annual_eps_by_year,
    _get_price,
    fetch_constituent_payloads,
    fetch_income_statement_growth,
    fetch_mag7_constituent_payloads,
    fetch_key_metrics_ttm,
    fetch_stock_peers,
)


def test_get_price_does_not_use_last_annual_dividend() -> None:
    assert _get_price({"lastAnnualDividend": 4.25}) is None


def test_annual_eps_by_year_extracts_raw_year_buckets() -> None:
    estimates = [
        {"date": "2026-12-31", "epsAvg": 10.0},
        {"date": "2027-12-31", "epsAvg": 12.0},
        {"date": "bad-date", "epsAvg": 99.0},
    ]

    assert _annual_eps_by_year(estimates) == {2026: 10.0, 2027: 12.0}


def test_annual_dates_by_year_extracts_raw_year_buckets() -> None:
    estimates = [
        {"date": "2026-12-31", "epsAvg": 10.0},
        {"date": "2027-12-31", "epsAvg": 12.0},
        {"date": "bad-date", "epsAvg": 99.0},
    ]

    assert _annual_dates_by_year(estimates) == {
        2026: "2026-12-31",
        2027: "2027-12-31",
    }


def test_fetch_constituent_payloads_returns_raw_annual_estimate_payloads(monkeypatch) -> None:
    monkeypatch.setattr(
        fmp_client,
        "fetch_profiles_batch",
        lambda tickers, api_key, timeout: {
            "AAPL": {
                "price": 200.0,
                "sharesOutstanding": 100.0,
                "mktCap": 20_000.0,
                "sector": "Technology",
                "industry": "Consumer Electronics",
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

    payloads = fetch_constituent_payloads(
        tickers=["AAPL"],
        api_key="demo",
        timeout=5,
    )

    assert payloads == [
        {
            "ticker": "AAPL",
            "price": 200.0,
            "shares": 100.0,
            "market_cap": 20_000.0,
            "annual_eps_by_year": {2026: 10.0, 2027: 12.0},
            "annual_revenue_by_year": {},
            "estimate_dates_by_year": {2026: "2026-12-31", 2027: "2027-12-31"},
            "estimate_as_of": payloads[0]["estimate_as_of"],
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
    ]


def test_fetch_mag7_constituent_payloads_wraps_generic_fetcher(monkeypatch) -> None:
    monkeypatch.setattr(
        fmp_client,
        "fetch_constituent_payloads",
        lambda *, tickers, api_key, timeout: [{"ticker": tickers[0], "api_key": api_key, "timeout": timeout}],
    )

    payloads = fetch_mag7_constituent_payloads(api_key="demo", timeout=5, tickers=["AAPL"])

    assert payloads == [{"ticker": "AAPL", "api_key": "demo", "timeout": 5}]


def test_fetch_stock_peers_extracts_peer_symbols(monkeypatch) -> None:
    monkeypatch.setattr(
        fmp_client,
        "_fmp_get",
        lambda path, params, timeout: [
            {"symbol": "MSFT"},
            {"symbol": "NVDA"},
            {"symbol": "AAPL"},
        ],
    )

    assert fetch_stock_peers("AAPL", api_key="demo", timeout=5) == ["MSFT", "NVDA"]


def test_fetch_income_statement_growth_and_key_metrics_return_first_row(monkeypatch) -> None:
    def _fake_get(path, params, timeout):
        if path == "income-statement-growth":
            return [{"growthRevenue": 0.2}]
        if path == "key-metrics-ttm":
            return [{"netDebtToEBITDA": 1.5}]
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(fmp_client, "_fmp_get", _fake_get)

    assert fetch_income_statement_growth("AAPL", api_key="demo", timeout=5) == {"growthRevenue": 0.2}
    assert fetch_key_metrics_ttm("AAPL", api_key="demo", timeout=5) == {"netDebtToEBITDA": 1.5}
