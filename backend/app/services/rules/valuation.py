"""
Valuation Trigger — Module 3.

Classifies big-tech forward P/E into the speaker's action zones.

Basis hierarchy (set by the provider layer):
  forward     — true forward P/E (FMP Mag 7 basket; authoritative)
  trailing    — trailing P/E (Yahoo QQQ fallback; directional proxy)
  ttm_derived — price ÷ TTM EPS (Yahoo last-resort; weakest proxy)
  unavailable — no P/E data

Zone classification uses the same speaker thresholds regardless of basis.
The basis, metric_name, object_label, provider, and coverage fields are
surfaced in the Valuation model so the UI can be honest and soften action
language when the source is not true forward P/E.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.doctrine import DEFAULT_DOCTRINE_PROFILE, can_drive_hard_action
from app.schemas.dashboard_state import Valuation, ValuationConstituent
from app.schemas.indicator_snapshot import ValuationInput

# Speaker-defined heuristic thresholds
BUY_ZONE_LOW = DEFAULT_DOCTRINE_PROFILE.bigtech_pe_buy_low.value
BUY_ZONE_HIGH = DEFAULT_DOCTRINE_PROFILE.bigtech_pe_buy_high.value
NEUTRAL_LOW = 26.0
NEUTRAL_HIGH = 29.0
PAUSE_THRESHOLD = DEFAULT_DOCTRINE_PROFILE.bigtech_pe_pause.value

# Human-readable basis labels
_BASIS_LABELS: dict[str, str] = {
    "forward":     "Forward P/E",
    "trailing":    "Trailing P/E (Proxy)",
    "ttm_derived": "Derived P/E (Proxy)",
    "unavailable": "Unavailable",
}

_PROXY_ZONE_LABELS: dict[str, str] = {
    "Green": "Proxy support only",
    "Yellow": "Proxy neutral",
    "Red": "Proxy stretched",
    "BelowBuyZone": "Proxy below buy zone",
    "Neutral": "Proxy transitional",
}


@dataclass
class ValuationResult:
    valuation: Valuation
    zone: str         # "Green" | "Yellow" | "Red" | "BelowBuyZone" | "Neutral"
    is_stretched: bool
    is_buy_zone: bool
    can_pause_new_buying: bool
    can_support_buy_zone: bool


def compute_valuation(val_input: ValuationInput) -> ValuationResult:
    pe = val_input.forward_pe
    current_year_pe = val_input.current_year_forward_pe
    next_year_pe = val_input.next_year_forward_pe
    selected_year = val_input.selected_year
    basis = val_input.pe_basis or "unavailable"
    source_note = val_input.pe_source_note
    basis_label = _BASIS_LABELS.get(basis, basis)
    is_fallback = pe is not None and basis != "forward"

    # Shared identity / coverage fields — pass through unchanged
    metric_name = val_input.metric_name
    object_label = val_input.object_label
    provider = val_input.pe_provider
    coverage_count = val_input.coverage_count
    coverage_ratio = val_input.coverage_ratio
    signal_mode = val_input.signal_mode
    basis_confidence = val_input.basis_confidence
    estimate_as_of = val_input.estimate_as_of
    horizon_label = val_input.horizon_label
    horizon_coverage_ratio = val_input.horizon_coverage_ratio
    constituents = [
        ValuationConstituent(**c) if isinstance(c, dict) else c
        for c in (val_input.constituents or [])
    ]

    if pe is None:
        return ValuationResult(
            valuation=Valuation(
                forward_pe=None,
                current_year_forward_pe=current_year_pe,
                next_year_forward_pe=next_year_pe,
                selected_year=selected_year,
                zone="Neutral",
                zone_label="Data unavailable",
                buy_zone_low=BUY_ZONE_LOW,
                buy_zone_high=BUY_ZONE_HIGH,
                pause_threshold=PAUSE_THRESHOLD,
                basis="unavailable",
                basis_label="Unavailable",
                source_note=source_note,
                is_fallback=False,
                metric_name=metric_name,
                object_label=object_label,
                provider=provider,
                coverage_count=coverage_count,
                coverage_ratio=coverage_ratio,
                signal_mode="directional_only",
                basis_confidence=basis_confidence,
                estimate_as_of=estimate_as_of,
                horizon_label=horizon_label,
                horizon_coverage_ratio=horizon_coverage_ratio,
                constituents=constituents,
            ),
            zone="Neutral",
            is_stretched=False,
            is_buy_zone=False,
            can_pause_new_buying=False,
            can_support_buy_zone=False,
        )

    # --- zone classification (same thresholds regardless of basis) ---
    if BUY_ZONE_LOW <= pe <= BUY_ZONE_HIGH:
        zone = "Green"
        label = "Safe Margin"
    elif NEUTRAL_LOW <= pe <= NEUTRAL_HIGH:
        zone = "Yellow"
        label = "Neutral"
    elif pe >= PAUSE_THRESHOLD:
        zone = "Red"
        label = "Valuation Stretched"
    elif pe < BUY_ZONE_LOW:
        zone = "BelowBuyZone"
        label = "Below Buy Zone"
    else:
        zone = "Neutral"
        label = "Transitional"

    if is_fallback:
        label = _PROXY_ZONE_LABELS.get(zone, "Proxy signal only")

    valuation = Valuation(
        forward_pe=pe,
        current_year_forward_pe=current_year_pe,
        next_year_forward_pe=next_year_pe,
        selected_year=selected_year,
        zone=zone,
        zone_label=label,
        buy_zone_low=BUY_ZONE_LOW,
        buy_zone_high=BUY_ZONE_HIGH,
        pause_threshold=PAUSE_THRESHOLD,
        basis=basis,
        basis_label=basis_label,
        source_note=source_note,
        is_fallback=is_fallback,
        metric_name=metric_name,
        object_label=object_label,
        provider=provider,
        coverage_count=coverage_count,
        coverage_ratio=coverage_ratio,
        signal_mode=signal_mode,
        basis_confidence=basis_confidence,
        estimate_as_of=estimate_as_of,
        horizon_label=horizon_label,
        horizon_coverage_ratio=horizon_coverage_ratio,
        constituents=constituents,
    )
    hard_action_enabled = can_drive_hard_action(signal_mode)

    return ValuationResult(
        valuation=valuation,
        zone=zone,
        is_stretched=(zone == "Red"),
        is_buy_zone=(zone == "Green"),
        can_pause_new_buying=hard_action_enabled and zone == "Red",
        can_support_buy_zone=hard_action_enabled and zone == "Green",
    )
