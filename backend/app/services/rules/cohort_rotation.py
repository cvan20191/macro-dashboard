from __future__ import annotations

from dataclasses import dataclass

from app.doctrine import SignalMode
from app.schemas.dashboard_state import (
    CohortRotationGuidance,
    CohortRotationItem,
    CohortValuation,
    FedChessboard,
    PolicyOptionality,
    Valuation,
)


@dataclass(frozen=True)
class CohortRotationResult:
    guidance: CohortRotationGuidance


def _cohort_map(valuation: Valuation | None) -> dict[str, CohortValuation]:
    if valuation is None:
        return {}
    return {row.cohort_code: row for row in valuation.cohort_valuations}


def _pe_band_for_cohort(cohort_code: str, forward_pe: float | None) -> str:
    if forward_pe is None:
        return "unknown"

    if cohort_code in {"mag7", "non_mag7_ai"}:
        if forward_pe <= 25.0:
            return "supportive"
        if forward_pe >= 30.0:
            return "stretched"
        return "neutral"

    if cohort_code == "non_ai_high_valuation":
        if forward_pe > 25.0:
            return "stretched"
        if forward_pe <= 20.0:
            return "supportive"
        return "neutral"

    if cohort_code == "non_ai_low_valuation_defensive":
        if forward_pe <= 20.0:
            return "supportive"
        if forward_pe > 25.0:
            return "stretched"
        return "neutral"

    return "unknown"


def _build_item(
    *,
    cohort_code: str,
    label: str,
    forward_pe: float | None,
    signal_mode: SignalMode,
    stance: str,
    reason: str,
) -> CohortRotationItem:
    return CohortRotationItem(
        cohort_code=cohort_code,
        label=label,
        forward_pe=forward_pe,
        signal_mode=signal_mode,
        stance=stance,
        reason=reason,
    )


def compute_cohort_rotation_guidance(
    *,
    fed_chessboard: FedChessboard | None,
    policy_optionality: PolicyOptionality | None,
    valuation: Valuation | None,
) -> CohortRotationResult:
    cohorts = _cohort_map(valuation)
    quadrant = fed_chessboard.quadrant or "Unknown" if fed_chessboard else "Unknown"
    transition_path = (
        fed_chessboard.liquidity_transition_path or "none" if fed_chessboard else "none"
    )

    trapped = bool(policy_optionality.fed_trapped) if policy_optionality else False
    weird = bool(policy_optionality.rate_cut_weirdness_active) if policy_optionality else False
    free = bool(policy_optionality and policy_optionality.constraint_level == "free")

    items: list[CohortRotationItem] = []
    favored: list[str] = []
    defensive_anchor_code: str | None = None

    for cohort_code in [
        "mag7",
        "non_mag7_ai",
        "non_ai_high_valuation",
        "non_ai_low_valuation_defensive",
    ]:
        row = cohorts.get(cohort_code)
        label = row.label if row is not None else cohort_code.replace("_", " ").title()
        forward_pe = row.forward_pe if row is not None else None
        signal_mode = row.signal_mode if row is not None else "directional_only"
        pe_band = _pe_band_for_cohort(cohort_code, forward_pe)

        if cohort_code == "mag7":
            if (
                quadrant == "D"
                and transition_path == "D_to_C"
                and pe_band == "supportive"
                and not trapped
                and not weird
            ):
                stance = "accumulate_slowly"
                reason = (
                    "Actual quadrant is still defensive, but the D-to-C transition plus supportive "
                    "Mag 7 valuation allows slow accumulation."
                )
                favored.append(cohort_code)
            elif free and not weird and not trapped and pe_band == "supportive":
                stance = "overweight"
                reason = "Policy backdrop is supportive and Mag 7 valuation is in the comfortable zone."
                favored.append(cohort_code)
            elif pe_band == "stretched":
                stance = "avoid"
                reason = "Mag 7 valuation is stretched."
            elif trapped or weird or quadrant in {"D", "Unknown"}:
                stance = "underweight"
                reason = "Macro and policy conditions do not justify leaning into the Mag 7 cohort."
            else:
                stance = "neutral"
                reason = "No clean overweight trigger."

            items.append(
                _build_item(
                    cohort_code=cohort_code,
                    label=label,
                    forward_pe=forward_pe,
                    signal_mode=signal_mode,
                    stance=stance,
                    reason=reason,
                )
            )
            continue

        if cohort_code == "non_mag7_ai":
            if free and not weird and not trapped and pe_band in {"supportive", "neutral"}:
                stance = "overweight" if pe_band == "supportive" else "neutral"
                reason = "Policy backdrop is supportive; non-Mag7 AI can work when it is not stretched."
                if stance == "overweight":
                    favored.append(cohort_code)
            elif pe_band == "stretched":
                stance = "avoid"
                reason = "Non-Mag7 AI valuation is stretched."
            elif trapped or weird or quadrant in {"D", "Unknown"}:
                stance = "underweight"
                reason = "Non-Mag7 AI is more vulnerable when the easing backdrop is not clean."
            else:
                stance = "neutral"
                reason = "No clean overweight trigger."

            items.append(
                _build_item(
                    cohort_code=cohort_code,
                    label=label,
                    forward_pe=forward_pe,
                    signal_mode=signal_mode,
                    stance=stance,
                    reason=reason,
                )
            )
            continue

        if cohort_code == "non_ai_high_valuation":
            if pe_band == "stretched":
                stance = "avoid"
                reason = "Lower-growth high-valuation non-AI is above the transcript caution band."
            elif trapped or weird:
                stance = "neutral"
                reason = "This cohort can stay in the mix only when its own valuation stays controlled."
            elif free and pe_band == "supportive":
                stance = "neutral"
                reason = "Valuation is not excessive, but this is not the primary cohort in a clean easing backdrop."
            else:
                stance = "neutral"
                reason = "No strong transcript-backed overweight signal."

            items.append(
                _build_item(
                    cohort_code=cohort_code,
                    label=label,
                    forward_pe=forward_pe,
                    signal_mode=signal_mode,
                    stance=stance,
                    reason=reason,
                )
            )
            continue

        if trapped or weird or quadrant in {"D", "Unknown"}:
            stance = "overweight"
            reason = "Defensive low-valuation cohort is the anchor in constrained or defensive conditions."
            favored.append(cohort_code)
            defensive_anchor_code = cohort_code
        elif pe_band == "supportive":
            stance = "neutral"
            reason = (
                "Valuation is supportive, but this cohort is no longer the primary overweight when the easing backdrop is clean."
            )
            defensive_anchor_code = cohort_code
        else:
            stance = "neutral"
            reason = "Defensive cohort remains the fallback anchor."
            defensive_anchor_code = cohort_code

        items.append(
            _build_item(
                cohort_code=cohort_code,
                label=label,
                forward_pe=forward_pe,
                signal_mode=signal_mode,
                stance=stance,
                reason=reason,
            )
        )

    if quadrant == "D" and transition_path == "D_to_C":
        note = (
            "Actual quadrant is still D. Defensive cohort remains the anchor, but supportive Mag 7 valuation "
            "can be accumulated slowly as an emerging transition trade."
        )
    elif trapped or weird:
        note = (
            "Policy backdrop is constrained or weird-cut. Defensive cohort should anchor positioning; "
            "growth cohorts should not be leaned on aggressively."
        )
    elif free:
        note = (
            "Policy backdrop is supportive. Growth cohorts can be favored when their own cohort valuation is not stretched."
        )
    else:
        note = (
            "Cohort rotation remains mixed. Use cohort-specific valuation pressure rather than one basket for the whole market."
        )

    return CohortRotationResult(
        guidance=CohortRotationGuidance(
            favored_cohort_codes=favored,
            defensive_anchor_code=defensive_anchor_code,
            items=items,
            note=note,
        )
    )
