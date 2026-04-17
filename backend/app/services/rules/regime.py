"""
Regime Classification — Module 7.

Computes primary_regime, tactical_state, secondary_overlays, confidence,
and current_posture from the outputs of all other rule modules.
from the outputs of all other rule modules.

All classification is deterministic. The LLM never touches this logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import (
    EquityProfileGuidance,
    ExposureGuidance,
    MarketEasingExpectations,
)
from app.services.rules.chessboard import ChessboardResult
from app.services.rules.market_pricing_guard import pricing_stretch_blocks_new_buys
from app.services.rules.policy_optionality import PolicyOptionalityResult
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
O_FED_TRAPPED = "Fed Trapped"
O_BAD_DATA_GOOD = "Bad Data Can Be Good"
O_WEIRD_CUT_LOW_ROOM = "Weird Cut / Low Room"


@dataclass
class RegimeResult:
    primary_regime: str
    tactical_state: str
    legacy_regime_label: str
    secondary_overlays: list[str]
    confidence: str
    current_posture: str
    exposure_guidance: ExposureGuidance
    equity_profile_guidance: EquityProfileGuidance


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
    policy_optionality: PolicyOptionalityResult,
    market_priced_easing: MarketEasingExpectations | None = None,
) -> str:
    transition_path = cb.chessboard.liquidity_transition_path

    if cb.quadrant == "Unknown":
        return T_WAIT
    if stress.stress_severe or (stag.trap.active and cb.liquidity_tight):
        return T_DEFENSIVE

    # Actual D remains defensive at the top level. Transition improves the
    # interpretation, but it does not rewrite the base quadrant into C.
    if cb.quadrant == "D":
        return T_DEFENSIVE

    if pricing_stretch_blocks_new_buys(
        fed_chessboard=cb.chessboard,
        market_priced_easing=market_priced_easing,
    ):
        return T_HOLD_NO_ADD

    if cb.quadrant == "A":
        if val.can_pause_new_buying:
            return T_HOLD_NO_ADD
        return T_AGGRESSIVE
    if cb.quadrant == "B":
        if val.can_pause_new_buying:
            return T_HOLD_NO_ADD
        return T_SELECTIVE

    if val.can_pause_new_buying:
        return T_HOLD_NO_ADD

    if (
        val.can_support_buy_zone
        and cb.chessboard.transition_tag in {"Improving", "Stable"}
        and not stag.trap.active
        and not policy_optionality.fed_trapped
        and not policy_optionality.rate_cut_weirdness_active
    ):
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


def _derive_exposure_guidance(cb: ChessboardResult) -> ExposureGuidance:
    """
    Transcript-faithful cash deployment guidance is tied to the actual quadrant,
    not to valuation, transition, or tactical language.
    """
    if cb.quadrant == "A":
        return ExposureGuidance(
            deployment_style="aggressive",
            max_cash_deployment_pct=100,
            leverage_allowed=True,
            note="Most liquid environment. Full cash deployment is acceptable and leverage is permissible.",
        )
    if cb.quadrant == "B":
        return ExposureGuidance(
            deployment_style="selective",
            max_cash_deployment_pct=50,
            leverage_allowed=False,
            note="Mixed liquidity. Stay selective and do not deploy more than about half of cash.",
        )
    if cb.quadrant == "C":
        return ExposureGuidance(
            deployment_style="selective",
            max_cash_deployment_pct=50,
            leverage_allowed=False,
            note="Transition liquidity. Stay selective and do not deploy more than about half of cash.",
        )
    if cb.quadrant == "D":
        return ExposureGuidance(
            deployment_style="defensive",
            max_cash_deployment_pct=20,
            leverage_allowed=False,
            note="Least liquid environment. Keep deployment small, around 20% maximum, or sit on the sideline.",
        )
    return ExposureGuidance(
        deployment_style="wait",
        max_cash_deployment_pct=0,
        leverage_allowed=False,
        note="Signals are unresolved. Wait for cleaner confirmation before deploying new cash.",
    )


def _derive_equity_profile_guidance(cb: ChessboardResult) -> EquityProfileGuidance:
    transition_path = cb.chessboard.liquidity_transition_path

    if cb.quadrant == "A":
        return EquityProfileGuidance(
            primary_profile_code="stock_d_type",
            primary_profile_label="Hyper-growth / loss-making / highly leveraged",
            exit_discipline_required=True,
            same_sector_peer_compare_required=True,
            note=(
                "Most liquid regime. Company D type works best, but exit discipline is mandatory at any sign "
                "of rates turning back up or liquidity support fading."
            ),
        )
    if cb.quadrant == "B":
        return EquityProfileGuidance(
            primary_profile_code="stock_b_type",
            primary_profile_label="Moderate growth / moderate leverage / some profitability",
            secondary_profile_code="stock_c_type",
            secondary_profile_label="High growth / high leverage / refinancing beneficiary",
            same_sector_peer_compare_required=True,
            note=(
                "Mixed liquidity. Company B type is preferred; company C type can also work, but B is safer "
                "under rising-rate pressure."
            ),
        )
    if cb.quadrant == "C":
        return EquityProfileGuidance(
            primary_profile_code="stock_c_type",
            primary_profile_label="High growth / high leverage / refinancing beneficiary",
            secondary_profile_code="stock_b_type",
            secondary_profile_label="Moderate growth / moderate leverage / some profitability",
            same_sector_peer_compare_required=True,
            note=(
                "Transition liquidity. Company C type is preferred; company B type can also work, "
                "but C benefits more from falling rates and refinancing relief."
            ),
        )
    if cb.quadrant == "D":
        if transition_path == "D_to_C":
            return EquityProfileGuidance(
                primary_profile_code="stock_a_type",
                primary_profile_label="Stable / low valuation / low leverage / solvent",
                emerging_profile_code="stock_c_type",
                emerging_profile_label="Emerging C-type: high growth / refinancing beneficiary",
                same_sector_peer_compare_required=True,
                note=(
                    "Actual quadrant remains D, so company A type remains the defensive anchor. "
                    "Because the market is transitioning from D toward C, company C type can begin to emerge, "
                    "but only very slowly."
                ),
            )
        return EquityProfileGuidance(
            primary_profile_code="stock_a_type",
            primary_profile_label="Stable / low valuation / low leverage / solvent",
            same_sector_peer_compare_required=True,
            note="Least liquid regime. Company A type is preferred: stable, low leverage, low valuation, and solvent.",
        )
    return EquityProfileGuidance(
        primary_profile_code="wait",
        primary_profile_label="Wait / no preferred equity profile",
        same_sector_peer_compare_required=True,
        note="Signals are unresolved. Wait for a cleaner macro regime before preferring a stock profile.",
    )


def compute_regime(
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
    dollar: DollarResult,
    rally: RallyResult,
    policy_optionality: PolicyOptionalityResult,
    market_priced_easing: MarketEasingExpectations | None = None,
) -> RegimeResult:
    primary_regime = _quadrant_regime_label(cb)
    tactical_state = _derive_tactical_state(
        cb,
        stag,
        val,
        stress,
        policy_optionality,
        market_priced_easing,
    )
    legacy_regime_label = _legacy_label(tactical_state, cb, stag, val, stress)
    exposure_guidance = _derive_exposure_guidance(cb)
    equity_profile_guidance = _derive_equity_profile_guidance(cb)

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
    if policy_optionality.fed_trapped:
        overlays.append(O_FED_TRAPPED)
    elif policy_optionality.bad_data_is_good_enabled:
        overlays.append(O_BAD_DATA_GOOD)
    if policy_optionality.rate_cut_weirdness_active:
        overlays.append(O_WEIRD_CUT_LOW_ROOM)
    if market_priced_easing is not None and market_priced_easing.pricing_stretch_active:
        overlays.append("Cuts Already Priced In")

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
    if policy_optionality.constraint_level in {"free", "trapped"}:
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
        exposure_guidance=exposure_guidance,
        equity_profile_guidance=equity_profile_guidance,
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
