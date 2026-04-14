"""
Fed liquidity overview cache service.

Maintains an incremental, date-keyed cache for:
- WALCL (Fed balance sheet)
- DFEDTARU (Fed funds target upper bound)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.services.ingestion.series_map import FRED_SERIES
from app.services.providers.fred_client import fetch_series_history

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent / ".cache" / "fed_liquidity_overview.json"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class _SeriesConfig:
    cache_key: str
    series_id: str
    label: str
    unit: str
    overlap_days: int
    initial_start_date: str
    cadence: str  # "weekly_thursday_release" | "business_daily"


_SERIES: tuple[_SeriesConfig, ...] = (
    _SeriesConfig(
        cache_key="fed_balance_sheet",
        series_id=FRED_SERIES["balance_sheet"],
        label="Fed Balance Sheet (Total Assets)",
        unit="Millions USD",
        overlap_days=84,
        initial_start_date="2002-01-01",
        cadence="weekly_thursday_release",
    ),
    _SeriesConfig(
        cache_key="fed_rate",
        series_id=FRED_SERIES["fed_funds_rate"],
        label="Fed Funds Target Upper Bound",
        unit="Percent",
        overlap_days=14,
        initial_start_date="2002-01-01",
        cadence="business_daily",
    ),
)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _to_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _parse_iso(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _next_thursday(from_date: date) -> str:
    # Python weekday: Monday=0 ... Sunday=6; Thursday=3
    days_ahead = (3 - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return _to_iso(from_date + timedelta(days=days_ahead))


def _next_business_day(from_date: date) -> str:
    d = from_date + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return _to_iso(d)


def _next_release_date(cadence: str, today: date) -> str:
    if cadence == "weekly_thursday_release":
        return _next_thursday(today)
    return _next_business_day(today)


def _load_cache() -> dict:
    if not _CACHE_FILE.exists():
        return {"version": _CACHE_VERSION, "series": {}}
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Fed liquidity cache unreadable, rebuilding: %s", exc)
        return {"version": _CACHE_VERSION, "series": {}}
    if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
        return {"version": _CACHE_VERSION, "series": {}}
    if not isinstance(data.get("series"), dict):
        data["series"] = {}
    return data


def _save_cache(payload: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _latest_known_date(points: dict[str, float]) -> str | None:
    if not points:
        return None
    return max(points.keys())


def _calc_fetch_start(latest_iso: str | None, overlap_days: int, default_start: str) -> str:
    if not latest_iso:
        return default_start
    latest = _parse_iso(latest_iso)
    return _to_iso(latest - timedelta(days=overlap_days))


def _upsert_points(existing: dict[str, float], incoming: list[tuple[str, float]]) -> dict[str, float]:
    out = dict(existing)
    for d, v in incoming:
        out[d] = v
    return out


def _ordered_history(points: dict[str, float]) -> list[dict[str, float | str]]:
    return [{"date": d, "value": points[d]} for d in sorted(points.keys())]


def _build_lever_payload(cfg: _SeriesConfig, points: dict[str, float], today: date) -> dict:
    latest_date = _latest_known_date(points)
    latest_value = points[latest_date] if latest_date else None
    return {
        "label": cfg.label,
        "series_id": cfg.series_id,
        "latest_date": latest_date or _to_iso(today),
        "latest_value": latest_value,
        "unit": cfg.unit,
        "next_release_date": _next_release_date(cfg.cadence, today),
        "history": _ordered_history(points),
    }


def get_fed_liquidity_overview(force_refresh: bool = False) -> dict:
    """
    Return API-ready Fed liquidity overview payload.

    Uses incremental overlap-upsert against a persisted date-keyed cache.
    """
    cache = _load_cache()
    series_cache: dict = cache["series"]
    now = datetime.now(timezone.utc)
    today = now.date()
    should_persist = False

    for cfg in _SERIES:
        state = series_cache.get(cfg.cache_key)
        points: dict[str, float] = {}
        if isinstance(state, dict) and isinstance(state.get("points"), dict):
            # JSON keys are always strings; values are numeric.
            points = {str(k): float(v) for k, v in state["points"].items()}
        latest_known = _latest_known_date(points)
        start = _calc_fetch_start(latest_known, cfg.overlap_days, cfg.initial_start_date)

        if force_refresh or latest_known is None:
            start = cfg.initial_start_date if force_refresh else start

        try:
            incoming = fetch_series_history(
                series_id=cfg.series_id,
                api_key=settings.fred_api_key,
                timeout=settings.http_timeout_seconds,
                observation_start=start,
            )
            if incoming:
                merged = _upsert_points(points, incoming)
                if merged != points:
                    points = merged
                    should_persist = True
        except Exception as exc:
            logger.warning("Fed liquidity fetch failed for %s: %s", cfg.series_id, exc)

        series_cache[cfg.cache_key] = {
            "series_id": cfg.series_id,
            "points": points,
            "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    if should_persist or force_refresh:
        cache["as_of"] = _to_iso(today)
        cache["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_cache(cache)

    fed_balance = _build_lever_payload(_SERIES[0], series_cache[_SERIES[0].cache_key]["points"], today)
    fed_rate = _build_lever_payload(_SERIES[1], series_cache[_SERIES[1].cache_key]["points"], today)
    return {
        "as_of": _to_iso(today),
        "description": (
            "Incremental Fed liquidity cache from FRED (WALCL/DFEDTARU). "
            "Dates are observation dates; release cadence may lag publication."
        ),
        "fed_balance_sheet": fed_balance,
        "fed_rate": fed_rate,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
