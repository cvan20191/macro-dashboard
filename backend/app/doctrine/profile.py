"""
Doctrine profile and shared semantic types.

This module is the single owner for doctrine thresholds and confidence helpers.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ThresholdKind = Literal["heuristic", "warning", "hard_gate"]
TriState = Literal["true", "false", "unknown"]
SignalMode = Literal["actionable", "directional_only"]
SourceClass = Literal["official", "licensed", "manual", "proxy"]


class Threshold(BaseModel):
    value: float
    kind: ThresholdKind
    scope: str
    note: str | None = None


class DoctrineProfile(BaseModel):
    name: str = "defiant_gatekeeper_v1"

    bigtech_pe_buy_low: Threshold
    bigtech_pe_buy_high: Threshold
    bigtech_pe_pause: Threshold
    speaker_forward_pe_switch_month: Threshold
    core_cpi_sticky: Threshold
    pmi_contraction: Threshold
    unemployment_trap_low: Threshold
    unemployment_trap_high: Threshold
    broad_npl_caution: Threshold
    broad_npl_warning: Threshold
    corporate_equities_m2_warning: Threshold
    corporate_equities_m2_extreme: Threshold


DEFAULT_DOCTRINE_PROFILE = DoctrineProfile(
    bigtech_pe_buy_low=Threshold(
        value=20.0,
        kind="heuristic",
        scope="bigtech_forward_pe",
        note="Speaker heuristic zone, not a universal all-sector rule.",
    ),
    bigtech_pe_buy_high=Threshold(
        value=25.0,
        kind="heuristic",
        scope="bigtech_forward_pe",
        note="Upper edge of the historical accumulation band.",
    ),
    bigtech_pe_pause=Threshold(
        value=30.0,
        kind="heuristic",
        scope="bigtech_forward_pe",
        note="Stretch threshold for new accumulation, not an automatic sell signal.",
    ),
    speaker_forward_pe_switch_month=Threshold(
        value=10.0,
        kind="heuristic",
        scope="speaker_forward_pe_horizon",
        note="Default doctrine switch into next-year focus near Q4; implementation helper, not a timeless market law.",
    ),
    core_cpi_sticky=Threshold(
        value=3.0,
        kind="warning",
        scope="core_cpi_yoy",
    ),
    pmi_contraction=Threshold(
        value=50.0,
        kind="warning",
        scope="pmi_manufacturing",
    ),
    unemployment_trap_low=Threshold(
        value=4.0,
        kind="heuristic",
        scope="unemployment_rate",
    ),
    unemployment_trap_high=Threshold(
        value=4.3,
        kind="heuristic",
        scope="unemployment_rate",
    ),
    broad_npl_caution=Threshold(
        value=1.0,
        kind="warning",
        scope="broad_bank_delinquency",
        note="Doctrine heuristic carried from the notes, not a structural banking law.",
    ),
    broad_npl_warning=Threshold(
        value=1.5,
        kind="warning",
        scope="broad_bank_delinquency",
    ),
    corporate_equities_m2_warning=Threshold(
        value=5.8,
        kind="heuristic",
        scope="corporate_equities_m2_proxy",
        note="Proxy froth gauge only. Not the speaker's market-cap/M2 signal.",
    ),
    corporate_equities_m2_extreme=Threshold(
        value=6.8,
        kind="heuristic",
        scope="corporate_equities_m2_proxy",
    ),
)


def can_drive_hard_action(signal_mode: SignalMode) -> bool:
    return signal_mode == "actionable"


def default_confidence_weight(source_class: SourceClass) -> float:
    if source_class == "official":
        return 1.0
    if source_class == "licensed":
        return 0.9
    if source_class == "manual":
        return 0.75
    return 0.4
