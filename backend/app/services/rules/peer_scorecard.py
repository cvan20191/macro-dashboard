from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

from app.schemas.dashboard_state import PeerScoreMetric, PeerScorecard
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


def build_peer_scorecard(
    *,
    target: PeerRaw,
    peers: list[PeerRaw],
    as_of: date,
) -> PeerScorecard:
    if target.industry:
        peer_group = [
            peer
            for peer in peers
            if peer.ticker != target.ticker and peer.industry == target.industry
        ]
        scope_label = "same-industry"
    elif target.sector:
        peer_group = [
            peer
            for peer in peers
            if peer.ticker != target.ticker and peer.sector == target.sector
        ]
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

    return PeerScorecard(
        ticker=target.ticker,
        sector=target.sector,
        industry=target.industry,
        peer_tickers=peer_tickers,
        revenue_growth=revenue_metric,
        earnings_growth=earnings_metric,
        forward_pe=forward_pe_metric,
        debt_to_ebitda=leverage_metric,
        verdict=verdict,
        same_sector_peer_compare_required=True,
        note=note,
    )
