from __future__ import annotations

from app.schemas.dashboard_state import DashboardState, DeterministicSummary
from app.schemas.playbook_conclusion import PlaybookConclusion


def _action_text(action: str | None) -> str | None:
    if action == "accumulate":
        return "Action: accumulate."
    if action == "accumulate_selectively":
        return "Action: accumulate selectively."
    if action == "pause_new_buying":
        return "Action: pause new buying."
    if action == "defensive_preservation":
        return "Action: defensive preservation."
    if action == "hold_and_wait":
        return "Action: hold and wait."
    return None


def build_deterministic_summary(
    state: DashboardState,
    conclusion: PlaybookConclusion | None = None,
) -> DeterministicSummary:
    cb = state.fed_chessboard
    quadrant = cb.quadrant if cb is not None and cb.quadrant else "Unknown"
    transition_path = (
        cb.liquidity_transition_path
        if cb is not None and cb.liquidity_transition_path
        else "none"
    )

    headline = state.primary_regime

    if quadrant == "D" and transition_path == "D_to_C":
        subheadline = "Actual quadrant is still D, but liquidity is transitioning toward C."
    elif quadrant == "C":
        subheadline = "Liquidity is improving, but QT is still not fully over."
    elif quadrant == "A":
        subheadline = "Most liquid regime. Aggressive growth can work, but exit discipline matters."
    elif quadrant == "B":
        subheadline = "Mixed liquidity. Stay selective and avoid treating this as a full buy-the-dip regime."
    else:
        subheadline = "Signals are unresolved. Wait for cleaner confirmation."

    action_line = _action_text(conclusion.new_cash_action if conclusion is not None else None)

    deployment_line = None
    if state.exposure_guidance is not None:
        deployment_line = (
            f"Deployment: up to {state.exposure_guidance.max_cash_deployment_pct}% cash; "
            f"leverage allowed = {'yes' if state.exposure_guidance.leverage_allowed else 'no'}."
        )

    cohort_line = None
    if state.cohort_rotation_guidance is not None and state.cohort_rotation_guidance.items:
        favored = state.cohort_rotation_guidance.favored_cohort_codes or []
        if favored:
            cohort_line = "Favored cohorts: " + ", ".join(favored) + "."
        elif state.cohort_rotation_guidance.defensive_anchor_code:
            cohort_line = "Defensive anchor: " + state.cohort_rotation_guidance.defensive_anchor_code + "."

    cautions: list[str] = []

    if state.policy_optionality is not None:
        if state.policy_optionality.fed_trapped:
            cautions.append("Fed is trapped.")
        if state.policy_optionality.rate_cut_weirdness_active:
            cautions.append("Weird-cut / low-room setup is active.")

    if (
        state.liquidity_plumbing is not None
        and state.liquidity_plumbing.balance_sheet_expansion_not_qe
    ):
        cautions.append("Balance-sheet support is plumbing support, not QE.")

    if state.exit_discipline_signal is not None and state.exit_discipline_signal.active:
        cautions.append("Exit discipline is active for the A-regime growth profile.")

    if state.valuation is not None and state.valuation.signal_mode == "directional_only":
        cautions.append("Valuation signal is directional-only, not hard-actionable.")

    caution_line = " ".join(cautions) if cautions else None

    return DeterministicSummary(
        headline=headline,
        subheadline=subheadline,
        action_line=action_line,
        deployment_line=deployment_line,
        cohort_line=cohort_line,
        caution_line=caution_line,
    )
