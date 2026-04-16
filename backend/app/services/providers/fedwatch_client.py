from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FEDWATCH_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "fedwatch_snapshot.json"
)


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

    meetings = raw.get("meetings")
    if not isinstance(meetings, list):
        raise ValueError("fedwatch_snapshot.json -> meetings must be a list.")

    return {
        "as_of": raw.get("as_of"),
        "source_mode": raw.get("source_mode") or "manual_snapshot",
        "current_target_mid": raw.get("current_target_mid"),
        "meetings": meetings,
    }
