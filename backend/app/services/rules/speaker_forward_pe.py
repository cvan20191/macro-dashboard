from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.doctrine import DEFAULT_DOCTRINE_PROFILE, SignalMode

MIN_CONSTITUENTS = 5
MIN_COVERAGE_RATIO = 0.80
DEFAULT_SWITCH_MONTH = int(DEFAULT_DOCTRINE_PROFILE.speaker_forward_pe_switch_month.value)


@dataclass
class BasketConstituent:
    ticker: str
    price: float | None
    shares: float | None
    market_cap: float | None
    annual_eps_by_year: dict[int, float]
    estimate_as_of: str | None = None


@dataclass
class SpeakerForwardPEResult:
    current_year_forward_pe: float | None
    next_year_forward_pe: float | None
    speaker_forward_pe: float | None
    selected_year: int | None
    horizon_label: str | None
    coverage_count: int
    coverage_ratio: float
    signal_mode: SignalMode
    basis_confidence: float | None
    horizon_coverage_ratio: float | None
    constituents: list[dict]
    note: str
    valid: bool


def _normalize_constituents(payloads: list[dict | BasketConstituent]) -> list[BasketConstituent]:
    normalized: list[BasketConstituent] = []
    for payload in payloads:
        if isinstance(payload, BasketConstituent):
            normalized.append(payload)
        else:
            normalized.append(BasketConstituent(**payload))
    return normalized


def _constituent_market_cap(c: BasketConstituent) -> float | None:
    if c.market_cap is not None and c.market_cap > 0:
        return float(c.market_cap)
    if c.price is not None and c.shares is not None and c.price > 0 and c.shares > 0:
        return float(c.price * c.shares)
    return None


def _basket_forward_pe(
    constituents: list[BasketConstituent],
    target_year: int,
) -> tuple[float | None, int, float, set[str]]:
    total_market_cap = 0.0
    valid_market_cap = 0.0
    total_forward_earnings = 0.0
    coverage_count = 0
    included: set[str] = set()

    for c in constituents:
        market_cap = _constituent_market_cap(c)
        if market_cap is not None:
            total_market_cap += market_cap
        eps = c.annual_eps_by_year.get(target_year)
        if market_cap is None or c.shares is None or c.shares <= 0 or eps is None or eps <= 0:
            continue
        valid_market_cap += market_cap
        total_forward_earnings += eps * c.shares
        coverage_count += 1
        included.add(c.ticker)

    if total_market_cap <= 0 or total_forward_earnings <= 0:
        return None, coverage_count, 0.0, included
    return valid_market_cap / total_forward_earnings, coverage_count, valid_market_cap / total_market_cap, included


def compute_speaker_forward_pe(
    payloads: list[dict | BasketConstituent],
    *,
    as_of: date,
    switch_month: int = DEFAULT_SWITCH_MONTH,
) -> SpeakerForwardPEResult:
    constituents = _normalize_constituents(payloads)
    current_year = as_of.year
    next_year = as_of.year + 1
    desired_year = next_year if as_of.month >= switch_month else current_year

    current_pe, current_count, current_coverage, current_included = _basket_forward_pe(
        constituents, current_year
    )
    next_pe, next_count, next_coverage, next_included = _basket_forward_pe(
        constituents, next_year
    )

    if desired_year == next_year and next_pe is not None:
        selected_year = next_year
        speaker_pe = next_pe
        selected_count = next_count
        selected_coverage = next_coverage
        included = next_included
        horizon_label = "speaker_calendar_next_year"
        basis_confidence = 1.0
    elif current_pe is not None:
        selected_year = current_year
        speaker_pe = current_pe
        selected_count = current_count
        selected_coverage = current_coverage
        included = current_included
        horizon_label = (
            "speaker_calendar_current_year_fallback"
            if desired_year == next_year
            else "speaker_calendar_current_year"
        )
        basis_confidence = 0.85 if desired_year == next_year else 0.95
    elif next_pe is not None:
        selected_year = next_year
        speaker_pe = next_pe
        selected_count = next_count
        selected_coverage = next_coverage
        included = next_included
        horizon_label = "speaker_calendar_next_year_fallback"
        basis_confidence = 0.85
    else:
        selected_year = None
        speaker_pe = None
        selected_count = 0
        selected_coverage = 0.0
        included = set()
        horizon_label = None
        basis_confidence = None

    valid = (
        speaker_pe is not None
        and selected_count >= MIN_CONSTITUENTS
        and selected_coverage >= MIN_COVERAGE_RATIO
    )
    signal_mode: SignalMode = (
        "actionable" if valid and basis_confidence is not None and basis_confidence >= 0.85 else "directional_only"
    )

    constituents_payload: list[dict] = []
    for c in constituents:
        market_cap = _constituent_market_cap(c)
        current_eps = c.annual_eps_by_year.get(current_year)
        next_eps = c.annual_eps_by_year.get(next_year)
        selected_eps = c.annual_eps_by_year.get(selected_year) if selected_year is not None else None
        selected_pe = (
            round(c.price / selected_eps, 2)
            if c.price is not None and selected_eps is not None and selected_eps > 0
            else None
        )
        constituents_payload.append(
            {
                "ticker": c.ticker,
                "price": c.price,
                "forward_eps": None if selected_eps is None else round(selected_eps, 4),
                "forward_pe": selected_pe,
                "fy1_eps": None if current_eps is None else round(current_eps, 4),
                "fy2_eps": None if next_eps is None else round(next_eps, 4),
                "shares": None if c.shares is None else round(c.shares, 2),
                "fiscal_year_end": None if selected_year is None else f"{selected_year}-12-31",
                "estimate_as_of": c.estimate_as_of,
                "basis_confidence": round(basis_confidence, 2) if basis_confidence is not None and c.ticker in included else None,
                "market_cap": None if market_cap is None else round(market_cap, 2),
            }
        )

    note = (
        f"Mag 7 market-cap-weighted forward P/E — {selected_count}/{len(constituents)} constituents, "
        f"{selected_coverage:.0%} market-cap coverage "
        f"(speaker-style annual horizon selection, selected {selected_year or 'unavailable'})"
    )
    if not valid:
        note += ". Coverage is insufficient for actionable forward valuation."

    return SpeakerForwardPEResult(
        current_year_forward_pe=None if current_pe is None else round(current_pe, 4),
        next_year_forward_pe=None if next_pe is None else round(next_pe, 4),
        speaker_forward_pe=None if speaker_pe is None else round(speaker_pe, 4),
        selected_year=selected_year,
        horizon_label=horizon_label,
        coverage_count=selected_count,
        coverage_ratio=round(selected_coverage, 4),
        signal_mode=signal_mode,
        basis_confidence=None if basis_confidence is None else round(basis_confidence, 4),
        horizon_coverage_ratio=round(next_coverage, 4),
        constituents=constituents_payload,
        note=note,
        valid=valid,
    )
