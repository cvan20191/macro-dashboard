from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.schemas.dashboard_state import (
    LiquidityPlumbing,
    PolicyOptionality,
    StrategicWatchlist,
    StrategicWatchlistItem,
)

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "strategic_watchlist_registry.json"


@dataclass(frozen=True)
class StrategicWatchlistResult:
    watchlist: StrategicWatchlist


def load_strategic_watchlist_registry() -> list[dict]:
    raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("strategic_watchlist_registry.json must contain a list.")
    return raw


def _derive_labor_inflation_item(policy: PolicyOptionality | None) -> StrategicWatchlistItem:
    if policy is None:
        return StrategicWatchlistItem(
            code="labor_inflation",
            label="Labor Market and Inflation",
            kind="derived_macro",
            status="watch",
            source_mode="derived",
            priority=1,
            note="Policy optionality is unavailable, so labor/inflation watch status cannot be assessed cleanly.",
        )

    if policy.fed_trapped or policy.rate_cut_weirdness_active:
        return StrategicWatchlistItem(
            code="labor_inflation",
            label="Labor Market and Inflation",
            kind="derived_macro",
            status="warning",
            source_mode="derived",
            priority=1,
            note=policy.note or "Labor/inflation mix is constraining the Fed. This is a warning state.",
        )

    if policy.constraint_level == "free":
        return StrategicWatchlistItem(
            code="labor_inflation",
            label="Labor Market and Inflation",
            kind="derived_macro",
            status="supportive",
            source_mode="derived",
            priority=1,
            note=policy.note or "Labor slack and cooling inflation are creating room for easier policy.",
        )

    return StrategicWatchlistItem(
        code="labor_inflation",
        label="Labor Market and Inflation",
        kind="derived_macro",
        status="mixed",
        source_mode="derived",
        priority=1,
        note=policy.note or "Labor/inflation mix is mixed; no clean bullish or fully trapped read.",
    )


def _derive_plumbing_item(plumbing: LiquidityPlumbing | None) -> StrategicWatchlistItem:
    if plumbing is None:
        return StrategicWatchlistItem(
            code="bank_reserves_repo_rrp",
            label="Bank Reserves / Repo / Reverse Repo",
            kind="derived_macro",
            status="watch",
            source_mode="derived",
            priority=1,
            note="Plumbing state is unavailable.",
        )

    if plumbing.balance_sheet_expansion_not_qe or plumbing.state in {"elevated", "severe"}:
        return StrategicWatchlistItem(
            code="bank_reserves_repo_rrp",
            label="Bank Reserves / Repo / Reverse Repo",
            kind="derived_macro",
            status="warning",
            source_mode="derived",
            priority=1,
            note=plumbing.caution_note or "Liquidity plumbing is under stress; any balance-sheet support here is not QE.",
        )

    if plumbing.state == "normal":
        return StrategicWatchlistItem(
            code="bank_reserves_repo_rrp",
            label="Bank Reserves / Repo / Reverse Repo",
            kind="derived_macro",
            status="supportive",
            source_mode="derived",
            priority=1,
            note="Liquidity plumbing is not currently showing a stress read.",
        )

    return StrategicWatchlistItem(
        code="bank_reserves_repo_rrp",
        label="Bank Reserves / Repo / Reverse Repo",
        kind="derived_macro",
        status="watch",
        source_mode="derived",
        priority=1,
        note=plumbing.caution_note or "Continue monitoring liquidity plumbing closely.",
    )


def compute_strategic_watchlist(
    *,
    policy_optionality: PolicyOptionality | None,
    liquidity_plumbing: LiquidityPlumbing | None,
    registry: list[dict] | None = None,
) -> StrategicWatchlistResult:
    registry = registry or load_strategic_watchlist_registry()

    items: list[StrategicWatchlistItem] = [
        _derive_labor_inflation_item(policy_optionality),
        _derive_plumbing_item(liquidity_plumbing),
    ]

    for row in registry:
        items.append(
            StrategicWatchlistItem(
                code=str(row.get("code") or ""),
                label=str(row.get("label") or ""),
                kind=str(row.get("kind") or "manual_event"),
                status=str(row.get("status") or "watch"),
                source_mode="manual",
                priority=int(row.get("priority") or 3),
                note=str(row.get("note")) if row.get("note") else None,
            )
        )

    items.sort(key=lambda item: (item.priority, item.label))

    return StrategicWatchlistResult(
        watchlist=StrategicWatchlist(
            items=items,
            note=(
                "Transcript-faithful 2026 watchlist: event-driven items remain manual until a dedicated provider layer is added."
            ),
        )
    )
