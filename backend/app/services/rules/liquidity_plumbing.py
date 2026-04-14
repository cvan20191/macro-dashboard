from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import LiquidityPlumbing
from app.schemas.indicator_snapshot import PlumbingInput

_LOW_RRP_BUFFER_RATIO = 0.35
_HIGH_REPO_SPIKE_RATIO = 2.0


@dataclass
class LiquidityPlumbingResult:
    plumbing: LiquidityPlumbing
    state: str
    state_label: str
    balance_sheet_expansion_not_qe: bool


def _lower(value: str | None) -> str:
    return (value or "").lower()


def compute_liquidity_plumbing(pl: PlumbingInput) -> LiquidityPlumbingResult:
    has_any = any(
        value is not None
        for value in (
            pl.total_reserves,
            pl.repo_total,
            pl.reverse_repo_total,
            pl.reserves_buffer_ratio,
            pl.repo_spike_ratio,
            pl.reverse_repo_buffer_ratio,
            pl.walcl_trend_1m,
        )
    )
    if not has_any:
        plumbing = LiquidityPlumbing(
            state="unknown",
            state_label="Unknown",
            caution_note="Reserve / repo / reverse-repo inputs unavailable.",
        )
        return LiquidityPlumbingResult(
            plumbing=plumbing,
            state="unknown",
            state_label="Unknown",
            balance_sheet_expansion_not_qe=False,
        )

    reserves_down = _lower(pl.reserves_trend_1m) == "down"
    repo_up = _lower(pl.repo_trend_1m) == "up"
    reverse_repo_down = _lower(pl.reverse_repo_trend_1m) == "down"
    repo_spike = pl.repo_spike_ratio is not None and pl.repo_spike_ratio >= _HIGH_REPO_SPIKE_RATIO
    reverse_repo_depleted = (
        pl.reverse_repo_buffer_ratio is not None
        and pl.reverse_repo_buffer_ratio <= _LOW_RRP_BUFFER_RATIO
    )
    walcl_up = _lower(pl.walcl_trend_1m) == "up"

    if repo_spike and reserves_down and reverse_repo_depleted:
        state = "severe"
        state_label = "Funding stress"
        note = (
            "Repo is spiking while reserve buffers are weakening and reverse-repo "
            "buffers are already depleted."
        )
    elif repo_spike and (reserves_down or reverse_repo_depleted):
        state = "elevated"
        state_label = "Plumbing stress"
        note = (
            "Temporary funding operations are rising against a weaker reserve / "
            "reverse-repo backdrop."
        )
    elif reserves_down and reverse_repo_depleted and reverse_repo_down:
        state = "elevated"
        state_label = "Plumbing caution"
        note = (
            "Reserve buffers are thinning while the reverse-repo buffer is draining. "
            "Liquidity quality is worsening even without a visible repo spike."
        )
    elif repo_up and reserves_down:
        state = "elevated"
        state_label = "Plumbing caution"
        note = (
            "Repo usage is rising while reserves are moving lower. "
            "That is a stress read, not a clean liquidity read."
        )
    else:
        state = "normal"
        state_label = "Normal"
        note = None

    balance_sheet_expansion_not_qe = walcl_up and state in {"elevated", "severe"}
    if balance_sheet_expansion_not_qe:
        suffix = " Treat any balance-sheet uptick here as plumbing support, not QE."
        note = f"{note}{suffix}" if note else suffix.strip()

    plumbing = LiquidityPlumbing(
        state=state,
        state_label=state_label,
        reserves_total=pl.total_reserves,
        reserves_trend_1m=pl.reserves_trend_1m,
        reserves_buffer_ratio=pl.reserves_buffer_ratio,
        repo_total=pl.repo_total,
        repo_trend_1m=pl.repo_trend_1m,
        repo_spike_ratio=pl.repo_spike_ratio,
        reverse_repo_total=pl.reverse_repo_total,
        reverse_repo_trend_1m=pl.reverse_repo_trend_1m,
        reverse_repo_buffer_ratio=pl.reverse_repo_buffer_ratio,
        balance_sheet_expansion_not_qe=balance_sheet_expansion_not_qe,
        caution_note=note,
    )
    return LiquidityPlumbingResult(
        plumbing=plumbing,
        state=state,
        state_label=state_label,
        balance_sheet_expansion_not_qe=balance_sheet_expansion_not_qe,
    )
