from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion import fed_liquidity_cache as flc


def test_upsert_points_overwrites_overlap_dates() -> None:
    existing = {"2026-03-25": 6657161.0, "2026-04-01": 6660000.0}
    incoming = [("2026-04-01", 6661234.0), ("2026-04-08", 6670000.0)]

    merged = flc._upsert_points(existing, incoming)

    assert merged["2026-03-25"] == 6657161.0
    assert merged["2026-04-01"] == 6661234.0
    assert merged["2026-04-08"] == 6670000.0


def test_next_release_helpers() -> None:
    # Wednesday -> next Thursday (1 day later)
    assert flc._next_release_date("weekly_thursday_release", date(2026, 4, 8)) == "2026-04-09"
    # Friday -> next business day Monday
    assert flc._next_release_date("business_daily", date(2026, 4, 10)) == "2026-04-13"


def test_fed_liquidity_endpoint_shape(monkeypatch) -> None:
    def _fake_payload(force_refresh: bool = False) -> dict:
        _ = force_refresh
        return {
            "as_of": "2026-04-08",
            "description": "test payload",
            "generated_at": "2026-04-08T16:30:00Z",
            "fed_balance_sheet": {
                "label": "Fed Balance Sheet (Total Assets)",
                "series_id": "WALCL",
                "latest_date": "2026-04-01",
                "latest_value": 6661234.0,
                "unit": "Millions USD",
                "next_release_date": "2026-04-09",
                "history": [
                    {"date": "2026-03-25", "value": 6657161.0},
                    {"date": "2026-04-01", "value": 6661234.0},
                ],
            },
            "fed_rate": {
                "label": "Fed Funds Target Upper Bound",
                "series_id": "DFEDTARU",
                "latest_date": "2026-04-08",
                "latest_value": 4.5,
                "unit": "Percent",
                "next_release_date": "2026-04-09",
                "history": [
                    {"date": "2026-04-07", "value": 4.5},
                    {"date": "2026-04-08", "value": 4.5},
                ],
            },
        }

    monkeypatch.setattr(
        "app.routers.live_playbook.get_fed_liquidity_overview",
        _fake_payload,
    )

    client = TestClient(app)
    resp = client.get("/api/live/fed-liquidity-overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fed_balance_sheet"]["series_id"] == "WALCL"
    assert body["fed_balance_sheet"]["history"][-1]["date"] == "2026-04-01"
    assert body["fed_rate"]["series_id"] == "DFEDTARU"
