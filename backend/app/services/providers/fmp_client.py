"""
Financial Modeling Prep (FMP) provider — used for transcript cohort forward-P/E baskets.

Endpoints used:
  GET /stable/profile?symbol=AAPL,MSFT,...  — market cap, price, shares outstanding
  GET /stable/analyst-estimates?symbol=X&period=annual&limit=4  — forward EPS consensus

Field-name adapter:
  FMP field names can vary across endpoint versions.  All lookups go through
  helper functions that try multiple candidate keys in priority order so the
  basket computation does not break on minor API changes.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import httpx

from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FMP_BASE = "https://financialmodelingprep.com/stable"

MAG7_TICKERS: list[str] = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]

# ---------------------------------------------------------------------------
# Internal helpers — field-name adapter
# ---------------------------------------------------------------------------

def _get_market_cap(profile: dict) -> float | None:
    """Try multiple FMP field names for market cap, fall back to price × shares."""
    for key in ("mktCap", "marketCap", "market_cap"):
        v = profile.get(key)
        if _positive_finite(v):
            return float(v)
    # derived fallback
    price = _get_price(profile)
    shares = _get_shares(profile)
    if price is not None and shares is not None:
        return price * shares
    return None


def _get_shares(profile: dict) -> float | None:
    for key in ("sharesOutstanding", "outstandingShares", "shares", "shareOutstanding"):
        v = profile.get(key)
        if _positive_finite(v):
            return float(v)
    # Derived fallback: shares = marketCap / price
    mktcap = None
    for key in ("mktCap", "marketCap", "market_cap"):
        v = profile.get(key)
        if _positive_finite(v):
            mktcap = float(v)
            break
    price = _get_price(profile)
    if mktcap is not None and price is not None and price > 0:
        return mktcap / price
    return None


def _get_price(profile: dict) -> float | None:
    for key in ("price", "stockPrice", "currentPrice"):
        v = profile.get(key)
        if _positive_finite(v):
            return float(v)
    return None


def _get_forward_eps(estimate_row: dict) -> float | None:
    """Try multiple FMP field names for consensus forward EPS in an analyst-estimate row."""
    for key in ("epsAvg", "estimatedEpsAvg", "estimatedEpsMean", "epsMean",
                "epsEstimated", "estimatedEps", "consensusEps"):
        v = estimate_row.get(key)
        if _positive_finite(v):
            return float(v)
    return None


def _get_estimate_date(estimate_row: dict) -> datetime | None:
    for key in ("date", "period", "fiscalDateEnding", "fiscalYear"):
        v = estimate_row.get(key)
        if isinstance(v, str) and v:
            try:
                # Accept "YYYY-MM-DD" or "YYYY" formats
                if len(v) == 4:
                    return datetime(int(v), 12, 31, tzinfo=timezone.utc)
                return datetime.strptime(v[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _positive_finite(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x)) and float(x) > 0


# ---------------------------------------------------------------------------
# FMP HTTP helpers
# ---------------------------------------------------------------------------

def _fmp_get(path: str, params: dict, timeout: int) -> list | dict:
    """Single GET call to the FMP stable API; raises ProviderError on failure."""
    try:
        resp = httpx.get(
            f"{FMP_BASE}/{path}",
            params=params,
            timeout=timeout,
        )
    except Exception as exc:
        raise ProviderError(f"FMP HTTP error on {path}: {exc}") from exc

    if resp.status_code == 401:
        raise ProviderError("FMP API key rejected (HTTP 401) — check FMP_API_KEY in .env")
    if resp.status_code == 403:
        raise ProviderError("FMP API key forbidden (HTTP 403) — endpoint may require a paid plan")
    if not resp.is_success:
        raise ProviderError(f"FMP {path} returned HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        return resp.json()
    except Exception as exc:
        raise ProviderError(f"FMP {path} returned non-JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# FMP data fetchers
# ---------------------------------------------------------------------------

def fetch_profiles_batch(tickers: list[str], api_key: str, timeout: int) -> dict[str, dict]:
    """
    Fetch company profiles for multiple tickers via individual FMP calls.
    The /stable/profile endpoint does not support comma-separated batch requests.
    Returns {ticker: profile_dict}.
    """
    result: dict[str, dict] = {}
    for ticker in tickers:
        try:
            data = _fmp_get("profile", {"symbol": ticker, "apikey": api_key}, timeout)
        except ProviderError as exc:
            logger.warning("FMP profile fetch failed for %s: %s", ticker, exc)
            continue

        if not isinstance(data, list) or not data:
            logger.debug("FMP profile returned empty/unexpected for %s", ticker)
            continue

        result[ticker.upper()] = data[0]

    return result


def fetch_analyst_estimates(ticker: str, api_key: str, timeout: int) -> list[dict]:
    """
    Fetch annual analyst EPS estimates for a single ticker.
    Returns list of estimate rows (most recent first from FMP).
    """
    try:
        data = _fmp_get(
            "analyst-estimates",
            {"symbol": ticker, "period": "annual", "limit": "4", "apikey": api_key},
            timeout,
        )
    except ProviderError:
        raise

    if not isinstance(data, list):
        return []
    return data


# ---------------------------------------------------------------------------
# Raw constituent payloads for the deterministic rule layer
# ---------------------------------------------------------------------------

def _annual_eps_by_year(estimates: list[dict]) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in estimates:
        row_date = _get_estimate_date(row)
        eps = _get_forward_eps(row)
        if row_date is None or eps is None:
            continue
        out[row_date.year] = eps
    return out


def _annual_dates_by_year(estimates: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in estimates:
        row_date = _get_estimate_date(row)
        eps = _get_forward_eps(row)
        if row_date is None or eps is None:
            continue
        out[row_date.year] = row_date.strftime("%Y-%m-%d")
    return out


def fetch_constituent_payloads(
    tickers: list[str],
    *,
    api_key: str,
    timeout: int = 20,
) -> list[dict]:
    payloads: list[dict] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        profiles = fetch_profiles_batch(tickers, api_key, timeout)
    except ProviderError as exc:
        raise ProviderError(f"FMP profile batch failed: {exc}") from exc

    for ticker in tickers:
        profile = profiles.get(ticker, {})
        market_cap = _get_market_cap(profile)
        shares = _get_shares(profile)
        price = _get_price(profile)

        try:
            estimates = fetch_analyst_estimates(ticker, api_key, timeout)
        except ProviderError as exc:
            logger.warning("FMP analyst-estimates failed for %s: %s", ticker, exc)
            estimates = []

        payloads.append(
            {
                "ticker": ticker,
                "price": price,
                "shares": shares,
                "market_cap": market_cap,
                "annual_eps_by_year": _annual_eps_by_year(estimates),
                "estimate_dates_by_year": _annual_dates_by_year(estimates),
                "estimate_as_of": today,
            }
        )

    return payloads


def fetch_mag7_constituent_payloads(
    api_key: str,
    timeout: int = 20,
    tickers: list[str] | None = None,
) -> list[dict]:
    return fetch_constituent_payloads(
        tickers=tickers or MAG7_TICKERS,
        api_key=api_key,
        timeout=timeout,
    )
