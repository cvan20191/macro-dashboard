from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import (
    AllocationLane,
    AllocationPlan,
    CohortRotationGuidance,
    ExposureGuidance,
    FedChessboard,
)


@dataclass(frozen=True)
class AllocationPlanResult:
    plan: AllocationPlan


def _permission_from_stance(stance: str) -> str:
    if stance in {"overweight", "accumulate_slowly"}:
        return "allowed"
    if stance in {"underweight", "avoid"}:
        return "blocked"
    return "watch_only"


def compute_allocation_plan(
    *,
    fed_chessboard: FedChessboard | None,
    exposure_guidance: ExposureGuidance | None,
    cohort_rotation_guidance: CohortRotationGuidance | None,
) -> AllocationPlanResult:
    total_cash_cap_pct = (
        exposure_guidance.max_cash_deployment_pct if exposure_guidance is not None else 0
    )
    quadrant = (fed_chessboard.quadrant if fed_chessboard is not None else None) or "Unknown"
    transition_path = (
        (fed_chessboard.liquidity_transition_path if fed_chessboard is not None else None)
        or "none"
    )

    lanes: list[AllocationLane] = []
    allowed_codes: list[str] = []
    defensive_allowed = False

    if cohort_rotation_guidance is not None:
        for item in cohort_rotation_guidance.items:
            permission = _permission_from_stance(item.stance or "neutral")
            lanes.append(
                AllocationLane(
                    cohort_code=item.cohort_code,
                    label=item.label,
                    permission=permission,
                    reason=item.reason,
                )
            )
            if permission == "allowed":
                allowed_codes.append(item.cohort_code)
            if (
                item.cohort_code == cohort_rotation_guidance.defensive_anchor_code
                and permission == "allowed"
            ):
                defensive_allowed = True

    if quadrant == "Unknown":
        portfolio_action = "wait"
        note = "Signals are unresolved. No cohort should receive new cash yet."
    elif quadrant == "D":
        if transition_path == "D_to_C" and allowed_codes:
            portfolio_action = "defensive_only"
            note = (
                "Actual quadrant is still D. New cash is allowed only within the existing defensive cap "
                "and only in explicitly allowed lanes."
            )
        elif defensive_allowed:
            portfolio_action = "defensive_only"
            note = (
                "Macro regime is defensive. New cash is allowed only in the defensive anchor lane "
                "within the existing cap."
            )
        else:
            portfolio_action = "wait"
            note = "Actual quadrant is D and no cohort has earned new-cash permission."
    elif quadrant in {"B", "C"}:
        if allowed_codes:
            portfolio_action = "deploy_within_cap"
            note = (
                "Selective deployment is allowed, but only in explicitly allowed cohort lanes "
                "and only within the existing cap."
            )
        else:
            portfolio_action = "pause_broad_market_adds"
            note = (
                "Do not add broadly. Keep non-blocked cohorts on watch until they earn explicit permission."
            )
    elif quadrant == "A":
        if allowed_codes:
            portfolio_action = "deploy_within_cap"
            note = "Liquidity regime is supportive. Deploy within the cap into explicitly allowed cohorts."
        else:
            portfolio_action = "pause_broad_market_adds"
            note = (
                "Liquidity is supportive, but no cohort currently has explicit valuation or rotation permission."
            )
    else:
        portfolio_action = "wait"
        note = "No clean allocation plan could be derived."

    return AllocationPlanResult(
        plan=AllocationPlan(
            portfolio_action=portfolio_action,
            total_cash_cap_pct=total_cash_cap_pct,
            lanes=lanes,
            note=note,
        )
    )
