"""Fed Chessboard — quadrant-first, medium-term doctrine model."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import FedChessboard, LiquidityPlumbing
from app.schemas.indicator_snapshot import LiquidityInput

@dataclass
class ChessboardResult:
    chessboard: FedChessboard
    liquidity_improving: bool
    liquidity_tight: bool
    quadrant: str


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
    rate_direction = (liq.rate_direction_medium_term or "unknown").lower()
    rate_impulse_short = (liq.rate_impulse_short or "unknown").lower()
    raw_balance_sheet_direction = (liq.balance_sheet_direction_medium_term or "flat_or_mixed").lower()
    balance_sheet_pace = (liq.balance_sheet_pace or "flat_or_mixed").lower()
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
        if transition_basis_note:
            transition_basis_note = (
                f"{transition_basis_note} Actual quadrant remains D, but the market is transitioning toward C because QT is slowing."
            )
        else:
            transition_basis_note = (
                "Actual quadrant remains D, but the market is transitioning toward C because QT is slowing."
            )
    elif quadrant == "C":
        transition_tag = "Improving" if balance_sheet_pace == "contracting_slower" or rate_impulse_short == "confirming_easing" else "Stable"
    elif quadrant == "A":
        transition_tag = "Improving"
    elif quadrant == "B":
        transition_tag = "Stable"
    elif quadrant == "D":
        transition_tag = "Deteriorating"
    else:
        transition_tag = "Stable"

    liquidity_improving = quadrant in {"A", "C"} or liquidity_transition_path == "D_to_C"
    liquidity_tight = quadrant == "D" and liquidity_transition_path != "D_to_C"

    cb = FedChessboard(
        quadrant=quadrant,
        label=label,
        rate_direction_medium_term=rate_direction,
        rate_impulse_short=rate_impulse_short,
        balance_sheet_direction_medium_term=raw_balance_sheet_direction,
        effective_balance_sheet_direction=effective_balance_sheet_direction,
        balance_sheet_liquidity_interpretation=balance_sheet_liquidity_interpretation,
        balance_sheet_pace=balance_sheet_pace,
        liquidity_transition_path=liquidity_transition_path,
        transition_tag=transition_tag,
        quadrant_basis_note=(
            liq.quadrant_basis_note
            or "Quadrant uses the actual medium-term policy-rate path and the effective market liquidity read from the Fed balance-sheet path."
        ),
        transition_basis_note=transition_basis_note,
    )

    return ChessboardResult(
        chessboard=cb,
        liquidity_improving=liquidity_improving,
        liquidity_tight=liquidity_tight,
        quadrant=quadrant,
    )
