"""
Normalization layer — transforms raw FetchResult dict into IndicatorSnapshot.

Responsible for:
 - trend derivation from recent series
 - CPI YoY / status computation
 - oil risk inference
 - policy support heuristics
 - assembling the final IndicatorSnapshot
"""

from __future__ import annotations

import json
import logging
from statistics import median
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.schemas.indicator_snapshot import (
    DataFreshnessInput,
    DollarContextInput,
    GrowthInput,
    IndicatorSnapshot,
    InflationInput,
    LiquidityInput,
    PlumbingInput,
    PolicySupportInput,
    SystemicStressInput,
    ValuationInput,
)
from app.services.override_store import get_active_override
from app.services.providers.base import FetchResult
from app.services.providers.cpi_provider import compute_yoy_and_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trend helpers
# ---------------------------------------------------------------------------

_RATE_BPS_THRESHOLD = 0.10
_BALANCE_SHEET_DELTA_THRESHOLD = 25_000.0  # WALCL is in millions USD => 25B threshold
_UNEMPLOYMENT_DELTA_THRESHOLD = 0.05
_CLAIMS_PCT_THRESHOLD = 0.03
_PAYROLLS_DELTA_THRESHOLD = 25.0
_RATE_MOVE_RECENCY_DAYS = 120
_BALANCE_SHEET_REGIME_LOOKBACK_DAYS = 182
_BALANCE_SHEET_PACE_LOOKBACK_DAYS = 56
_BALANCE_SHEET_PREV_PACE_LOOKBACK_DAYS = 112
_PLUMBING_RESERVE_TREND_LOOKBACK_DAYS = 28
_PLUMBING_RESERVE_BUFFER_LOOKBACK_DAYS = 182
_PLUMBING_FLOW_TREND_LOOKBACK_DAYS = 28
_PLUMBING_FLOW_BUFFER_LOOKBACK_DAYS = 180


def _parse_series_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _sorted_points(series: list[tuple[str, float]]) -> list[tuple[date, float]]:
    points = [(_parse_series_date(d), v) for d, v in series]
    return [(d, v) for d, v in points if d is not None]


def _anchor_value(series: list[tuple[str, float]], lookback_days: int) -> tuple[float, float] | None:
    if len(series) < 2:
        return None
    parsed = _sorted_points(series)
    if len(parsed) < 2:
        return None
    end_date, end_val = parsed[-1]
    target = end_date - timedelta(days=lookback_days)
    anchor: tuple[date, float] | None = None
    for d, v in parsed:
        if d <= target:
            anchor = (d, v)
        else:
            break
    if anchor is None:
        return None
    return anchor[1], end_val


def _trend_by_relative_change(series: list[tuple[str, float]], lookback_days: int, threshold: float) -> str:
    anchor = _anchor_value(series, lookback_days)
    if anchor is None:
        return "unknown"
    first_val, last_val = anchor
    if first_val == 0:
        return "unknown"
    pct = (last_val - first_val) / abs(first_val)
    if pct > threshold:
        return "up"
    if pct < -threshold:
        return "down"
    return "flat"


def _trend_by_absolute_delta(series: list[tuple[str, float]], lookback_days: int, threshold: float) -> str:
    anchor = _anchor_value(series, lookback_days)
    if anchor is None:
        return "unknown"
    first_val, last_val = anchor
    delta = last_val - first_val
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "flat"


def _median_ratio(series: list[tuple[str, float]], lookback_days: int) -> float | None:
    if not series:
        return None
    parsed = [(_parse_series_date(d), v) for d, v in series]
    parsed = [(d, v) for d, v in parsed if d is not None and v > 0]
    if not parsed:
        return None
    end_date = parsed[-1][0]
    assert end_date is not None
    values = [v for d, v in parsed if d is not None and d >= end_date - timedelta(days=lookback_days)]
    if not values:
        return None
    baseline = median(values)
    if baseline <= 0:
        return None
    return round(values[-1] / baseline, 4)


def _rate_trend(series: list[tuple[str, float]], lookback_days: int) -> str:
    return _trend_by_absolute_delta(series, lookback_days, _RATE_BPS_THRESHOLD)


def _latest_distinct_rate_move(series: list[tuple[str, float]]) -> tuple[str, date | None]:
    """
    Infer the actual medium-term policy path from the latest distinct target move.

    Returns the direction of the current policy plateau and the date that plateau
    began. That lets short impulse decay back to "stable" after a long flat
    post-cut or post-hike period.
    """
    points = _sorted_points(series)
    if len(points) < 2:
        return "unknown", None

    latest_value = points[-1][1]
    for idx in range(len(points) - 2, -1, -1):
        prev_date, prev_value = points[idx]
        if abs(latest_value - prev_value) >= _RATE_BPS_THRESHOLD:
            move_date = points[idx + 1][0]
            if latest_value > prev_value:
                return "tightening", move_date
            return "easing", move_date

    return "stable", points[-1][0]


def _rate_impulse_from_move_date(
    *,
    medium_term_direction: str,
    move_date: date | None,
    series: list[tuple[str, float]],
) -> str:
    points = _sorted_points(series)
    if not points or move_date is None:
        return "unknown" if medium_term_direction == "unknown" else "stable"

    latest_date = points[-1][0]
    recency_days = (latest_date - move_date).days

    if medium_term_direction == "easing":
        return "confirming_easing" if recency_days <= _RATE_MOVE_RECENCY_DAYS else "stable"
    if medium_term_direction == "tightening":
        return "confirming_tightening" if recency_days <= _RATE_MOVE_RECENCY_DAYS else "stable"
    if medium_term_direction == "stable":
        return "stable"
    return "unknown"


def _balance_sheet_direction_medium_term(series: list[tuple[str, float]]) -> str:
    trend = _trend_by_absolute_delta(
        series,
        _BALANCE_SHEET_REGIME_LOOKBACK_DAYS,
        _BALANCE_SHEET_DELTA_THRESHOLD,
    )
    if trend == "up":
        return "expanding"
    if trend == "down":
        return "contracting"
    return "flat_or_mixed"


def _value_at_or_before(points: list[tuple[date, float]], target_date: date) -> float | None:
    anchor: float | None = None
    for point_date, point_value in points:
        if point_date <= target_date:
            anchor = point_value
        else:
            break
    return anchor


def _balance_sheet_pace(series: list[tuple[str, float]], medium_term: str) -> str:
    points = _sorted_points(series)
    if len(points) < 3:
        return "flat_or_mixed"

    latest_date, latest_value = points[-1]
    recent_start = _value_at_or_before(
        points,
        latest_date - timedelta(days=_BALANCE_SHEET_PACE_LOOKBACK_DAYS),
    )
    prior_start = _value_at_or_before(
        points,
        latest_date - timedelta(days=_BALANCE_SHEET_PREV_PACE_LOOKBACK_DAYS),
    )

    if recent_start is None or prior_start is None:
        return "flat_or_mixed"

    recent_delta = latest_value - recent_start
    prior_delta = recent_start - prior_start

    if medium_term == "contracting":
        if recent_delta >= prior_delta:
            return "contracting_slower"
        return "contracting_same_or_faster"
    if medium_term == "expanding":
        if recent_delta <= prior_delta:
            return "expanding_slower"
        return "expanding_same_or_faster"
    return "flat_or_mixed"


def _compute_cycle_position(series: list[tuple[str, float]]) -> float | None:
    """
    Return the current rate's normalized position within the trailing series range.

    cycle_position = (current - cycle_low) / (cycle_high - cycle_low)

    Returns None when:
    - fewer than 12 observations are available (insufficient history)
    - the range is effectively flat (< 0.05 percentage points)

    This is a heuristic implementation helper, not speaker doctrine.
    It is used by chessboard.py as a secondary input to _policy_stance().
    """
    if len(series) < 12:
        return None
    values = [v for _, v in series]
    lo, hi = min(values), max(values)
    if hi - lo < 0.05:
        # Rate has been essentially flat throughout the window — not useful
        return None
    return round((values[-1] - lo) / (hi - lo), 3)


# ---------------------------------------------------------------------------
# Market-cap / M2 helper
# ---------------------------------------------------------------------------

def _compute_market_cap_m2(sp500_price: float | None, m2: float | None) -> float | None:
    """
    Fallback only when Z.1 + manual numerator are unavailable.

    Rough proxy: scaled SPY AUM vs M2 (WM2NS, billions USD). Not comparable to Z.1/M2 levels.
    """
    if sp500_price is None or m2 is None or m2 == 0:
        return None
    spy_aum_billions = sp500_price * 0.9
    total_us_equity_billions = spy_aum_billions * 100
    return round(total_us_equity_billions / m2, 3)


def _ratio_from_billions(
    numerator_billions: float | None,
    m2_billions: float | None,
) -> float | None:
    if numerator_billions is None or m2_billions is None or m2_billions == 0:
        return None
    return round(numerator_billions / m2_billions, 3)


_MANUAL_EQUITY_M2_PATH = Path(__file__).resolve().parents[2] / "data" / "manual_equity_m2_numerator.json"


def _parse_manual_equity_m2_file() -> tuple[float | None, str | None]:
    """
    Optional override file: app/data/manual_equity_m2_numerator.json — see .example.json.

    Returns (equity_value_billions, as_of) where as_of is optional metadata for UI.
    """
    override = get_active_override("equity_m2_numerator_billions")
    if override is not None:
        try:
            val = float(override.value)
        except (TypeError, ValueError):
            val = None
        if val is not None and val > 0:
            effective = override.effective_at or override.entered_at
            return val, effective.strftime("%Y-%m-%d")

    if not _MANUAL_EQUITY_M2_PATH.is_file():
        return None, None
    try:
        raw = json.loads(_MANUAL_EQUITY_M2_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("manual equity/M2 numerator JSON unreadable: %s", exc)
        return None, None
    if not isinstance(raw, dict):
        return None, None
    b = raw.get("equity_value_billions")
    if b is None:
        return None, None
    try:
        val = float(b)
    except (TypeError, ValueError):
        return None, None
    if val <= 0:
        return None, None
    ao = raw.get("as_of")
    as_of_str: str | None
    if isinstance(ao, str) and ao.strip():
        as_of_str = ao.strip()
    elif ao is not None:
        as_of_str = str(ao).strip() or None
    else:
        as_of_str = None
    return val, as_of_str


def equity_m2_ratio_core(
    manual_billions: float | None,
    z1_millions: float | None,
    m2_billions: float | None,
    sp500_price: float | None,
) -> tuple[float | None, str | None]:
    views = compute_equity_m2_views(
        manual_billions=manual_billions,
        z1_millions=z1_millions,
        m2_billions=m2_billions,
        sp500_price=sp500_price,
    )
    return views["active_ratio"], views["active_source"]


def compute_equity_m2_views(
    manual_billions: float | None,
    z1_millions: float | None,
    m2_billions: float | None,
    sp500_price: float | None,
) -> dict[str, float | str | None]:
    """
    Separate active, speaker-style, Z.1, and SPY-fallback equity/M2 paths.

    active_ratio follows existing precedence:
    manual override > Z.1 corporate equities > SPY fallback proxy.
    """
    if m2_billions is None or m2_billions == 0:
        return {
            "active_ratio": None,
            "active_source": None,
            "speaker_ratio": None,
            "speaker_source": None,
            "z1_ratio": None,
            "z1_source": None,
            "spy_ratio": None,
            "spy_source": None,
        }

    speaker_ratio = _ratio_from_billions(manual_billions, m2_billions)
    z1_ratio = None
    if z1_millions is not None:
        z1_ratio = _ratio_from_billions(z1_millions / 1000.0, m2_billions)
    spy_ratio = _compute_market_cap_m2(sp500_price, m2_billions)

    if speaker_ratio is not None:
        active_ratio = speaker_ratio
        active_source = "manual_override"
    elif z1_ratio is not None:
        active_ratio = z1_ratio
        active_source = "fred_z1"
    elif spy_ratio is not None:
        active_ratio = spy_ratio
        active_source = "spy_fallback"
    else:
        active_ratio = None
        active_source = None

    return {
        "active_ratio": active_ratio,
        "active_source": active_source,
        "speaker_ratio": speaker_ratio,
        "speaker_source": "manual_override" if speaker_ratio is not None else None,
        "z1_ratio": z1_ratio,
        "z1_source": "fred_z1" if z1_ratio is not None else None,
        "spy_ratio": spy_ratio,
        "spy_source": "spy_fallback" if spy_ratio is not None else None,
    }


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

def build_indicator_snapshot(
    raw: dict[str, FetchResult],
    freshness_statuses: dict[str, str],
    stale_series: list[str],
    overall_status: str,
    fed_put: bool = False,
    treasury_put: bool = False,
    political_put: bool = False,
) -> IndicatorSnapshot:
    """
    Transform a dict of FetchResult values into a complete IndicatorSnapshot.

    `raw` keys correspond to series_map.FRED_SERIES and YAHOO_TICKERS keys.
    Missing keys degrade gracefully to None fields.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_val(key: str) -> float | None:
        r = raw.get(key)
        return r.value if r else None

    def get_series(key: str) -> list[tuple[str, float]]:
        r = raw.get(key)
        return r.series if r else []

    # ------------------------------------------------------------------
    # Liquidity
    # ------------------------------------------------------------------
    rate_series = get_series("fed_funds_rate")
    bs_series = get_series("balance_sheet")

    rate_t1m = _rate_trend(rate_series, 21)
    rate_t3m = _rate_trend(rate_series, 63)
    bs_t1m = _trend_by_absolute_delta(bs_series, 28, _BALANCE_SHEET_DELTA_THRESHOLD)
    bs_t3m = _trend_by_absolute_delta(bs_series, 91, _BALANCE_SHEET_DELTA_THRESHOLD)
    rate_direction_medium_term, rate_move_date = _latest_distinct_rate_move(rate_series)
    rate_impulse_short = _rate_impulse_from_move_date(
        medium_term_direction=rate_direction_medium_term,
        move_date=rate_move_date,
        series=rate_series,
    )
    balance_sheet_direction_medium_term = _balance_sheet_direction_medium_term(bs_series)
    balance_sheet_pace = _balance_sheet_pace(bs_series, balance_sheet_direction_medium_term)

    liquidity = LiquidityInput(
        fed_funds_rate=get_val("fed_funds_rate"),
        # Legacy compatibility fields.
        rate_trend_1m=rate_t1m,
        rate_trend_3m=rate_t3m,
        balance_sheet_assets=get_val("balance_sheet"),
        balance_sheet_trend_1m=bs_t1m,
        balance_sheet_trend_3m=bs_t3m,
        rate_cycle_position=_compute_cycle_position(rate_series),
        # Doctrine-facing fields.
        rate_direction_medium_term=rate_direction_medium_term,
        rate_impulse_short=rate_impulse_short,
        balance_sheet_direction_medium_term=balance_sheet_direction_medium_term,
        balance_sheet_pace=balance_sheet_pace,
        quadrant_basis_note=(
            "Quadrant uses the actual medium-term policy-rate path and actual medium-term "
            "Fed balance-sheet path; transition is handled separately."
        ),
    )
    plumbing = PlumbingInput(
        total_reserves=get_val("total_reserves"),
        reserves_trend_1m=_trend_by_relative_change(
            get_series("total_reserves"),
            _PLUMBING_RESERVE_TREND_LOOKBACK_DAYS,
            0.01,
        ),
        reserves_buffer_ratio=_median_ratio(
            get_series("total_reserves"),
            _PLUMBING_RESERVE_BUFFER_LOOKBACK_DAYS,
        ),
        repo_total=get_val("repo_total"),
        repo_trend_1m=_trend_by_relative_change(
            get_series("repo_total"),
            _PLUMBING_FLOW_TREND_LOOKBACK_DAYS,
            0.10,
        ),
        repo_spike_ratio=_median_ratio(get_series("repo_total"), _PLUMBING_FLOW_BUFFER_LOOKBACK_DAYS),
        reverse_repo_total=get_val("reverse_repo_total"),
        reverse_repo_trend_1m=_trend_by_relative_change(
            get_series("reverse_repo_total"),
            _PLUMBING_FLOW_TREND_LOOKBACK_DAYS,
            0.10,
        ),
        reverse_repo_buffer_ratio=_median_ratio(
            get_series("reverse_repo_total"),
            _PLUMBING_FLOW_BUFFER_LOOKBACK_DAYS,
        ),
        walcl_trend_1m=_trend_by_absolute_delta(bs_series, 28, _BALANCE_SHEET_DELTA_THRESHOLD),
    )

    # ------------------------------------------------------------------
    # Growth
    # ------------------------------------------------------------------
    unemployment_series = get_series("unemployment_rate")
    claims_series = get_series("initial_claims")
    payrolls_series = get_series("nonfarm_payrolls")

    growth = GrowthInput(
        pmi_manufacturing=get_val("pmi_manufacturing"),
        pmi_services=get_val("pmi_services"),
        unemployment_rate=get_val("unemployment_rate"),
        unemployment_trend=_trend_by_absolute_delta(unemployment_series, 35, _UNEMPLOYMENT_DELTA_THRESHOLD),
        initial_claims_trend=_trend_by_relative_change(claims_series, 28, _CLAIMS_PCT_THRESHOLD),
        payrolls_trend=_trend_by_absolute_delta(payrolls_series, 35, _PAYROLLS_DELTA_THRESHOLD),
    )

    # ------------------------------------------------------------------
    # Inflation
    # ------------------------------------------------------------------
    core_result = raw.get("core_cpi")
    shelter_result = raw.get("shelter_cpi")
    services_result = raw.get("services_ex_energy")

    core_yoy, core_mom, _ = compute_yoy_and_status(core_result) if core_result else (None, None, "unknown")
    _, _, shelter_status = compute_yoy_and_status(shelter_result) if shelter_result else (None, None, "unknown")
    _, _, services_status = compute_yoy_and_status(services_result) if services_result else (None, None, "unknown")

    wti_val = get_val("wti_oil")
    oil_risk = (wti_val is not None and wti_val >= 100.0)

    inflation = InflationInput(
        core_cpi_yoy=core_yoy,
        core_cpi_mom=core_mom,
        shelter_status=shelter_status,
        services_ex_energy_status=services_status,
        wti_oil=wti_val,
        oil_risk_active=oil_risk,
    )

    # ------------------------------------------------------------------
    # Valuation — FMP Mag 7 basket (primary) or Yahoo QQQ proxy (fallback).
    # The FetchResult carries all metadata in its extra dict.
    # ------------------------------------------------------------------
    pe_result = raw.get("forward_pe")
    _pe_extra = pe_result.extra if pe_result else {}
    pe_basis = _pe_extra.get("pe_basis", "unavailable")
    pe_source_note = pe_result.note if pe_result else None
    valuation = ValuationInput(
        forward_pe=get_val("forward_pe"),
        current_year_forward_pe=_pe_extra.get("current_year_forward_pe"),
        next_year_forward_pe=_pe_extra.get("next_year_forward_pe"),
        selected_year=_pe_extra.get("selected_year"),
        pe_basis=pe_basis,
        pe_source_note=pe_source_note,
        metric_name=_pe_extra.get("metric_name"),
        object_label=_pe_extra.get("object_label"),
        pe_provider=_pe_extra.get("provider"),
        coverage_count=_pe_extra.get("coverage_count"),
        coverage_ratio=_pe_extra.get("coverage_ratio"),
        signal_mode=_pe_extra.get("signal_mode", "directional_only"),
        basis_confidence=_pe_extra.get("basis_confidence"),
        estimate_as_of=_pe_extra.get("estimate_as_of"),
        horizon_label=_pe_extra.get("horizon_label"),
        horizon_coverage_ratio=_pe_extra.get("horizon_coverage_ratio"),
        constituents=_pe_extra.get("constituents", []),
    )

    # ------------------------------------------------------------------
    # Systemic Stress
    # ------------------------------------------------------------------
    m2_val = get_val("m2")
    sp500_val = get_val("sp500_etf")
    z1_millions = get_val("equity_market_value_z1")
    manual_b, manual_as_of = _parse_manual_equity_m2_file()
    equity_views = compute_equity_m2_views(
        manual_billions=manual_b,
        z1_millions=z1_millions,
        m2_billions=m2_val,
        sp500_price=sp500_val,
    )
    market_cap_m2 = equity_views["active_ratio"]
    equity_m2_src = equity_views["active_source"]
    speaker_market_cap_m2 = equity_views["speaker_ratio"]
    speaker_market_cap_m2_src = equity_views["speaker_source"]
    z1_equities_m2 = equity_views["z1_ratio"]
    z1_equities_m2_src = equity_views["z1_source"]
    spy_fallback_equity_m2 = equity_views["spy_ratio"]

    z1_res = raw.get("equity_market_value_z1")
    sp_res = raw.get("sp500_etf")
    num_as_of: str | None = None
    num_fresh: str | None = None
    if equity_m2_src == "manual_override":
        num_as_of = manual_as_of
        num_fresh = "manual"
    elif equity_m2_src == "fred_z1":
        num_as_of = z1_res.observed_at if z1_res else None
        num_fresh = freshness_statuses.get("equity_market_value_z1")
    elif equity_m2_src == "spy_fallback":
        num_as_of = sp_res.observed_at if sp_res else None
        num_fresh = freshness_statuses.get("sp500_etf")

    stress = SystemicStressInput(
        yield_curve_10y_2y=get_val("yield_curve"),
        npl_ratio=get_val("npl_ratio"),
        cre_delinquency_rate=get_val("cre_delinquency"),
        credit_card_chargeoff_rate=get_val("credit_card_chargeoff"),
        market_cap_m2_ratio=market_cap_m2,
        equity_m2_ratio_source=equity_m2_src,
        speaker_market_cap_m2_ratio=speaker_market_cap_m2,
        speaker_market_cap_m2_source=speaker_market_cap_m2_src,
        corporate_equities_m2_ratio=z1_equities_m2,
        corporate_equities_m2_source=z1_equities_m2_src,
        spy_fallback_equity_m2_ratio=spy_fallback_equity_m2,
        equity_m2_numerator_as_of=num_as_of,
        equity_m2_numerator_freshness=num_fresh,
        corporate_equities_m2_numerator_as_of=(
            z1_res.observed_at if z1_equities_m2 is not None and z1_res is not None else None
        ),
        corporate_equities_m2_numerator_freshness=(
            freshness_statuses.get("equity_market_value_z1") if z1_equities_m2 is not None else None
        ),
    )

    # ------------------------------------------------------------------
    # Dollar context
    # ------------------------------------------------------------------
    dollar = DollarContextInput(dxy=get_val("dxy"))

    # ------------------------------------------------------------------
    # Policy support
    # ------------------------------------------------------------------
    policy = PolicySupportInput(
        fed_put=bool(fed_put),
        treasury_put=bool(treasury_put),
        political_put=bool(political_put),
    )

    # ------------------------------------------------------------------
    # Freshness
    # ------------------------------------------------------------------
    data_freshness = DataFreshnessInput(
        overall_status=overall_status,
        stale_series=stale_series,
    )

    return IndicatorSnapshot(
        as_of=now_iso,
        data_freshness=data_freshness,
        liquidity=liquidity,
        plumbing=plumbing,
        growth=growth,
        inflation=inflation,
        valuation=valuation,
        systemic_stress=stress,
        dollar_context=dollar,
        policy_support=policy,
    )
