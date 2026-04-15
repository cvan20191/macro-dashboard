"""Fed Chessboard — quadrant-first, medium-term doctrine model."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import FedChessboard
from app.schemas.indicator_snapshot import LiquidityInput

# ── Heuristic implementation helpers ─────────────────────────────────────────
# These constants are heuristic defaults — implementation helpers, not
# transcript-exact speaker doctrine. Do not surface these in the UI as if they
# were universal economic laws.

# Zero-bound shortcut: rate at or near ZLB is unambiguously "easy"
_POLICY_ZERO_BOUND: float = 0.50

# Cycle-aware bands applied to 0–1 normalized cycle position
# (bottom 30% of trailing cycle range → easy; top 30% → restrictive)
_CYCLE_EASY_MAX: float = 0.30
_CYCLE_RESTRICTIVE_MIN: float = 0.70

# Fallback fixed bands used only when cycle history is unavailable.
# Labelled explicitly as fallback heuristics; the cycle-aware path is preferred.
_POLICY_EASY_FALLBACK: float = 1.0
_POLICY_RESTRICTIVE_FALLBACK: float = 3.5


# ── Helper functions ──────────────────────────────────────────────────────────

def _policy_stance(rate: float | None, cycle_pos: float | None) -> str:
    """
    Classify policy stance as 'easy' | 'middle' | 'restrictive'.

    Inference order (most to least preferred):
    1. Zero-bound shortcut — rate at or near ZLB is unambiguously easy.
    2. Cycle-aware inference — rate position within trailing 36-month range.
    3. Fallback fixed bands — used only when cycle history is unavailable.

    Rate impulse does NOT remap the middle band. Trend is reserved for the
    transition tag only.
    """
    # 1. Zero-bound shortcut
    if rate is not None and rate <= _POLICY_ZERO_BOUND:
        return "easy"

    # 2. Cycle-aware inference (preferred over fixed cutoffs when available)
    if cycle_pos is not None:
        if cycle_pos <= _CYCLE_EASY_MAX:
            return "easy"
        if cycle_pos >= _CYCLE_RESTRICTIVE_MIN:
            return "restrictive"
        return "middle"

    # 3. Fallback fixed bands (cycle history unavailable)
    if rate is None:
        return "middle"
    if rate <= _POLICY_EASY_FALLBACK:
        return "easy"
    if rate >= _POLICY_RESTRICTIVE_FALLBACK:
        return "restrictive"
    return "middle"

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


def compute_chessboard(liq: LiquidityInput) -> ChessboardResult:
    stance = _policy_stance(liq.fed_funds_rate, liq.rate_cycle_position)
    rate_direction = liq.rate_direction_medium_term or _legacy_rate_direction_medium_term(liq)
    rate_impulse_short = liq.rate_impulse_short or _legacy_rate_impulse_short(liq, rate_direction)
    balance_sheet_direction = (
        liq.balance_sheet_direction_medium_term
        or _legacy_balance_sheet_direction_medium_term(liq)
    )
    balance_sheet_pace = liq.balance_sheet_pace or _legacy_balance_sheet_pace(liq, balance_sheet_direction)

    if rate_direction == "easing" and balance_sheet_direction == "expanding":
        quadrant = "A"
        label = "MAX LIQUIDITY"
    elif rate_direction == "tightening" and balance_sheet_direction == "expanding":
        quadrant = "B"
        label = "MIXED LIQUIDITY: BALANCE SHEET SUPPORT"
    elif rate_direction == "easing" and balance_sheet_direction == "contracting":
        quadrant = "C"
        label = "TRANSITION TO EASIER MONEY"
    elif rate_direction == "tightening" and balance_sheet_direction == "contracting":
        quadrant = "D"
        label = "MAX ILLIQUIDITY"
    else:
        quadrant = "Unknown"
        label = "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"

    if quadrant == "A":
        transition_tag = "Improving"
    elif quadrant == "B":
        transition_tag = "Stable"
    elif quadrant == "C":
        if balance_sheet_pace == "contracting_slower" or rate_impulse_short == "confirming_easing":
            transition_tag = "Improving"
        elif rate_impulse_short == "mixed":
            transition_tag = "Stable"
        else:
            transition_tag = "Stable"
    elif quadrant == "D":
        if balance_sheet_pace == "contracting_slower" and rate_impulse_short in {"stable", "mixed"}:
            transition_tag = "Stable"
        else:
            transition_tag = "Deteriorating"
    else:
        transition_tag = "Stable"

    liquidity_improving = quadrant == "A" or (
        quadrant == "C" and transition_tag == "Improving"
    )
    liquidity_tight = quadrant == "D" or (
        quadrant == "C" and transition_tag == "Deteriorating"
    )

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
        policy_stance=stance,
        rate_impulse=rate_impulse_short,
        balance_sheet_direction=balance_sheet_direction,
        balance_sheet_pace=balance_sheet_pace,
        transition_tag=transition_tag,
        rate_direction_medium_term=rate_direction,
        rate_impulse_short=rate_impulse_short,
        balance_sheet_direction_medium_term=balance_sheet_direction,
        quadrant_basis_note=(
            liq.quadrant_basis_note
            or "Quadrant uses medium-term Fed rate direction plus medium-term Fed "
            "balance-sheet direction; short impulse and balance-sheet pace only "
            "modify transition."
        ),
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
