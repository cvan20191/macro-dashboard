from __future__ import annotations

from app.services.providers.trading_economics_client import normalize_calendar_row


def test_normalize_calendar_upcoming() -> None:
    raw = {
        "CalendarId": 123,
        "Date": "2026-04-10T12:30:00",
        "Country": "United States",
        "Category": "Labour",
        "Event": "Jobless Claims",
        "Importance": 2,
        "Previous": "218K",
        "Forecast": "215K",
        "Actual": "",
        "Revised": "",
        "TEForecast": "",
        "LastUpdate": "2026-04-01",
    }
    n = normalize_calendar_row(raw)
    assert n["status"] == "upcoming"
    assert n["event_name"] == "Jobless Claims"
    assert n["consensus"] == "215K"


def test_normalize_calendar_released() -> None:
    raw = {
        "CalendarId": 124,
        "Date": "2026-04-01T12:30:00",
        "Country": "United States",
        "Category": "Inflation",
        "Event": "Core CPI YoY",
        "Importance": 3,
        "Previous": "3.0%",
        "Forecast": "2.9%",
        "Actual": "3.1%",
    }
    n = normalize_calendar_row(raw)
    assert n["status"] == "released"
    assert n["actual"] == "3.1%"
