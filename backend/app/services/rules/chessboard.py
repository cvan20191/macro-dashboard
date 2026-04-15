"""Fed Chessboard — quadrant-first, medium-term doctrine model."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import FedChessboard, LiquidityPlumbing
from app.schemas.indicator_snapshot import LiquidityInput

def _legacy_rate_direction_medium_term(liq: LiquidityInput) -> str:
    t3 = (liq.rate_trend_3m or "").lower()
    if t3 == "down":
        return "easing"
    if t3 == "up":
        return "tightening"
    if t3 == "flat":
        return "stable"
    return "unknown"


def _legacy_rate_impulse_short(liq: LiquidityInput, medium_term: str) -> str:
    t1 = (liq.rate_trend_1m or "").lower()
    if medium_term == "easing":
        if t1 == "down":
            return "confirming_easing"
        if t1 == "flat":
            return "stable"
        if t1 == "up":
            return "mixed"
    if medium_term == "tightening":
        if t1 == "up":
            return "confirming_tightening"
        if t1 == "flat":
            return "stable"
        if t1 == "down":
            return "mixed"
    if medium_term == "stable":
        return "stable" if t1 == "flat" else "mixed"
    return "unknown"


def _legacy_balance_sheet_direction_medium_term(liq: LiquidityInput) -> str:
    b3 = (liq.balance_sheet_trend_3m or "").lower()
    if b3 == "up":
        return "expanding"
    if b3 == "down":
        return "contracting"
    return "flat_or_mixed"


def _legacy_balance_sheet_pace(liq: LiquidityInput, medium_term: str) -> str:
    b1 = (liq.balance_sheet_trend_1m or "").lower()
    if medium_term == "contracting":
        if b1 in {"flat", "up"}:
            return "contracting_slower"
        if b1 == "down":
            return "contracting_same_or_faster"
    if medium_term == "expanding":
        if b1 in {"flat", "down"}:
            return "expanding_slower"
        if b1 == "up":
            return "expanding_same_or_faster"
    return "flat_or_mixed"


@dataclass
class ChessboardResult:
    chessboard: FedChessboard
    liquidity_improving: bool
    liquidity_tight: bool
    quadrant: str  # "A" | "B" | "C" | "D" | "Unknown"


def _effective_balance_sheet_direction(
    *,
    raw_direction: str,
    plumbing: LiquidityPlumbing | None,
) -> tuple[str, str, str | None]:
    """
    Keep the raw WALCL direction for audit, but prevent plumbing-driven
    balance-sheet support from masquerading as supportive QE liquidity.
    """
    if raw_direction == "expanding" and plumbing is not None and plumbing.balance_sheet_expansion_not_qe:
        return (
            "flat_or_mixed",
            "plumbing_support_not_qe",
            "Raw balance-sheet expansion is being treated as plumbing support, not QE.",
        )

    if raw_direction == "expanding":
        return ("expanding", "supportive_expansion", None)
    if raw_direction == "contracting":
        return ("contracting", "contracting", None)
    return ("flat_or_mixed", "flat_or_mixed", None)


def compute_chessboard(
    liq: LiquidityInput,
    plumbing: LiquidityPlumbing | None = None,
) -> ChessboardResult:
    rate_direction = liq.rate_direction_medium_term or _legacy_rate_direction_medium_term(liq)
    rate_impulse_short = liq.rate_impulse_short or _legacy_rate_impulse_short(liq, rate_direction)
    raw_balance_sheet_direction = (
        liq.balance_sheet_direction_medium_term
        or _legacy_balance_sheet_direction_medium_term(liq)
    )
    balance_sheet_pace = liq.balance_sheet_pace or _legacy_balance_sheet_pace(liq, raw_balance_sheet_direction)
    (
        effective_balance_sheet_direction,
        balance_sheet_liquidity_interpretation,
        bs_liquidity_note,
    ) = _effective_balance_sheet_direction(
        raw_direction=raw_balance_sheet_direction,
        plumbing=plumbing,
    )

    if rate_direction == "easing" and effective_balance_sheet_direction == "expanding":
        quadrant = "A"
        label = "MAX LIQUIDITY"
    elif rate_direction == "tightening" and effective_balance_sheet_direction == "expanding":
        quadrant = "B"
        label = "MIXED LIQUIDITY: BALANCE SHEET SUPPORT"
    elif rate_direction == "easing" and effective_balance_sheet_direction == "contracting":
        quadrant = "C"
        label = "TRANSITION TO EASIER MONEY"
    elif rate_direction == "tightening" and effective_balance_sheet_direction == "contracting":
        quadrant = "D"
        label = "MAX ILLIQUIDITY"
    else:
        quadrant = "Unknown"
        label = "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"

    liquidity_transition_path = "none"
    transition_basis_note: str | None = bs_liquidity_note

    if quadrant == "D" and balance_sheet_pace == "contracting_slower" and rate_impulse_short in {"stable", "mixed"}:
        liquidity_transition_path = "D_to_C"
        transition_tag = "Improving"
        d_to_c_note = (
            "Actual quadrant remains D, but the path is transitioning toward C because QT is "
            "still ongoing but slowing and the rate path is no longer actively tightening."
        )
        transition_basis_note = (
            f"{transition_basis_note} {d_to_c_note}" if transition_basis_note else d_to_c_note
        )
    elif quadrant == "A":
        transition_tag = "Improving"
    elif quadrant == "B":
        transition_tag = "Stable"
    elif quadrant == "C":
        if balance_sheet_pace == "contracting_slower" or rate_impulse_short == "confirming_easing":
            transition_tag = "Improving"
        else:
            transition_tag = "Stable"
    elif quadrant == "D":
        transition_tag = "Deteriorating"
    else:
        transition_tag = "Stable"

    liquidity_improving = quadrant in {"A", "C"} or liquidity_transition_path == "D_to_C"
    liquidity_tight = quadrant == "D" and liquidity_transition_path != "D_to_C"

    # ── Direction field (preserved for existing consumers) ───────────────────
    direction = _derive_direction(liq)

    cb = FedChessboard(
        quadrant=quadrant,
        label=label,
        rate_trend_1m=liq.rate_trend_1m,
        rate_trend_3m=liq.rate_trend_3m,
        balance_sheet_trend_1m=liq.balance_sheet_trend_1m,
        balance_sheet_trend_3m=liq.balance_sheet_trend_3m,
        direction_vs_1m_ago=direction,
        policy_stance=None,
        rate_impulse=rate_impulse_short,
        balance_sheet_direction=effective_balance_sheet_direction,
        balance_sheet_pace=balance_sheet_pace,
        rate_direction_medium_term=rate_direction,
        rate_impulse_short=rate_impulse_short,
        balance_sheet_direction_medium_term=raw_balance_sheet_direction,
        effective_balance_sheet_direction=effective_balance_sheet_direction,
        balance_sheet_liquidity_interpretation=balance_sheet_liquidity_interpretation,
        liquidity_transition_path=liquidity_transition_path,
        transition_tag=transition_tag,
        quadrant_basis_note=(
            liq.quadrant_basis_note
            or "Quadrant uses the actual medium-term policy-rate path and the effective market "
            "liquidity read from the Fed balance-sheet path."
        ),
        transition_basis_note=transition_basis_note,
    )

    return ChessboardResult(
        chessboard=cb,
        liquidity_improving=liquidity_improving,
        liquidity_tight=liquidity_tight,
        quadrant=quadrant,
    )


def _derive_direction(liq: LiquidityInput) -> str | None:
    """
    Compare 1m vs 3m trends to determine if conditions are improving or
    deteriorating vs a month ago. Preserved for existing consumers.
    """
    r1, r3 = liq.rate_trend_1m, liq.rate_trend_3m
    b1, b3 = liq.balance_sheet_trend_1m, liq.balance_sheet_trend_3m

    if r1 is None and b1 is None:
        return None

    rate_improved = (r1 or "").lower() == "down" and (r3 or "").lower() == "up"
    bs_improved = (b1 or "").lower() == "up" and (b3 or "").lower() in {"down", "flat"}

    rate_worsened = (r1 or "").lower() == "up" and (r3 or "").lower() == "down"
    bs_worsened = (b1 or "").lower() in {"down", "flat"} and (b3 or "").lower() == "up"

    if rate_improved or bs_improved:
        return "improving"
    if rate_worsened or bs_worsened:
        return "deteriorating"
    return "stable"
