from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

DEFAULT_FEDWATCH_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "fedwatch_snapshot.json"
)
DEFAULT_FEDWATCH_CACHE_PATH = (
    Path(__file__).resolve().parents[3] / ".cache" / "fedwatch_snapshot.cache.json"
)


def _normalize_meeting_date(value: Any) -> str | None:
    if value is None:
        return None

    raw = str(value)[:10]
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return raw


def _to_date(value: Any) -> date | None:
    normalized = _normalize_meeting_date(value)
    if normalized is None:
        return None
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def _normalize_snapshot(raw: dict[str, Any], *, default_source_mode: str) -> dict[str, Any]:
    meetings = raw.get("meetings")
    if not isinstance(meetings, list):
        raise ValueError("FedWatch snapshot -> meetings must be a list.")

    normalized_meetings: list[dict[str, Any]] = []
    for row in meetings:
        if not isinstance(row, dict):
            continue
        normalized_meetings.append(
            {
                "meeting_label": row.get("meeting_label"),
                "meeting_date": _normalize_meeting_date(row.get("meeting_date")),
                "expected_end_rate_mid": row.get("expected_end_rate_mid"),
            }
        )

    return {
        "as_of": _normalize_meeting_date(raw.get("as_of")),
        "source_mode": raw.get("source_mode") or default_source_mode,
        "current_target_mid": raw.get("current_target_mid"),
        "meetings": normalized_meetings,
    }


def load_fedwatch_snapshot(path: Path | None = None) -> dict[str, Any]:
    """
    Deterministic snapshot loader for market-priced easing expectations.

    This deliberately starts with a checked-in normalized snapshot instead of
    a brittle unofficial scrape. If CME FedWatch API data is wired in later,
    keep the same normalized contract behind this loader seam.
    """

    snapshot_path = path or DEFAULT_FEDWATCH_SNAPSHOT_PATH
    if not snapshot_path.exists():
        return {
            "as_of": None,
            "source_mode": "manual_snapshot",
            "current_target_mid": None,
            "meetings": [],
        }

    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fedwatch_snapshot.json must contain an object.")
    return _normalize_snapshot(raw, default_source_mode="manual_snapshot")


def load_cached_fedwatch_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    cache_path = path or DEFAULT_FEDWATCH_CACHE_PATH
    if not cache_path.exists():
        return None

    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return _normalize_snapshot(raw, default_source_mode="cme_fedwatch_cache")


def save_cached_fedwatch_snapshot(
    snapshot: dict[str, Any],
    path: Path | None = None,
) -> None:
    cache_path = path or DEFAULT_FEDWATCH_CACHE_PATH
    normalized = _normalize_snapshot(snapshot, default_source_mode="cme_fedwatch_api")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")


def _pick_newer_snapshot(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if first is None:
        return second
    if second is None:
        return first

    first_date = _to_date(first.get("as_of"))
    second_date = _to_date(second.get("as_of"))

    if first_date and second_date:
        return first if first_date >= second_date else second
    if first_date:
        return first
    if second_date:
        return second
    return first


def load_best_fedwatch_snapshot(
    *,
    current_as_of: date | None,
    current_target_mid: float | None = None,
    fetch_live_snapshot: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Shared provider policy for dashboard and macro overlay:

    1. CME live
    2. dated cache
    3. manual snapshot

    Freshness / hard-actionability is still enforced downstream.
    """

    live_snapshot: dict[str, Any] | None = None
    if fetch_live_snapshot is not None:
        try:
            candidate = fetch_live_snapshot()
        except Exception:
            candidate = None
        if isinstance(candidate, dict) and isinstance(candidate.get("meetings"), list):
            live_snapshot = _normalize_snapshot(candidate, default_source_mode="cme_fedwatch_api")
            if live_snapshot.get("current_target_mid") is None and current_target_mid is not None:
                live_snapshot["current_target_mid"] = current_target_mid
            try:
                save_cached_fedwatch_snapshot(live_snapshot)
            except Exception:
                pass
            return live_snapshot

    cached_snapshot = load_cached_fedwatch_snapshot()
    manual_snapshot = load_fedwatch_snapshot()
    chosen = _pick_newer_snapshot(cached_snapshot, manual_snapshot)

    if chosen is None:
        chosen = {
            "as_of": None,
            "source_mode": "manual_snapshot",
            "current_target_mid": current_target_mid,
            "meetings": [],
        }

    if chosen.get("current_target_mid") is None and current_target_mid is not None:
        chosen["current_target_mid"] = current_target_mid

    return chosen
