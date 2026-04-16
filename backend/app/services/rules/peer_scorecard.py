from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from app.schemas.dashboard_state import PeerScoreMetric, PeerScorecard, ValuationGrowthFit
from app.services.rules.speaker_forward_pe import compute_speaker_forward_pe


@dataclass(frozen=True)
class PeerRaw:
    ticker: str
    sector: str | None
    industry: str | None
    annual_eps_by_year: dict[int, float]
    annual_revenue_by_year: dict[int, float]
    estimate_dates_by_year: dict[int, str]
    price: float | None
    shares: float | None
    revenue_growth_yoy: float | None
    earnings_growth_yoy: float | None
    debt_to_ebitda: float | None


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _favorable_percentile(
    target: float | None,
    peer_values: list[float],
    *,
    lower_is_better: bool,
) -> float | None:
    if target is None:
        return None

    values = [value for value in peer_values if value is not None]
    if len(values) < 3:
        return None

    if lower_is_better:
        better_or_equal = sum(1 for value in values if target <= value)
    else:
        better_or_equal = sum(1 for value in values if target >= value)

    return round((better_or_equal / len(values)) * 100.0, 1)


def _metric(
    target: float | None,
    peers: list[float],
    *,
    lower_is_better: bool,
) -> PeerScoreMetric:
    values = [value for value in peers if value is not None]
    peer_median = round(median(values), 4) if values else None
    favorable_percentile = _favorable_percentile(
        target,
        values,
        lower_is_better=lower_is_better,
    )

    if favorable_percentile is None:
        signal = "unknown"
    elif favorable_percentile >= 65:
        signal = "better_than_peers"
    elif favorable_percentile <= 35:
        signal = "worse_than_peers"
    else:
        signal = "in_line"

    return PeerScoreMetric(
        value=target,
        peer_median=peer_median,
        favorable_percentile=favorable_percentile,
        signal=signal,
    )


def _single_name_forward_pe(raw: PeerRaw, *, as_of: date) -> float | None:
    result = compute_speaker_forward_pe(
        [
            {
                "ticker": raw.ticker,
                "price": raw.price,
                "shares": raw.shares,
                "annual_eps_by_year": raw.annual_eps_by_year,
                "estimate_dates_by_year": raw.estimate_dates_by_year,
                "estimate_as_of": None,
            }
        ],
        as_of=as_of,
    )
    return result.speaker_forward_pe


def _forward_earnings_growth(raw: PeerRaw, *, as_of: date) -> float | None:
    current_year = _coerce_float(raw.annual_eps_by_year.get(as_of.year))
    next_year = _coerce_float(raw.annual_eps_by_year.get(as_of.year + 1))
    if current_year is None or next_year is None or current_year <= 0:
        return None
    return (next_year / current_year) - 1.0


def _forward_revenue_growth(raw: PeerRaw, *, as_of: date) -> float | None:
    current_year = _coerce_float(raw.annual_revenue_by_year.get(as_of.year))
    next_year = _coerce_float(raw.annual_revenue_by_year.get(as_of.year + 1))
    if current_year is None or next_year is None or current_year <= 0:
        return None
    return (next_year / current_year) - 1.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float] | None:
    if len(xs) < 5 or len(xs) != len(ys):
        return None

    x_bar = _mean(xs)
    y_bar = _mean(ys)
    ss_xx = sum((x - x_bar) ** 2 for x in xs)
    if ss_xx <= 0:
        return None

    ss_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    slope = ss_xy / ss_xx
    intercept = y_bar - slope * x_bar

    ss_tot = sum((y - y_bar) ** 2 for y in ys)
    if ss_tot <= 0:
        return slope, intercept, 0.0

    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r_squared = max(0.0, 1.0 - (ss_res / ss_tot))
    return slope, intercept, r_squared


def _valuation_vs_growth_fit(
    *,
    target: PeerRaw,
    peer_group: list[PeerRaw],
    as_of: date,
    target_forward_pe: float | None,
) -> ValuationGrowthFit:
    peer_eps_points: list[tuple[float, float]] = []
    for peer in peer_group:
        growth = _forward_earnings_growth(peer, as_of=as_of)
        forward_pe = _single_name_forward_pe(peer, as_of=as_of)
        if growth is not None and forward_pe is not None:
            peer_eps_points.append((growth, forward_pe))

    fit_growth_metric = "forward_earnings_growth"
    target_growth = _forward_earnings_growth(target, as_of=as_of)
    peer_points = peer_eps_points

    if len(peer_points) < 5 or target_growth is None:
        peer_revenue_points: list[tuple[float, float]] = []
        for peer in peer_group:
            growth = _forward_revenue_growth(peer, as_of=as_of)
            forward_pe = _single_name_forward_pe(peer, as_of=as_of)
            if growth is not None and forward_pe is not None:
                peer_revenue_points.append((growth, forward_pe))
        fit_growth_metric = "forward_revenue_growth"
        target_growth = _forward_revenue_growth(target, as_of=as_of)
        peer_points = peer_revenue_points

    if len(peer_points) < 5 or target_growth is None or target_forward_pe is None:
        return ValuationGrowthFit(
            fit_growth_metric=fit_growth_metric,
            peer_count=len(peer_points),
            fit_signal="insufficient",
            weighting_active=False,
            note="Not enough peer coverage to evaluate valuation versus forward growth.",
        )

    xs = [x for x, _ in peer_points]
    ys = [y for _, y in peer_points]
    fit = _linear_fit(xs, ys)
    if fit is None:
        return ValuationGrowthFit(
            fit_growth_metric=fit_growth_metric,
            peer_count=len(peer_points),
            fit_signal="insufficient",
            weighting_active=False,
            note="Peer forward-growth relationship is too weak to fit deterministically.",
        )

    slope, intercept, r_squared = fit
    expected_forward_pe = intercept + slope * target_growth
    if expected_forward_pe <= 0:
        return ValuationGrowthFit(
            fit_growth_metric=fit_growth_metric,
            peer_count=len(peer_points),
            r_squared=round(r_squared, 4),
            fit_signal="insufficient",
            weighting_active=False,
            note="Regression produced a non-usable expected forward P/E.",
        )

    residual_pct = (target_forward_pe - expected_forward_pe) / expected_forward_pe
    weighting_active = r_squared >= 0.8

    if residual_pct <= -0.15:
        fit_signal = "undervalued_vs_growth"
    elif residual_pct >= 0.15:
        fit_signal = "overvalued_vs_growth"
    else:
        fit_signal = "fairly_priced_vs_growth"

    note = (
        "Valuation-vs-growth fit is high confidence."
        if weighting_active
        else "Valuation-vs-growth fit is low confidence; use only as a weak check."
    )

    return ValuationGrowthFit(
        fit_growth_metric=fit_growth_metric,
        peer_count=len(peer_points),
        r_squared=round(r_squared, 4),
        expected_forward_pe=round(expected_forward_pe, 2),
        residual_pct=round(residual_pct, 4),
        fit_signal=fit_signal,
        weighting_active=weighting_active,
        note=note,
    )


def _apply_fit_weighting(*, verdict: str, fit: ValuationGrowthFit) -> str:
    if verdict == "insufficient" or not fit.weighting_active:
        return verdict

    if fit.fit_signal == "undervalued_vs_growth" and verdict == "balanced":
        return "leader"

    if fit.fit_signal == "overvalued_vs_growth":
        if verdict == "leader":
            return "balanced"
        if verdict == "balanced":
            return "fragile"

    return verdict


def build_peer_scorecard(
    *,
    target: PeerRaw,
    peers: list[PeerRaw],
    as_of: date,
) -> PeerScorecard:
    same_industry = [
        peer
        for peer in peers
        if target.industry and peer.ticker != target.ticker and peer.industry == target.industry
    ]
    same_sector = [
        peer
        for peer in peers
        if target.sector and peer.ticker != target.ticker and peer.sector == target.sector
    ]

    if len(same_industry) >= 3:
        peer_group = same_industry
        scope_label = "same-industry"
    elif target.sector:
        peer_group = same_sector
        scope_label = "same-sector"
    else:
        peer_group = []
        scope_label = "unscoped"

    peer_tickers = [peer.ticker for peer in peer_group]

    target_forward_pe = _single_name_forward_pe(target, as_of=as_of)
    peer_forward_pes = [
        value
        for value in (_single_name_forward_pe(peer, as_of=as_of) for peer in peer_group)
        if value is not None
    ]

    revenue_metric = _metric(
        target.revenue_growth_yoy,
        [peer.revenue_growth_yoy for peer in peer_group if peer.revenue_growth_yoy is not None],
        lower_is_better=False,
    )
    earnings_metric = _metric(
        target.earnings_growth_yoy,
        [peer.earnings_growth_yoy for peer in peer_group if peer.earnings_growth_yoy is not None],
        lower_is_better=False,
    )
    forward_pe_metric = _metric(
        target_forward_pe,
        peer_forward_pes,
        lower_is_better=True,
    )
    leverage_metric = _metric(
        target.debt_to_ebitda,
        [peer.debt_to_ebitda for peer in peer_group if peer.debt_to_ebitda is not None],
        lower_is_better=True,
    )
    fit_metric = _valuation_vs_growth_fit(
        target=target,
        peer_group=peer_group,
        as_of=as_of,
        target_forward_pe=target_forward_pe,
    )

    known_metrics = [
        metric
        for metric in (revenue_metric, earnings_metric, forward_pe_metric, leverage_metric)
        if metric.signal != "unknown"
    ]

    revenue_pct = revenue_metric.favorable_percentile
    earnings_pct = earnings_metric.favorable_percentile
    pe_pct = forward_pe_metric.favorable_percentile
    leverage_pct = leverage_metric.favorable_percentile

    growth_strong = (
        revenue_pct is not None
        and earnings_pct is not None
        and revenue_pct >= 65
        and earnings_pct >= 65
    )
    valuation_ok = pe_pct is None or pe_pct >= 35
    leverage_ok = leverage_pct is None or leverage_pct >= 35
    growth_weak = (
        (revenue_pct is not None and revenue_pct <= 35)
        or (earnings_pct is not None and earnings_pct <= 35)
    )
    valuation_stretched = pe_pct is not None and pe_pct <= 20
    leverage_stretched = leverage_pct is not None and leverage_pct <= 20

    if len(peer_group) < 3 or len(known_metrics) < 3:
        verdict = "insufficient"
        note = (
            f"{scope_label.capitalize()} peer sample or metric coverage is too thin for a deterministic stock-selection verdict."
        )
    elif growth_strong and valuation_ok and leverage_ok:
        verdict = "leader"
        note = f"Growth and valuation/leverage compare favorably against {scope_label} peers."
    elif growth_weak or valuation_stretched or leverage_stretched:
        verdict = "fragile"
        note = f"Relative growth or valuation/leverage profile is weak versus {scope_label} peers."
    else:
        verdict = "balanced"
        note = f"Profile is mixed but acceptable versus {scope_label} peers."

    weighted_verdict = _apply_fit_weighting(verdict=verdict, fit=fit_metric)
    if weighted_verdict != verdict:
        if fit_metric.fit_signal == "undervalued_vs_growth":
            note = f"{note} High-confidence valuation-vs-growth fit improves the verdict."
        elif fit_metric.fit_signal == "overvalued_vs_growth":
            note = f"{note} High-confidence valuation-vs-growth fit weakens the verdict."
        verdict = weighted_verdict

    return PeerScorecard(
        ticker=target.ticker,
        sector=target.sector,
        industry=target.industry,
        peer_tickers=peer_tickers,
        revenue_growth=revenue_metric,
        earnings_growth=earnings_metric,
        forward_pe=forward_pe_metric,
        debt_to_ebitda=leverage_metric,
        valuation_vs_growth_fit=fit_metric,
        verdict=verdict,
        same_sector_peer_compare_required=True,
        note=note,
    )
