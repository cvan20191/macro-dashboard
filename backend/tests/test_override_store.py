from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.services import override_store


def test_get_active_override_ignores_expired_entries(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    path = tmp_path / "override_registry.json"
    path.write_text(
        json.dumps(
            [
                {
                    "key": "pmi_manufacturing",
                    "value": 49.1,
                    "source_class": "manual",
                    "entered_at": (now - timedelta(days=2)).isoformat(),
                    "effective_at": (now - timedelta(days=2)).isoformat(),
                    "expires_at": (now - timedelta(days=1)).isoformat(),
                },
                {
                    "key": "pmi_manufacturing",
                    "value": 50.2,
                    "source_class": "manual",
                    "entered_at": (now - timedelta(hours=1)).isoformat(),
                },
            ]
        ),
        encoding="utf-8",
    )
    original = override_store._OVERRIDE_PATH
    override_store._OVERRIDE_PATH = path
    try:
        active = override_store.get_active_override("pmi_manufacturing", now=now)
    finally:
        override_store._OVERRIDE_PATH = original

    assert active is not None
    assert float(active.value) == 50.2
