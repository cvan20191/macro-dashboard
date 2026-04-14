"""
Audited override registry for curated manual inputs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.override_entry import OverrideEntry

logger = logging.getLogger(__name__)

_OVERRIDE_PATH = Path(__file__).resolve().parents[1] / "data" / "override_registry.json"


def load_override_registry() -> list[OverrideEntry]:
    if not _OVERRIDE_PATH.is_file():
        return []
    try:
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("override registry unreadable: %s", exc)
        return []
    if not isinstance(raw, list):
        return []
    entries: list[OverrideEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(OverrideEntry.model_validate(item))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("invalid override registry entry skipped: %s", exc)
    return entries


def get_active_override(key: str, now: datetime | None = None) -> OverrideEntry | None:
    current = now or datetime.now(timezone.utc)
    for entry in reversed(load_override_registry()):
        if entry.key != key:
            continue
        effective = entry.effective_at or entry.entered_at
        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=timezone.utc)
        if effective > current:
            continue
        if entry.expires_at is not None:
            expires = entry.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= current:
                continue
        return entry
    return None
