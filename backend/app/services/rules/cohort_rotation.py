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


def _valuation_actionable(signal_mode: SignalMode | None) -> bool:
    return (signal_mode or "directional_only") == "actionable"


def _raw_pe_band_for_cohort(cohort_code: str, forward_pe: float | None) -> str:
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


def _hard_pe_band_for_cohort(
    *,
    cohort_code: str,
    forward_pe: float | None,
    signal_mode: SignalMode | None,
) -> str:
    if not _valuation_actionable(signal_mode):
        return "unknown"
    return _raw_pe_band_for_cohort(cohort_code, forward_pe)


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
    any_directional_only = False

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
        raw_pe_band = _raw_pe_band_for_cohort(cohort_code, forward_pe)
        hard_pe_band = _hard_pe_band_for_cohort(
            cohort_code=cohort_code,
            forward_pe=forward_pe,
            signal_mode=signal_mode,
        )

        if signal_mode != "actionable":
            any_directional_only = True

        if cohort_code == "mag7":
            if hard_pe_band == "stretched":
                stance = "avoid"
                reason = "Mag 7 valuation is stretched on an actionable cohort basket."
            elif (
                quadrant == "D"
                and transition_path == "D_to_C"
                and not trapped
                and not weird
                and signal_mode != "actionable"
                and forward_pe is not None
            ):
                stance = "watch"
                if raw_pe_band == "supportive":
                    reason = (
                        "Mag 7 is an emerging transition trade, but the supportive cohort valuation is directional-only, "
                        "so do not accumulate on it yet."
                    )
                elif raw_pe_band == "stretched":
                    reason = (
                        "Mag 7 screens stretched on the visible forward P/E, but the cohort valuation is directional-only, "
                        "so do not hard-avoid on it yet."
                    )
                else:
                    reason = (
                        "Mag 7 is an emerging transition trade, but the cohort valuation is directional-only, "
                        "so do not accumulate on it yet."
                    )
            elif (
                quadrant == "D"
                and transition_path == "D_to_C"
                and hard_pe_band == "supportive"
                and not trapped
                and not weird
            ):
                stance = "accumulate_slowly"
                reason = (
                    "Actual quadrant is still defensive, but the D-to-C transition plus supportive "
                    "Mag 7 valuation on an actionable basket allows slow accumulation."
                )
                favored.append(cohort_code)
            elif trapped or weird or quadrant in {"D", "Unknown"}:
                stance = "underweight"
                reason = "Macro and policy conditions do not justify leaning into the Mag 7 cohort."
                if signal_mode != "actionable" and forward_pe is not None:
                    reason += " Cohort valuation is also directional-only."
            elif free and not weird and not trapped and hard_pe_band == "supportive":
                stance = "overweight"
                reason = (
                    "Policy backdrop is supportive and Mag 7 valuation is in the comfortable zone on an actionable basket."
                )
                favored.append(cohort_code)
            elif signal_mode != "actionable" and forward_pe is not None:
                stance = "watch"
                if raw_pe_band == "stretched":
                    reason = (
                        "Mag 7 screens stretched on the visible forward P/E, but the cohort valuation is directional-only; "
                        "do not hard-avoid on incomplete cohort coverage."
                    )
                else:
                    reason = (
                        "Mag 7 valuation is directional-only; do not hard-rotate on incomplete cohort coverage."
                    )
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
            if hard_pe_band == "stretched":
                stance = "avoid"
                reason = "Non-Mag7 AI valuation is stretched on an actionable cohort basket."
            elif trapped or weird or quadrant in {"D", "Unknown"}:
                stance = "underweight"
                reason = "Non-Mag7 AI is more vulnerable when the easing backdrop is not clean."
                if signal_mode != "actionable" and forward_pe is not None:
                    reason += " Cohort valuation is also directional-only."
            elif free and not weird and not trapped and hard_pe_band == "supportive":
                stance = "overweight"
                reason = (
                    "Policy backdrop is supportive and non-Mag7 AI valuation is not stretched on an actionable basket."
                )
                favored.append(cohort_code)
            elif signal_mode != "actionable" and forward_pe is not None:
                stance = "watch"
                if raw_pe_band == "stretched":
                    reason = (
                        "Non-Mag7 AI screens stretched on the visible forward P/E, but the cohort valuation is directional-only; "
                        "do not hard-avoid on incomplete cohort coverage."
                    )
                else:
                    reason = (
                        "Non-Mag7 AI valuation is directional-only; do not hard-rotate on incomplete cohort coverage."
                    )
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
            if hard_pe_band == "stretched":
                stance = "avoid"
                reason = (
                    "Lower-growth high-valuation non-AI is above the transcript caution band on an actionable basket."
                )
            elif signal_mode != "actionable" and forward_pe is not None:
                stance = "watch"
                if raw_pe_band == "stretched":
                    reason = (
                        "This cohort screens stretched on the visible forward P/E, but the valuation basket is directional-only. "
                        "Do not hard-avoid it until the basket is actionable."
                    )
                else:
                    reason = (
                        "This cohort valuation is directional-only. Do not hard-avoid or hard-favor it until the basket is actionable."
                    )
            elif trapped or weird:
                stance = "neutral"
                reason = "This cohort can stay in the mix only when its own valuation stays controlled."
            elif free and hard_pe_band == "supportive":
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

        if hard_pe_band == "stretched":
            stance = "neutral"
            reason = "Defensive cohort valuation is no longer attractive enough to justify a stronger stance."
            defensive_anchor_code = cohort_code
        elif trapped or weird or quadrant in {"D", "Unknown"}:
            stance = "overweight"
            reason = "Defensive low-valuation cohort is the anchor in constrained or defensive conditions."
            if signal_mode != "actionable" and forward_pe is not None:
                reason += " Valuation basket is directional-only, but the macro anchor still stands."
            favored.append(cohort_code)
            defensive_anchor_code = cohort_code
        elif signal_mode != "actionable" and forward_pe is not None:
            stance = "watch"
            reason = (
                "Defensive cohort valuation is directional-only; keep it as a watchlist or fallback rather than a hard rotation."
            )
            defensive_anchor_code = cohort_code
        elif hard_pe_band == "supportive":
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
            "on an actionable basket can be accumulated slowly as an emerging transition trade."
        )
    elif trapped or weird:
        note = (
            "Policy backdrop is constrained or weird-cut. Defensive cohort should anchor positioning; "
            "growth cohorts should not be leaned on aggressively."
        )
    elif free:
        note = (
            "Policy backdrop is supportive. Growth cohorts can be favored when their own cohort valuation is actionable and not stretched."
        )
    else:
        note = (
            "Cohort rotation remains mixed. Use cohort-specific valuation pressure rather than one basket for the whole market."
        )

    if any_directional_only:
        note = f"{note} Some cohort valuation baskets are directional-only and must not drive hard rotation."

    return CohortRotationResult(
        guidance=CohortRotationGuidance(
            favored_cohort_codes=favored,
            defensive_anchor_code=defensive_anchor_code,
            items=items,
            note=note,
        )
    )
