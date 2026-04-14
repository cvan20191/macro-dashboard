"""
Fed Chessboard — Module 1.

Two-layer model:
  Layer 1 — Primary Quadrant: A / B / C / D
            based on directional rate impulse + balance_sheet_direction
  Layer 2 — Transition Tag: Improving / Stable / Deteriorating
            based on the same impulse signals, contextualized by quadrant

Speaker-faithful directional meanings:
  A  rates down + balance sheet up   → MAX LIQUIDITY
  B  rates up   + balance sheet up   → MIXED LIQUIDITY
  C  rates down + balance sheet down → TRANSITION / MIXED
  D  rates up   + balance sheet down → MAX ILLIQUIDITY

Policy stance remains a secondary context signal for downstream overlays/copy.
"""

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


def _rate_impulse(liq: LiquidityInput) -> str:
    """
    Speaker-faithful timing:
    - 3m trend defines the regime path
    - 1m trend only confirms or creates ambiguity
    - 1m noise must not create a new quadrant by itself
    """
    t1 = (liq.rate_trend_1m or "").lower()
    t3 = (liq.rate_trend_3m or "").lower()

    if t3 == "down":
        return "mixed" if t1 == "up" else "easing"
    if t3 == "up":
        return "mixed" if t1 == "down" else "tightening"
    if t3 == "flat":
        return "stable"
    return "stable"


def _bs_direction(liq: LiquidityInput) -> str:
    """
    3m trend defines the medium-term balance-sheet direction.
    1m does not override it by itself.
    """
    b3 = (liq.balance_sheet_trend_3m or "").lower()

    if b3 == "up":
        return "expanding"
    if b3 == "down":
        return "contracting"
    return "flat_or_mixed"


def _bs_pace(liq: LiquidityInput) -> str:
    """
    Distinguish 'still contracting, but slower' from actual expansion.
    """
    b1 = (liq.balance_sheet_trend_1m or "").lower()
    b3 = (liq.balance_sheet_trend_3m or "").lower()

    if b3 == "down":
        if b1 in {"flat", "up"}:
            return "contracting_slower"
        return "contracting_same_or_faster"
    if b3 == "up":
        if b1 in {"flat", "down"}:
            return "expanding_slower"
        return "expanding_same_or_faster"
    return "flat_or_mixed"


@dataclass
class ChessboardResult:
    chessboard: FedChessboard
    liquidity_improving: bool
    liquidity_tight: bool
    quadrant: str  # "A" | "B" | "C" | "D" | "Unknown"


def compute_chessboard(liq: LiquidityInput) -> ChessboardResult:
    """
    Determine the Fed Chessboard quadrant and transition tag.

    Primary quadrant is directional: rate impulse + balance-sheet direction.
    Policy stance is retained as secondary context only.
    """
    stance = _policy_stance(liq.fed_funds_rate, liq.rate_cycle_position)
    impulse = _rate_impulse(liq)
    bs_dir = _bs_direction(liq)
    bs_pace = _bs_pace(liq)

    # ── Primary Quadrant (strict directional doctrine map) ───────────────────
    if impulse == "easing" and bs_dir == "expanding":
        quadrant = "A"
        label = "MAX LIQUIDITY"
    elif impulse == "tightening" and bs_dir == "expanding":
        quadrant = "B"
        label = "MIXED LIQUIDITY: BALANCE SHEET SUPPORT"
    elif impulse == "easing" and bs_dir == "contracting":
        quadrant = "C"
        label = "TRANSITION TO EASIER MONEY"
    elif impulse == "tightening" and bs_dir == "contracting":
        quadrant = "D"
        label = "MAX ILLIQUIDITY"
    else:
        quadrant = "Unknown"
        label = "AMBIGUOUS / WAIT FOR CLEANER SIGNAL"

    # ── Transition Tag ────────────────────────────────────────────────────────
    if quadrant == "Unknown":
        transition_tag = "Stable"
    else:
        if quadrant == "A":
            transition_tag = "Improving"
        elif quadrant == "B":
            transition_tag = "Stable"
        elif quadrant == "C":
            if bs_pace == "contracting_slower":
                transition_tag = "Improving"
            elif impulse == "mixed":
                transition_tag = "Stable"
            else:
                transition_tag = "Stable"
        elif quadrant == "D":
            if bs_pace == "contracting_slower" and impulse in {"stable", "mixed"}:
                transition_tag = "Stable"
            else:
                transition_tag = "Deteriorating"
        else:
            transition_tag = "Stable"

    # ── Downstream compatibility booleans ────────────────────────────────────
    # Derived from quadrant + transition_tag rather than raw trend strings,
    # keeping downstream logic aligned with the new two-layer model.
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
        rate_impulse=impulse,
        balance_sheet_direction=bs_dir,
        balance_sheet_pace=bs_pace,
        transition_tag=transition_tag,
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
