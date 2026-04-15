"""
Regime Classification — Module 7.

Computes primary_regime, tactical_state, secondary_overlays, confidence,
and current_posture from the outputs of all other rule modules.
from the outputs of all other rule modules.

All classification is deterministic. The LLM never touches this logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.rules.chessboard import ChessboardResult
from app.services.rules.rally import RallyResult
from app.services.rules.stagflation import StagflationResult
from app.services.rules.stress import DollarResult, StressResult
from app.services.rules.valuation import ValuationResult

# Primary regime labels — quadrant first
R_QUADRANT_A = "Quadrant A / Max Liquidity"
R_QUADRANT_B = "Quadrant B / Mixed Liquidity"
R_QUADRANT_C = "Quadrant C / Liquidity Transition"
R_QUADRANT_D = "Quadrant D / Illiquid Regime"
R_QUADRANT_UNKNOWN = "Quadrant Unknown / Wait"

# Tactical state labels
T_AGGRESSIVE = "Aggressive risk-on"
T_SELECTIVE = "Selective accumulation"
T_START_SLOWLY = "Start buying very slowly"
T_HOLD_NO_ADD = "Hold / no new buying"
T_DEFENSIVE = "Defensive preservation"
T_WAIT = "Wait for cleaner signal"

# Overlay labels
O_STICKY_INFLATION = "Sticky Inflation"
O_GROWTH_WEAKENING = "Growth Weakening"
O_RALLY_FUEL = "Rally Fuel Active"
O_SYSTEMIC_STRESS = "Systemic Stress Rising"
O_DOLLAR_PRESSURE = "Dollar Pressure"
O_VAL_SUPPORTIVE = "Valuation Supportive"
O_VAL_DANGEROUS = "Valuation Stretched"   # matches zone_label language; non-sensational


@dataclass
class RegimeResult:
    primary_regime: str
    tactical_state: str
    legacy_regime_label: str
    secondary_overlays: list[str]
    confidence: str
    current_posture: str


def _quadrant_regime_label(cb: ChessboardResult) -> str:
    return {
        "A": R_QUADRANT_A,
        "B": R_QUADRANT_B,
        "C": R_QUADRANT_C,
        "D": R_QUADRANT_D,
    }.get(cb.quadrant, R_QUADRANT_UNKNOWN)


def _derive_tactical_state(
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
) -> str:
    transition_path = cb.chessboard.liquidity_transition_path

    if cb.quadrant == "Unknown":
        return T_WAIT
    if stress.stress_severe:
        return T_DEFENSIVE
    if cb.quadrant == "D":
        if (
            transition_path == "D_to_C"
            and val.can_support_buy_zone
            and not stag.trap.active
            and not stress.stress_severe
        ):
            return T_START_SLOWLY
        return T_DEFENSIVE
    if cb.quadrant == "A":
        if val.can_pause_new_buying or stag.trap.active:
            return T_HOLD_NO_ADD
        return T_AGGRESSIVE
    if cb.quadrant == "B":
        if val.can_pause_new_buying or stag.trap.active:
            return T_HOLD_NO_ADD
        return T_SELECTIVE
    if val.can_pause_new_buying:
        return T_HOLD_NO_ADD
    if val.can_support_buy_zone and cb.chessboard.transition_tag in {"Improving", "Stable"} and not stag.trap.active:
        return T_START_SLOWLY
    if stag.trap.active:
        return T_HOLD_NO_ADD
    return T_SELECTIVE


def _legacy_label(
    tactical_state: str,
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
) -> str:
    if stress.stress_severe:
        return "Crash Watch"
    if stag.trap.active:
        return "Stagflation Trap"
    if tactical_state == T_AGGRESSIVE:
        return "Max Liquidity"
    if tactical_state == T_START_SLOWLY:
        return "Buy-the-Dip Window"
    if tactical_state == T_HOLD_NO_ADD and val.can_pause_new_buying:
        return "Valuation Stretched"
    if tactical_state == T_DEFENSIVE:
        return "Defensive / Illiquid Regime"
    if cb.quadrant == "C":
        return "Liquidity Transition"
    return "Mixed / Conflicted Regime"


def compute_regime(
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
    dollar: DollarResult,
    rally: RallyResult,
) -> RegimeResult:
    primary_regime = _quadrant_regime_label(cb)
    tactical_state = _derive_tactical_state(cb, stag, val, stress)
    legacy_regime_label = _legacy_label(tactical_state, cb, stag, val, stress)

    # ── Secondary overlays ───────────────────────────────────────────────────
    overlays: list[str] = []

    if stag.sticky_inflation:
        overlays.append(O_STICKY_INFLATION)
    if stag.growth_weakening:
        overlays.append(O_GROWTH_WEAKENING)
    if rally.rally_fuel_score >= 60:
        overlays.append(O_RALLY_FUEL)
    if stress.stress_warning_active:
        overlays.append(O_SYSTEMIC_STRESS)
    if dollar.dxy_pressure:
        overlays.append(O_DOLLAR_PRESSURE)
    if val.can_support_buy_zone:
        overlays.append(O_VAL_SUPPORTIVE)
    if val.can_pause_new_buying:
        overlays.append(O_VAL_DANGEROUS)

    # ── Confidence ───────────────────────────────────────────────────────────
    # Count how many signals align with the classified regime
    aligning = 0
    if cb.quadrant in {"A", "B", "C", "D"}:
        aligning += 2
    if stag.trap.active:
        aligning += 1
    if stress.stress_warning_active or stress.stress_severe:
        aligning += 1
    if val.can_support_buy_zone or val.can_pause_new_buying:
        aligning += 1
    if aligning >= 4:
        confidence = "High"
    elif aligning >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    posture = _derive_posture(tactical_state)

    return RegimeResult(
        primary_regime=primary_regime,
        tactical_state=tactical_state,
        legacy_regime_label=legacy_regime_label,
        secondary_overlays=overlays,
        confidence=confidence,
        current_posture=posture,
    )


def _derive_posture(
    tactical_state: str,
) -> str:
    if tactical_state == T_AGGRESSIVE:
        return (
            "Liquidity is strongly supportive; aggressive growth exposure is acceptable, "
            "but exit discipline matters if rates re-accelerate or support fades."
        )
    if tactical_state == T_SELECTIVE:
        return (
            "Stay selective. Favor profitable or refinancing-resilient growth, "
            "and avoid acting as if this is a full-liquidity regime."
        )
    if tactical_state == T_START_SLOWLY:
        return (
            "Start buying very slowly. Conditions are improving, but this is still a "
            "transition regime, not a full-liquidity chase."
        )
    if tactical_state == T_HOLD_NO_ADD:
        return (
            "Hold existing quality positions, but do not add aggressively at current "
            "valuation levels."
        )
    if tactical_state == T_DEFENSIVE:
        return (
            "Preserve capital. Favor balance-sheet strength, lower leverage, and "
            "defensive quality."
        )
    return (
        "Signals are unresolved. Wait for cleaner confirmation before taking fresh risk."
    )
