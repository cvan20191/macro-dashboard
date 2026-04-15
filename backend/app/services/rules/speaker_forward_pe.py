from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from typing import Any

from app.doctrine import SignalMode

_NEAR_YEAR_END_DAYS = 120
_MIN_ACTIONABLE_COVERAGE_RATIO = 0.90
_MIN_ACTIONABLE_CONSTITUENTS = 5


@dataclass(frozen=True)
class BasketConstituent:
    ticker: str
    price: float | None
    shares: float | None
    market_cap: float | None = None
    annual_eps_by_year: dict[int, float] = field(default_factory=dict)
    estimate_dates_by_year: dict[int, str] = field(default_factory=dict)
    estimate_as_of: str | None = None


@dataclass(frozen=True)
class SpeakerForwardPEResult:
    valid: bool
    note: str
    current_year_forward_pe: float | None
    next_year_forward_pe: float | None
    speaker_forward_pe: float | None
    selected_year: int | None
    horizon_label: str
    coverage_count: int
    coverage_ratio: float
    signal_mode: SignalMode
    basis_confidence: float | None
    horizon_coverage_ratio: float | None
    constituents: list[dict[str, Any]] = field(default_factory=list)


def _positive_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(out) or out <= 0:
        return None
    return out


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _normalize_constituents(
    payloads: list[dict[str, Any] | BasketConstituent],
) -> list[BasketConstituent]:
    normalized: list[BasketConstituent] = []
    for payload in payloads:
        if isinstance(payload, BasketConstituent):
            normalized.append(payload)
            continue

        annual_eps = payload.get("annual_eps_by_year") or {}
        annual_dates = payload.get("estimate_dates_by_year") or {}

        normalized.append(
            BasketConstituent(
                ticker=str(payload.get("ticker") or ""),
                price=_positive_float(payload.get("price")),
                shares=_positive_float(payload.get("shares")),
                market_cap=_positive_float(payload.get("market_cap")),
                annual_eps_by_year={
                    int(year): float(eps)
                    for year, eps in annual_eps.items()
                    if _positive_float(eps) is not None
                },
                estimate_dates_by_year={
                    int(year): str(raw_date)
                    for year, raw_date in annual_dates.items()
                    if raw_date
                },
                estimate_as_of=payload.get("estimate_as_of"),
            )
        )
    return normalized


def _constituent_market_cap(c: BasketConstituent) -> float | None:
    if c.market_cap is not None and c.market_cap > 0:
        return float(c.market_cap)
    if c.price is not None and c.shares is not None and c.price > 0 and c.shares > 0:
        return float(c.price * c.shares)
    return None


def _weighted_median_days_to_fye(
    constituents: list[BasketConstituent],
    *,
    current_year: int,
    as_of: date,
) -> int | None:
    weighted_points: list[tuple[int, float]] = []

    for constituent in constituents:
        market_cap = _constituent_market_cap(constituent)
        fiscal_year_end = _parse_date(constituent.estimate_dates_by_year.get(current_year))
        if market_cap is None or fiscal_year_end is None:
            continue

        days = (fiscal_year_end - as_of).days
        if days < 0:
            continue

        weighted_points.append((days, market_cap))

    if not weighted_points:
        return None

    weighted_points.sort(key=lambda point: point[0])
    total_weight = sum(weight for _, weight in weighted_points)
    half_weight = total_weight / 2.0

    running_weight = 0.0
    for days, weight in weighted_points:
        running_weight += weight
        if running_weight >= half_weight:
            return days

    return weighted_points[-1][0]


def _basket_forward_pe(
    constituents: list[BasketConstituent],
    target_year: int,
) -> tuple[float | None, list[str], float, float]:
    total_market_cap = 0.0
    included_market_cap = 0.0
    total_forward_earnings = 0.0
    included: list[str] = []

    for c in constituents:
        market_cap = _constituent_market_cap(c)
        if market_cap is None:
            continue

        total_market_cap += market_cap
        eps = c.annual_eps_by_year.get(target_year)
        if eps is None or eps <= 0 or c.shares is None:
            continue

        included_market_cap += market_cap
        total_forward_earnings += eps * c.shares
        included.append(c.ticker)

    if total_forward_earnings <= 0 or included_market_cap <= 0:
        return None, [], included_market_cap, total_market_cap

    return included_market_cap / total_forward_earnings, included, included_market_cap, total_market_cap


def compute_speaker_forward_pe(
    payloads: list[dict[str, Any] | BasketConstituent],
    *,
    as_of: date,
) -> SpeakerForwardPEResult:
    constituents = _normalize_constituents(payloads)

    current_year = as_of.year
    next_year = as_of.year + 1

    current_pe, current_included, current_mc, total_mc = _basket_forward_pe(constituents, current_year)
    next_pe, next_included, next_mc, total_mc_next = _basket_forward_pe(constituents, next_year)
    total_market_cap = total_mc if total_mc > 0 else total_mc_next
    usable_constituent_count = sum(1 for c in constituents if _constituent_market_cap(c) is not None)
    weighted_days_to_fye = _weighted_median_days_to_fye(
        constituents,
        current_year=current_year,
        as_of=as_of,
    )

    if current_pe is None and next_pe is not None:
        selected_year = next_year
    elif next_pe is None:
        selected_year = current_year
    elif weighted_days_to_fye is not None and weighted_days_to_fye <= _NEAR_YEAR_END_DAYS:
        selected_year = next_year
    else:
        selected_year = current_year

    if selected_year == next_year and next_pe is not None:
        speaker_pe = next_pe
        selected_included = next_included
        selected_mc = next_mc
        horizon_label = "speaker_fye_proximity_next_year"
    else:
        speaker_pe = current_pe
        selected_included = current_included
        selected_mc = current_mc
        horizon_label = "speaker_fye_proximity_current_year"

    coverage_count = len(selected_included)
    coverage_ratio = round(selected_mc / total_market_cap, 4) if total_market_cap > 0 else 0.0
    horizon_coverage_ratio = coverage_ratio

    selected_year_actionable = (
        speaker_pe is not None
        and usable_constituent_count >= _MIN_ACTIONABLE_CONSTITUENTS
        and coverage_count >= _MIN_ACTIONABLE_CONSTITUENTS
        and coverage_ratio >= _MIN_ACTIONABLE_COVERAGE_RATIO
    )

    signal_mode: SignalMode = "actionable" if selected_year_actionable else "directional_only"
    basis_confidence = round(coverage_ratio, 2) if speaker_pe is not None else 0.0
    valid = speaker_pe is not None and coverage_count > 0

    if not valid:
        note = "Mag 7 speaker forward P/E unavailable — no usable selected-year forward-earnings basket."
    elif signal_mode == "directional_only":
        note = (
            "Mag 7 speaker forward P/E available, but selected-year basket completeness is not strong enough "
            "for hard-action use."
        )
    else:
        note = "Mag 7 speaker forward P/E actionable on market-cap-complete selected-year basket."

    constituents_out: list[dict[str, Any]] = []
    for c in constituents:
        selected_eps = c.annual_eps_by_year.get(selected_year)
        forward_pe = None
        if c.price is not None and selected_eps is not None and selected_eps > 0:
            forward_pe = round(c.price / selected_eps, 2)

        constituents_out.append(
            {
                "ticker": c.ticker,
                "price": c.price,
                "forward_eps": selected_eps,
                "forward_pe": forward_pe,
                "fy1_eps": c.annual_eps_by_year.get(current_year),
                "fy2_eps": c.annual_eps_by_year.get(next_year),
                "shares": c.shares,
                "fiscal_year_end": c.estimate_dates_by_year.get(selected_year),
                "estimate_as_of": c.estimate_as_of,
                "basis_confidence": 1.0 if selected_eps is not None else 0.0,
            }
        )

    return SpeakerForwardPEResult(
        valid=valid,
        note=note,
        current_year_forward_pe=current_pe,
        next_year_forward_pe=next_pe,
        speaker_forward_pe=speaker_pe,
        selected_year=selected_year if valid else None,
        horizon_label=horizon_label,
        coverage_count=coverage_count,
        coverage_ratio=coverage_ratio,
        signal_mode=signal_mode,
        basis_confidence=basis_confidence,
        horizon_coverage_ratio=horizon_coverage_ratio,
        constituents=constituents_out,
    )
