"""
DashboardState Builder — the orchestrator.

Accepts an IndicatorSnapshot and runs all rule modules in sequence to
produce a fully valid DashboardState. This is the single deterministic
entry point for all rule logic.

Flow:
  1. chessboard
  2. stagflation trap
  3. valuation
  4. systemic stress
  5. dollar context
  6. rally conditions
  7. regime + overlays + confidence + posture
  8. top watchpoints
  9. what changed
  10. what changes the call
  11. assemble DashboardState

Public API:
  build_dashboard_state(snapshot)                -> DashboardState
  build_dashboard_state_with_conclusion(snapshot) -> (DashboardState, PlaybookConclusion)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import DataFreshness, DashboardState, ReasonedText, RegimeTransition
from app.schemas.indicator_snapshot import IndicatorSnapshot
from app.schemas.playbook_conclusion import PlaybookConclusion
from app.services.rules.chessboard import ChessboardResult, compute_chessboard
from app.services.rules.liquidity_plumbing import LiquidityPlumbingResult, compute_liquidity_plumbing
from app.services.rules.playbook_conclusion import build_playbook_conclusion
from app.services.rules.policy_optionality import PolicyOptionalityResult, compute_policy_optionality
from app.services.rules.rally import RallyResult, compute_rally
from app.services.rules.regime import RegimeResult, compute_regime
from app.services.rules.stagflation import StagflationResult, compute_stagflation
from app.services.rules.stress import StressResult, compute_dollar, compute_stress
from app.services.rules.transitions import (
    compute_what_changed,
    compute_what_changed_details,
    compute_what_changes_call,
    compute_what_changes_call_details,
)
from app.services.rules.valuation import ValuationResult, compute_valuation
from app.services.rules.watchpoints import compute_watchpoint_details, compute_watchpoints


@dataclass
class _RuleOutputs:
    """Private container for all intermediate rule results."""
    cb: ChessboardResult
    stag: StagflationResult
    policy_optionality: PolicyOptionalityResult
    val: ValuationResult
    plumbing: LiquidityPlumbingResult
    stress: StressResult
    dollar: object
    rally: RallyResult
    regime: RegimeResult
    watchpoints: list
    watchpoint_details: list[ReasonedText]
    what_changed: list
    what_changed_details: list[ReasonedText]
    what_changes_call: list
    what_changes_call_details: list[ReasonedText]
    freshness: DataFreshness


def _run_rules(snapshot: IndicatorSnapshot) -> _RuleOutputs:
    """
    Run all rule modules in order and return every intermediate result.

    This is the single source of truth for rule computation. Both public
    builder functions delegate here so computation is never duplicated.
    """
    # ── Step 1: Liquidity plumbing overlay ────────────────────────────────────
    plumbing = compute_liquidity_plumbing(snapshot.plumbing)

    # ── Step 2: Fed Chessboard ────────────────────────────────────────────────
    cb = compute_chessboard(snapshot.liquidity, plumbing=plumbing.plumbing)

    # ── Step 3: Stagflation Trap ──────────────────────────────────────────────
    stag = compute_stagflation(snapshot.growth, snapshot.inflation)

    # ── Step 4: Valuation ─────────────────────────────────────────────────────
    val = compute_valuation(snapshot.valuation)

    # ── Step 5: Policy Optionality ────────────────────────────────────────────
    policy_optionality = compute_policy_optionality(snapshot.growth, snapshot.inflation)

    # ── Step 6: Systemic Stress ───────────────────────────────────────────────
    stress = compute_stress(snapshot.systemic_stress)

    # ── Step 7: Dollar Context ────────────────────────────────────────────────
    dollar = compute_dollar(snapshot.dollar_context)

    # ── Step 8: Rally Conditions ──────────────────────────────────────────────
    rally = compute_rally(cb, stag, val, stress, snapshot.policy_support)

    # ── Step 9: Regime ────────────────────────────────────────────────────────
    regime = compute_regime(cb, stag, val, stress, dollar, rally, policy_optionality)

    # ── Step 10: Top Watchpoints ──────────────────────────────────────────────
    watchpoints = compute_watchpoints(
        cb, stag, val, stress, dollar, regime.primary_regime, plumbing
    )
    watchpoint_details = compute_watchpoint_details(
        cb, stag, val, stress, dollar, regime.primary_regime, plumbing
    )

    # ── Step 11: What Changed ─────────────────────────────────────────────────
    what_changed = compute_what_changed(snapshot, cb, stag, val, stress)
    what_changed_details = compute_what_changed_details(snapshot, cb, stag, val, stress)

    # ── Step 12: What Changes the Call ────────────────────────────────────────
    what_changes_call = compute_what_changes_call(regime, val, stag, stress, cb)
    what_changes_call_details = compute_what_changes_call_details(regime, val, stag, stress, cb)

    # ── Step 13: Freshness ────────────────────────────────────────────────────
    freshness = DataFreshness(
        overall_status=snapshot.data_freshness.overall_status or "unknown",
        stale_series=snapshot.data_freshness.stale_series,
    )

    return _RuleOutputs(
        cb=cb,
        stag=stag,
        policy_optionality=policy_optionality,
        val=val,
        plumbing=plumbing,
        stress=stress,
        dollar=dollar,
        rally=rally,
        regime=regime,
        watchpoints=watchpoints,
        watchpoint_details=watchpoint_details,
        what_changed=what_changed,
        what_changed_details=what_changed_details,
        what_changes_call=what_changes_call,
        what_changes_call_details=what_changes_call_details,
        freshness=freshness,
    )


def _score_to_confidence(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.55:
        return "Medium"
    return "Low"


def _derive_confidences(snapshot: IndicatorSnapshot, r: _RuleOutputs) -> tuple[str, str, str]:
    evidence_signals = [
        snapshot.liquidity.fed_funds_rate is not None,
        snapshot.liquidity.balance_sheet_assets is not None,
        snapshot.inflation.core_cpi_yoy is not None,
        snapshot.growth.unemployment_rate is not None,
        snapshot.valuation.forward_pe is not None,
        r.stag.trap.trap_state != "unknown",
        snapshot.plumbing.total_reserves is not None or snapshot.plumbing.repo_total is not None,
    ]
    evidence_score = sum(1 for item in evidence_signals if item) / len(evidence_signals)

    doctrine_score = evidence_score
    if r.val.valuation.signal_mode != "actionable":
        doctrine_score -= 0.15
    if r.stag.trap.trap_state == "unknown":
        doctrine_score -= 0.15
    if snapshot.growth.pmi_manufacturing is None:
        doctrine_score -= 0.1
    if r.plumbing.state in {"elevated", "severe"}:
        doctrine_score -= 0.05

    action_score = doctrine_score
    if r.val.valuation.signal_mode != "actionable":
        action_score -= 0.2
    if r.stag.trap.trap_state == "unknown":
        action_score -= 0.1
    if r.stress.stress.proxy_warning_active:
        action_score -= 0.05
    if r.plumbing.state == "elevated":
        action_score -= 0.05
    elif r.plumbing.state == "severe":
        action_score -= 0.1

    return (
        _score_to_confidence(max(0.0, min(1.0, evidence_score))),
        _score_to_confidence(max(0.0, min(1.0, doctrine_score))),
        _score_to_confidence(max(0.0, min(1.0, action_score))),
    )


def _derive_regime_transition(r: _RuleOutputs) -> RegimeTransition:
    transition_path = r.cb.chessboard.liquidity_transition_path
    if transition_path and transition_path != "none" and "_to_" in transition_path:
        from_regime, to_regime = transition_path.split("_to_", 1)
        reasons = [
            f"transition_path:{transition_path}",
            f"rate_impulse:{r.cb.chessboard.rate_impulse or 'unknown'}",
            f"balance_sheet_pace:{r.cb.chessboard.balance_sheet_pace or 'unknown'}",
        ]
        return RegimeTransition(
            from_regime=from_regime,
            to_regime=to_regime,
            transition_strength="moderate",
            direction="improving",
            reasons=reasons,
        )

    direction = {
        "Improving": "improving",
        "Deteriorating": "deteriorating",
        "Stable": "sideways",
    }.get(r.cb.chessboard.transition_tag or "", "unknown")
    to_regime = r.cb.quadrant
    from_regime: str | None = None
    if direction == "improving":
        if to_regime == "C":
            from_regime = "D"
        elif to_regime == "A":
            from_regime = "B"
        elif to_regime == "B":
            from_regime = "D"
    elif direction == "deteriorating":
        if to_regime == "B":
            from_regime = "A"
        elif to_regime == "D":
            from_regime = "C"
        elif to_regime == "C":
            from_regime = "A"

    strength = "weak"
    if direction in {"improving", "deteriorating"}:
        strength = (
            "strong"
            if r.cb.chessboard.balance_sheet_direction != "flat_or_mixed"
            and r.cb.chessboard.rate_impulse not in {None, "stable", "mixed"}
            else "moderate"
        )

    reasons = [
        f"rate_impulse:{r.cb.chessboard.rate_impulse or 'unknown'}",
        f"balance_sheet_direction:{r.cb.chessboard.balance_sheet_direction or 'unknown'}",
        f"transition_tag:{r.cb.chessboard.transition_tag or 'unknown'}",
    ]
    return RegimeTransition(
        from_regime=from_regime,
        to_regime=to_regime,
        transition_strength=strength,
        direction=direction,
        reasons=reasons,
    )


def _assemble_state(snapshot: IndicatorSnapshot, r: _RuleOutputs) -> DashboardState:
    """Assemble a DashboardState from pre-computed rule outputs."""
    evidence_confidence, doctrine_confidence, action_confidence = _derive_confidences(snapshot, r)
    return DashboardState(
        as_of=snapshot.as_of,
        data_freshness=r.freshness,
        primary_regime=r.regime.primary_regime,
        tactical_state=r.regime.tactical_state,
        legacy_regime_label=r.regime.legacy_regime_label,
        secondary_overlays=r.regime.secondary_overlays,
        confidence=r.regime.confidence,
        evidence_confidence=evidence_confidence,
        doctrine_confidence=doctrine_confidence,
        action_confidence=action_confidence,
        current_posture=r.regime.current_posture,
        regime_transition=_derive_regime_transition(r),
        fed_chessboard=r.cb.chessboard,
        policy_optionality=r.policy_optionality.optionality,
        liquidity_plumbing=r.plumbing.plumbing,
        stagflation_trap=r.stag.trap,
        valuation=r.val.valuation,
        systemic_stress=r.stress.stress,
        dollar_context=r.dollar.dollar,
        rally_conditions=r.rally.conditions,
        exposure_guidance=r.regime.exposure_guidance,
        equity_profile_guidance=r.regime.equity_profile_guidance,
        top_watchpoints=r.watchpoints,
        top_watchpoint_details=r.watchpoint_details,
        what_changed=r.what_changed,
        what_changed_details=r.what_changed_details,
        what_changes_call=r.what_changes_call,
        what_changes_call_details=r.what_changes_call_details,
    )


def build_dashboard_state(snapshot: IndicatorSnapshot) -> DashboardState:
    """
    Deterministic, side-effect-free orchestrator.

    All regime classification, overlay detection, watchpoint ranking,
    and change detection happens here. The LLM never sees raw indicators.
    """
    r = _run_rules(snapshot)
    return _assemble_state(snapshot, r)


def build_dashboard_state_with_conclusion(
    snapshot: IndicatorSnapshot,
) -> tuple[DashboardState, PlaybookConclusion]:
    """
    Companion builder returning both DashboardState and PlaybookConclusion.

    Runs all rule modules exactly once. Use this in any call site that needs
    the structured PlaybookConclusion alongside the standard DashboardState.
    Existing callers of build_dashboard_state() are unaffected.
    """
    r = _run_rules(snapshot)
    state = _assemble_state(snapshot, r)
    conclusion = build_playbook_conclusion(
        cb=r.cb,
        val=r.val,
        stag=r.stag,
        stress=r.stress,
        policy_optionality=r.policy_optionality,
        rally=r.rally,
        regime=r.regime,
    )
    return state, conclusion
