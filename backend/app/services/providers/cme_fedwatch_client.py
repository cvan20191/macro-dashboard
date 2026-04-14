"""
CME FedWatch end-of-day API (OAuth2 client credentials).

Falls back to manual JSON when credentials are not configured.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)

_TOKEN_CACHE = Path(__file__).resolve().parents[3] / ".cache" / "cme_fedwatch_token.json"


def is_api_configured() -> bool:
    return bool(
        settings.cme_fedwatch_client_id
        and settings.cme_fedwatch_client_secret
        and settings.cme_fedwatch_token_url
    )


def _load_cached_token() -> tuple[str, float] | None:
    if not _TOKEN_CACHE.is_file():
        return None
    try:
        data = json.loads(_TOKEN_CACHE.read_text(encoding="utf-8"))
        token = data.get("access_token")
        exp = float(data.get("expires_at", 0))
        if token and time.time() < exp - 60:
            return str(token), exp
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _save_token(token: str, expires_in: int) -> None:
    _TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token,
        "expires_at": time.time() + max(expires_in, 60),
    }
    _TOKEN_CACHE.write_text(json.dumps(payload), encoding="utf-8")


def get_bearer_token(timeout: int = 20) -> str:
    cached = _load_cached_token()
    if cached:
        return cached[0]
    if not is_api_configured():
        raise ProviderError("CME FedWatch OAuth not configured")
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            settings.cme_fedwatch_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.cme_fedwatch_client_id,
                "client_secret": settings.cme_fedwatch_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        body = resp.json()
    token = body.get("access_token")
    if not token:
        raise ProviderError("CME token response missing access_token")
    expires_in = int(body.get("expires_in", 3600))
    _save_token(str(token), expires_in)
    return str(token)


def _cme_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "CME-Application-Name": settings.cme_application_name,
        "CME-Application-Vendor": settings.cme_application_vendor,
        "CME-Application-Version": settings.cme_application_version,
        "CME-Request-ID": settings.cme_request_id_prefix + str(int(time.time() * 1000)),
        "User-Agent": settings.cme_user_agent,
    }


def fetch_forecasts_raw(timeout: int = 30) -> list[dict[str, Any]]:
    if not is_api_configured():
        raise ProviderError("CME FedWatch not configured")
    token = get_bearer_token(timeout=timeout)
    base = settings.cme_fedwatch_api_base.rstrip("/")
    url = f"{base}/forecasts"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=_cme_headers(token))
        resp.raise_for_status()
        data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        return inner if isinstance(inner, list) else []
    return []


def normalize_probability(p: float | int) -> float:
    x = float(p)
    if x > 1.0:
        return min(x / 100.0, 1.0)
    return max(0.0, min(1.0, x))


def normalize_forecast_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Single meeting forecast → normalized fields for FedPricingMeetingNormalized."""
    meeting = str(raw.get("meetingDt") or raw.get("meeting_date") or "")
    reporting = str(raw.get("reportingDt") or raw.get("source_timestamp") or "")
    ranges_raw = raw.get("rateRange") or raw.get("rate_ranges") or []
    ranges: list[dict[str, Any]] = []
    if isinstance(ranges_raw, list):
        for rr in ranges_raw:
            if not isinstance(rr, dict):
                continue
            lo = rr.get("lowerRt") or rr.get("lower_rate_bps")
            hi = rr.get("upperRt") or rr.get("upper_rate_bps")
            pr = rr.get("probability")
            if lo is None or hi is None or pr is None:
                continue
            ranges.append({
                "lower_rate_bps": int(lo),
                "upper_rate_bps": int(hi),
                "probability": normalize_probability(float(pr)),
            })
    return {
        "meeting_date": meeting,
        "source_timestamp": reporting,
        "rate_ranges": ranges,
    }


def bucket_probabilities(
    rate_ranges: list[dict[str, Any]],
    current_target_upper_bps: int | None,
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """
    Assign each range to hold / cut_25 / cut_50 / hike_25 by midpoint vs current upper bound.
    Returns (hold, cut25, cut50, hike25, implied_mid).
    """
    if not rate_ranges or current_target_upper_bps is None:
        return None, None, None, None, None
    cur = float(current_target_upper_bps)
    hold = cut25 = cut50 = hike25 = 0.0
    implied_num = 0.0
    implied_den = 0.0
    for rr in rate_ranges:
        lo = float(rr["lower_rate_bps"])
        hi = float(rr["upper_rate_bps"])
        p = float(rr["probability"])
        mid = (lo + hi) / 2.0
        implied_num += mid * p
        implied_den += p
        d = mid - cur
        if abs(d) < 15:
            hold += p
        elif d <= -35:
            cut50 += p
        elif d < -15:
            cut25 += p
        elif d > 15:
            hike25 += p
        else:
            hold += p
    implied = implied_num / implied_den if implied_den > 0 else None
    return hold, cut25, cut50, hike25, implied
