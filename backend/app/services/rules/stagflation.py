"""
Stagflation Trap Monitor — Module 2.

Determines growth_weakening, sticky_inflation, and the full trap trigger.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.doctrine import DEFAULT_DOCTRINE_PROFILE, TriState
from app.schemas.dashboard_state import StagflationTrap
from app.schemas.indicator_snapshot import GrowthInput, InflationInput

_OIL_RISK_THRESHOLD = 100.0
_CPI_STICKY_THRESHOLD = DEFAULT_DOCTRINE_PROFILE.core_cpi_sticky.value
_PMI_CONTRACTION = DEFAULT_DOCTRINE_PROFILE.pmi_contraction.value
_UNEMP_TRAP_LOW = DEFAULT_DOCTRINE_PROFILE.unemployment_trap_low.value
_UNEMP_TRAP_HIGH = DEFAULT_DOCTRINE_PROFILE.unemployment_trap_high.value


def _norm_status(s: str | None) -> str:
    return (s or "").strip().lower()


def _subcomponent_known(status: str | None) -> bool:
    u = _norm_status(status)
    return u not in ("", "unknown", "n/a")


def _inflation_inputs_incomplete(inflation: InflationInput) -> bool:
    if inflation.core_cpi_yoy is None:
        return True
    return not _subcomponent_known(inflation.shelter_status) and not _subcomponent_known(
        inflation.services_ex_energy_status
    )


def inflation_inputs_incomplete(inflation: InflationInput) -> bool:
    """Public alias for macro overlay / other modules."""
    return _inflation_inputs_incomplete(inflation)


def _derive_inflation_headline(
    inflation: InflationInput,
    inflation_incomplete: bool,
    sticky_inflation: bool,
    oil_risk_active: bool,
) -> str:
    if inflation.core_cpi_yoy is None:
        if oil_risk_active:
            return "Oil risk elevated; core confirmation incomplete"
        return "Inflation confirmation incomplete"
    if inflation_incomplete:
        return "Inflation confirmation incomplete"
    if sticky_inflation:
        return "Sticky"
    return "Sticky inflation not confirmed"


def _derive_trap_assessment_note(
    trap_active: bool,
    trap_state: TriState,
    inflation_incomplete: bool,
) -> str | None:
    if trap_active:
        return None
    if trap_state == "unknown":
        return "Stagflation trap evidence is incomplete and limited — avoid treating the absence of a trigger as a clean all-clear."
    if inflation_incomplete:
        return (
            "Inflation confirmation incomplete — trap assessment is limited with available inputs."
        )
    return "Stagflation trap not currently active"


@dataclass
class StagflationResult:
    trap: StagflationTrap
    growth_weakening: bool
    sticky_inflation: bool
    oil_risk_active: bool


def compute_stagflation(
    growth: GrowthInput, inflation: InflationInput
) -> StagflationResult:
    pmi_mfg = growth.pmi_manufacturing
    pmi_svc = growth.pmi_services
    unemp = growth.unemployment_rate
    unemp_trend = (growth.unemployment_trend or "").lower()
    claims_trend = (growth.initial_claims_trend or "").lower()
    payrolls_trend = (growth.payrolls_trend or "").lower()

    # ── Growth Weakening ────────────────────────────────────────────────────
    # Primary: manufacturing PMI below 50
    mfg_weak = pmi_mfg is not None and pmi_mfg < _PMI_CONTRACTION

    # At least one secondary signal
    svc_softening = pmi_svc is not None and pmi_svc < _PMI_CONTRACTION + 1.0
    labor_softening = any([
        unemp_trend == "up",
        claims_trend == "up",
        payrolls_trend == "down",
    ])

    growth_state: TriState
    if pmi_mfg is None:
        growth_state = "unknown"
    elif mfg_weak and (svc_softening or labor_softening):
        growth_state = "true"
    elif not mfg_weak:
        growth_state = "false"
    elif pmi_svc is None and not labor_softening:
        growth_state = "unknown"
    else:
        growth_state = "false"
    growth_weakening = growth_state == "true"

    # ── Oil Risk ────────────────────────────────────────────────────────────
    if inflation.oil_risk_active is not None:
        oil_risk_active = inflation.oil_risk_active
    elif inflation.wti_oil is not None:
        oil_risk_active = inflation.wti_oil >= _OIL_RISK_THRESHOLD
    else:
        oil_risk_active = False

    # ── Sticky Inflation ────────────────────────────────────────────────────
    cpi_elevated = (
        inflation.core_cpi_yoy is not None
        and inflation.core_cpi_yoy > _CPI_STICKY_THRESHOLD
    )
    shelter_sticky = (inflation.shelter_status or "").lower() == "sticky"
    svc_ex_sticky = (inflation.services_ex_energy_status or "").lower() == "sticky"

    sticky_signal = cpi_elevated and any([
        shelter_sticky,
        svc_ex_sticky,
        oil_risk_active,
        inflation.wti_oil is not None and inflation.wti_oil >= _OIL_RISK_THRESHOLD,
    ])
    if inflation.core_cpi_yoy is None:
        sticky_state: TriState = "unknown"
    elif sticky_signal:
        sticky_state = "true"
    elif _inflation_inputs_incomplete(inflation):
        sticky_state = "unknown"
    else:
        sticky_state = "false"
    sticky_inflation = sticky_state == "true"

    # ── Full Trap ────────────────────────────────────────────────────────────
    # Requires all three: PMI contracting, unemployment in low-but-not-cracked band,
    # CPI above threshold
    unemp_in_trap_band = (
        unemp is not None
        and _UNEMP_TRAP_LOW <= unemp <= _UNEMP_TRAP_HIGH
    )
    if pmi_mfg is None or unemp is None or inflation.core_cpi_yoy is None:
        trap_state: TriState = "unknown"
    elif mfg_weak and unemp_in_trap_band and cpi_elevated:
        trap_state = "true"
    elif _inflation_inputs_incomplete(inflation) and not sticky_signal:
        trap_state = "unknown"
    else:
        trap_state = "false"
    trap_active = trap_state == "true"

    inflation_incomplete = _inflation_inputs_incomplete(inflation)
    inflation_headline = _derive_inflation_headline(
        inflation,
        inflation_incomplete,
        sticky_inflation,
        oil_risk_active,
    )
    trap_note = _derive_trap_assessment_note(trap_active, trap_state, inflation_incomplete)

    trap = StagflationTrap(
        active=trap_active,
        growth_weakening=growth_weakening,
        sticky_inflation=sticky_inflation,
        growth_weakening_state=growth_state,
        sticky_inflation_state=sticky_state,
        trap_state=trap_state,
        inflation_headline=inflation_headline,
        inflation_inputs_incomplete=inflation_incomplete,
        trap_assessment_note=trap_note,
        pmi_manufacturing=pmi_mfg,
        pmi_services=pmi_svc,
        unemployment_rate=unemp,
        core_cpi_yoy=inflation.core_cpi_yoy,
        shelter_status=inflation.shelter_status,
        services_ex_energy_status=inflation.services_ex_energy_status,
        wti_oil=inflation.wti_oil,
        oil_risk_active=oil_risk_active,
    )

    return StagflationResult(
        trap=trap,
        growth_weakening=growth_weakening,
        sticky_inflation=sticky_inflation,
        oil_risk_active=oil_risk_active,
    )
