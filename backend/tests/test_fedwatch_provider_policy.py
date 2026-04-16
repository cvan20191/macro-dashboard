from __future__ import annotations

from datetime import date

from app.services.providers import fedwatch_client


def test_live_cme_snapshot_wins_and_is_cached(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "fedwatch_snapshot.cache.json"
    manual_path = tmp_path / "fedwatch_snapshot.json"

    manual_path.write_text(
        """
        {
          "as_of": "2025-09-01",
          "source_mode": "manual_snapshot",
          "current_target_mid": 4.375,
          "meetings": []
        }
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_CACHE_PATH", cache_path)
    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_SNAPSHOT_PATH", manual_path)

    def _live() -> dict[str, object]:
        return {
            "as_of": "2025-10-02",
            "source_mode": "cme_fedwatch_api",
            "current_target_mid": 4.375,
            "meetings": [
                {
                    "meeting_label": "2025-11",
                    "meeting_date": "2025-11-06",
                    "expected_end_rate_mid": 4.125,
                }
            ],
        }

    out = fedwatch_client.load_best_fedwatch_snapshot(
        current_as_of=date(2025, 10, 2),
        fetch_live_snapshot=_live,
    )

    assert out["source_mode"] == "cme_fedwatch_api"
    assert cache_path.exists()


def test_cache_wins_when_live_fails(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "fedwatch_snapshot.cache.json"
    manual_path = tmp_path / "fedwatch_snapshot.json"

    cache_path.write_text(
        """
        {
          "as_of": "2025-10-01",
          "source_mode": "cme_fedwatch_cache",
          "current_target_mid": 4.375,
          "meetings": []
        }
        """.strip(),
        encoding="utf-8",
    )
    manual_path.write_text(
        """
        {
          "as_of": "2025-09-01",
          "source_mode": "manual_snapshot",
          "current_target_mid": 4.375,
          "meetings": []
        }
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_CACHE_PATH", cache_path)
    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_SNAPSHOT_PATH", manual_path)

    def _fail() -> dict[str, object]:
        raise RuntimeError("live CME unavailable")

    out = fedwatch_client.load_best_fedwatch_snapshot(
        current_as_of=date(2025, 10, 2),
        fetch_live_snapshot=_fail,
    )

    assert out["source_mode"] == "cme_fedwatch_cache"
    assert out["as_of"] == "2025-10-01"


def test_manual_snapshot_is_final_fallback(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "fedwatch_snapshot.cache.json"
    manual_path = tmp_path / "fedwatch_snapshot.json"

    manual_path.write_text(
        """
        {
          "as_of": "2025-09-01",
          "source_mode": "manual_snapshot",
          "current_target_mid": 4.375,
          "meetings": []
        }
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_CACHE_PATH", cache_path)
    monkeypatch.setattr(fedwatch_client, "DEFAULT_FEDWATCH_SNAPSHOT_PATH", manual_path)

    def _fail() -> dict[str, object]:
        raise RuntimeError("live CME unavailable")

    out = fedwatch_client.load_best_fedwatch_snapshot(
        current_as_of=date(2025, 10, 2),
        fetch_live_snapshot=_fail,
    )

    assert out["source_mode"] == "manual_snapshot"
    assert out["as_of"] == "2025-09-01"
