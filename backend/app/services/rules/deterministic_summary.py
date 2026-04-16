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


def _profile_line(state: DashboardState) -> str | None:
    guide = state.equity_profile_guidance
    if guide is None:
        return None

    base = f"Primary stock profile: {guide.primary_profile_label}."
    if guide.emerging_profile_label:
        base += f" Emerging profile: {guide.emerging_profile_label}."
    if guide.exit_discipline_required:
        base += " Exit discipline is required."
    return base


def _peer_line(state: DashboardState) -> str | None:
    if not state.peer_scorecards:
        return None

    leaders = [card.ticker for card in state.peer_scorecards if card.verdict == "leader"]
    if leaders:
        return f"Peer check: current leaders versus same-sector peers = {', '.join(leaders[:3])}."
    return "Peer check: same-sector comparison is available, but no clear leader is standing out."


def _allocation_line(state: DashboardState) -> str | None:
    plan = state.allocation_plan
    if plan is None:
        return None

    allowed = [lane.label for lane in plan.lanes if lane.permission == "allowed"]
    blocked = [lane.label for lane in plan.lanes if lane.permission == "blocked"]

    parts: list[str] = [f"Allocation plan: {plan.portfolio_action}."]
    if allowed:
        parts.append("Allowed lanes: " + ", ".join(allowed) + ".")
    if blocked:
        parts.append("Blocked lanes: " + ", ".join(blocked) + ".")
    return " ".join(parts)


def _pricing_line(state: DashboardState) -> str | None:
    market_priced_easing = state.market_priced_easing
    if (
        market_priced_easing is None
        or market_priced_easing.expected_cut_count_12m is None
        or market_priced_easing.expected_cut_bps_12m is None
    ):
        return None

    return (
        f"Market pricing: about {market_priced_easing.expected_cut_count_12m} cuts "
        f"({market_priced_easing.expected_cut_bps_12m:.0f} bps) over the next 12 months."
    )


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

    cohort_line = _allocation_line(state)
    profile_line = _profile_line(state)
    peer_line = _peer_line(state)
    pricing_line = _pricing_line(state)

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

    if state.market_priced_easing is not None:
        market_priced_easing = state.market_priced_easing
        if market_priced_easing.pricing_stretch_active and market_priced_easing.hard_actionable:
            cautions.append("Market is already pricing aggressive easing, which looks stretched.")
        elif market_priced_easing.pricing_stretch_active and not market_priced_easing.hard_actionable:
            cautions.append("Market-priced easing snapshot is stale; stretch read is descriptive only.")

    caution_line = " ".join(cautions) if cautions else None

    return DeterministicSummary(
        headline=headline,
        subheadline=subheadline,
        action_line=action_line,
        deployment_line=deployment_line,
        cohort_line=cohort_line,
        profile_line=profile_line,
        peer_line=peer_line,
        pricing_line=pricing_line,
        caution_line=caution_line,
    )
