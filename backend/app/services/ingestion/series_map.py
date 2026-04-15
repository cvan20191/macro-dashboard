"""
Central mapping of all series IDs, tickers, and freshness expectations.

Keeping everything here prevents scattered magic strings across provider files.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# FRED series identifiers
# ---------------------------------------------------------------------------
FRED_SERIES: dict[str, str] = {
    # Monetary policy
    "fed_funds_rate":     "DFEDTARU",        # Fed Funds target upper bound, daily
    "balance_sheet":      "WALCL",           # Total assets (Fed balance sheet), weekly
    # Keep the logical key for compatibility, but drive plumbing from reserve balances
    # with Federal Reserve Banks so the overlay reacts on a weekly cadence.
    "total_reserves":     "WRESBAL",         # Reserve balances with Federal Reserve Banks, weekly
    "repo_total":         "RPTTLD",          # Total repo operations, daily
    "reverse_repo_total": "RRPTTLD",         # Total reverse repo operations, daily
    # Labour
    "unemployment_rate":  "UNRATE",          # Unemployment rate, monthly
    "initial_claims":     "ICSA",            # Initial jobless claims, weekly
    "nonfarm_payrolls":   "PAYEMS",          # Nonfarm payrolls, monthly
    # Inflation (verified FRED series IDs)
    "headline_cpi":       "CPIAUCSL",        # Headline CPI index, SA, monthly
    "core_cpi":           "CPILFESL",        # Core CPI index, SA, monthly
    "shelter_cpi":        "CUSR0000SAH1",    # CPI Shelter, monthly
    "services_ex_energy": "CUSR0000SASLE",   # CPI Services less energy (verified working)
    # Stress
    "yield_curve":        "T10Y2Y",          # 10Y-2Y Treasury spread, daily
    "npl_ratio":          "DRALACBS",        # Delinquency Rate on All Loans, All Commercial Banks, quarterly
    "cre_delinquency":    "DRSREACBS",       # Delinquency rate on loans secured by real estate, quarterly
    "credit_card_chargeoff": "CORCCACBN",    # Credit card charge-off rate (%), quarterly, NSA
    # Z.1 L.223 all sectors corporate equities market value — FRED units: millions USD
    "equity_market_value_z1": "BOGZ1LM893064105Q",
    "m2":                 "WM2NS",           # M2 money stock, weekly (billions USD)
}

# ---------------------------------------------------------------------------
# Yahoo Finance tickers
# ---------------------------------------------------------------------------
YAHOO_TICKERS: dict[str, str] = {
    "wti_oil":            "CL=F",       # WTI Crude front-month futures
    "dxy":                "DX-Y.NYB",   # US Dollar Index
    "nasdaq_etf":         "QQQ",        # Nasdaq proxy for trailing P/E context
    "sp500_etf":          "SPY",        # S&P 500 for market-cap proxy
}

# ---------------------------------------------------------------------------
# Freshness windows — how old a series can be before being flagged stale
# (in calendar days)
#
# FRED sets observed_at to the observation's *economic* date (quarter-end,
# week-ending Monday, CPI reference month, etc.), not the publication date.
# Windows must allow that lag or most monthly/quarterly series read as stale.
# ---------------------------------------------------------------------------
FRESHNESS_RULES: dict[str, int] = {
    "fed_funds_rate":     5,    # daily series, allow weekend gap
    "balance_sheet":      14,   # weekly (H.4.1 releases Thursdays, allow 2 weeks)
    "total_reserves":     14,   # weekly reserve balances (H.4.1), allow 2 weeks
    "repo_total":         10,   # daily
    "reverse_repo_total": 10,   # daily
    "unemployment_rate":  65,   # monthly (BLS releases ~4 weeks after month-end)
    "initial_claims":     14,   # weekly (Thursday release)
    "nonfarm_payrolls":   65,   # monthly (BLS first Friday of following month)
    "headline_cpi":       100,  # monthly index date lags calendar; BLS mid-month release
    "core_cpi":           100,  # monthly index date lags calendar; BLS mid-month release
    "shelter_cpi":        100,
    "services_ex_energy": 100,
    "yield_curve":        5,    # daily
    "npl_ratio":          200,  # quarterly; obs date is quarter-end, can be 5–6 months “old” vs today
    "cre_delinquency":    200,
    "credit_card_chargeoff": 200,
    "equity_market_value_z1": 200,
    "m2":                 45,   # weekly; observed_at is week-ending Monday, not publish day — 20d was too tight
    "wti_oil":            5,    # daily market
    "dxy":                5,
    "nasdaq_etf":         5,
    "sp500_etf":          5,
    "forward_pe":         5,   # Mag 7 basket (FMP) or QQQ proxy (Yahoo) — treat as daily quote
    "pmi_manufacturing":  65,   # monthly (ISM releases first business day of month)
    "pmi_services":       65,
}

# ---------------------------------------------------------------------------
# Provider name labels (for source metadata)
# ---------------------------------------------------------------------------
PROVIDER_FRED = "FRED"
PROVIDER_YAHOO = "Yahoo Finance"
PROVIDER_FMP = "FMP"
PROVIDER_STUB = "stub"
