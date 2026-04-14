"""
Systemic Stress + Dollar Context — Modules 4 & 5.

Crash-gauge style warnings: yield curve, CRE delinquency, card charge-offs,
Z.1 corporate equities / M2 (or legacy SPY proxy), DXY.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.doctrine import DEFAULT_DOCTRINE_PROFILE
from app.schemas.dashboard_state import DollarContext, SystemicStress
from app.schemas.indicator_snapshot import DollarContextInput, SystemicStressInput

# Credit card charge-off rate (CORCCACBN, %, quarterly annualized) — tune vs history
_CARD_CO_CAUTION = 4.6
_CARD_CO_WARNING = 5.5

# Equity / M2 — Z.1 market value (billions) / WM2NS (billions); typical range ~4.5–6+
_MCM2_WARNING_Z1 = DEFAULT_DOCTRINE_PROFILE.corporate_equities_m2_warning.value
_MCM2_EXTREME_Z1 = DEFAULT_DOCTRINE_PROFILE.corporate_equities_m2_extreme.value

# Legacy SPY-scaled proxy only — not comparable to Z.1 levels
_MCM2_WARNING_SPY = 2.0
_MCM2_EXTREME_SPY = 3.0

_DXY_PRESSURE = 100.0


@dataclass
class StressResult:
    stress: SystemicStress
    stress_warning_active: bool
    stress_severe: bool


@dataclass
class DollarResult:
    dollar: DollarContext
    dxy_pressure: bool


def _mcm2_zones(ratio: float | None, source: str | None) -> str | None:
    if ratio is None:
        return None
    if source == "spy_fallback":
        w, x = _MCM2_WARNING_SPY, _MCM2_EXTREME_SPY
    else:
        w, x = _MCM2_WARNING_Z1, _MCM2_EXTREME_Z1
    if ratio < w:
        return "Normal"
    if ratio < x:
        return "Warning"
    return "Extreme"


def compute_stress(s: SystemicStressInput) -> StressResult:
    yc = s.yield_curve_10y_2y
    inverted = yc is not None and yc < 0.0

    npl = s.npl_ratio
    npl_caution = DEFAULT_DOCTRINE_PROFILE.broad_npl_caution.value
    npl_warning = DEFAULT_DOCTRINE_PROFILE.broad_npl_warning.value
    if npl is None:
        npl_zone = None
    elif npl < npl_caution:
        npl_zone = "Normal"
    elif npl < npl_warning:
        npl_zone = "Caution"
    else:
        npl_zone = "Warning"

    cre = s.cre_delinquency_rate
    if cre is None:
        cre_zone = None
    elif cre < npl_caution:
        cre_zone = "Normal"
    elif cre < npl_warning:
        cre_zone = "Caution"
    else:
        cre_zone = "Warning"

    card = s.credit_card_chargeoff_rate
    if card is None:
        card_zone = None
    elif card < _CARD_CO_CAUTION:
        card_zone = "Normal"
    elif card < _CARD_CO_WARNING:
        card_zone = "Caution"
    else:
        card_zone = "Warning"

    src = s.equity_m2_ratio_source
    mcm2 = s.corporate_equities_m2_ratio or s.market_cap_m2_ratio
    mcm2_zone = _mcm2_zones(mcm2, src)
    proxy_warning_active = mcm2_zone in {"Warning", "Extreme"}

    stress_warning_active = any([
        inverted,
        npl_zone in {"Caution", "Warning"},
        card_zone in {"Caution", "Warning"},
    ])
    stress_severe = any([
        npl_zone == "Warning",
        card_zone == "Warning",
    ])

    return StressResult(
        stress=SystemicStress(
            yield_curve_inverted=inverted,
            yield_curve_value=yc,
            npl_ratio=npl,
            npl_zone=npl_zone,
            cre_delinquency_rate=cre,
            cre_delinquency_zone=cre_zone,
            credit_card_chargeoff_rate=card,
            credit_card_chargeoff_zone=card_zone,
            market_cap_m2_ratio=mcm2,
            market_cap_m2_zone=mcm2_zone,
            corporate_equities_m2_ratio=mcm2,
            corporate_equities_m2_zone=mcm2_zone,
            equity_m2_ratio_source=src,
            equity_m2_numerator_as_of=s.equity_m2_numerator_as_of,
            equity_m2_numerator_freshness=s.equity_m2_numerator_freshness,
            proxy_warning_active=proxy_warning_active,
        ),
        stress_warning_active=stress_warning_active,
        stress_severe=stress_severe,
    )


def compute_dollar(d: DollarContextInput) -> DollarResult:
    dxy = d.dxy
    pressure = dxy is not None and dxy > _DXY_PRESSURE
    return DollarResult(
        dollar=DollarContext(dxy=dxy, dxy_pressure=pressure),
        dxy_pressure=pressure,
    )
