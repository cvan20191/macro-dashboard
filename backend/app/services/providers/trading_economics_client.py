"""
Trading Economics economic calendar API.

Docs: https://docs.tradingeconomics.com/economic_calendar/snapshot/
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)

_BASE = "https://api.tradingeconomics.com"


def is_available(api_key: str) -> bool:
    return bool(api_key and api_key.strip())


def normalize_calendar_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Map TE API fields to normalized dict (CalendarEventNormalized-compatible)."""
    cal_id = raw.get("CalendarId")
    event_id = str(cal_id) if cal_id is not None else None
    dt = raw.get("Date") or ""
    country = raw.get("Country") or ""
    category = raw.get("Category")
    event_name = raw.get("Event") or ""
    importance = int(raw.get("Importance") or 0)
    previous = _empty_to_none(raw.get("Previous"))
    consensus = _empty_to_none(raw.get("Forecast"))
    actual = _empty_to_none(raw.get("Actual"))
    revised = _empty_to_none(raw.get("Revised"))
    te_fc = _empty_to_none(raw.get("TEForecast"))
    last_up = _empty_to_none(raw.get("LastUpdate"))
    status = "released" if actual not in (None, "",) else "upcoming"
    return {
        "event_id": event_id,
        "release_datetime": str(dt),
        "country": str(country),
        "category": str(category) if category is not None else None,
        "event_name": str(event_name),
        "importance": importance,
        "previous": previous,
        "consensus": consensus,
        "actual": actual,
        "revised_previous": revised,
        "te_forecast": te_fc,
        "last_update": last_up,
        "status": status,
    }


def _empty_to_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return None if s == "" else s


def fetch_us_calendar_range(
    api_key: str,
    start_date: str,
    end_date: str,
    timeout: int = 30,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """
    GET /calendar/country/united%20states/{start}/{end}?c={key}
    Returns list of raw JSON objects (before normalize).
    """
    if not is_available(api_key):
        raise ProviderError("TRADING_ECONOMICS_API_KEY not configured")
    path = f"/calendar/country/united%20states/{start_date}/{end_date}"
    url = f"{_BASE}{path}"
    params = {"c": api_key.strip()}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code in (403, 429):
                    wait = min(2**attempt, 16)
                    logger.warning("TE calendar HTTP %s, retry in %ss", resp.status_code, wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, list):
                    return []
                return data
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in (403, 429) and attempt < max_retries - 1:
                time.sleep(min(2**attempt, 16))
                continue
            raise ProviderError(f"Trading Economics HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt, 16))
                continue
            raise ProviderError(f"Trading Economics request failed: {exc}") from exc
    raise ProviderError(f"Trading Economics failed after retries: {last_exc}")


def default_us_date_window(days_forward: int = 14) -> tuple[str, str]:
    now = datetime.now(timezone.utc).date()
    end = now + timedelta(days=days_forward)
    return now.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
