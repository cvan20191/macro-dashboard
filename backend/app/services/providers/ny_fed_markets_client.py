"""
NY Fed Markets Data API (public).

Docs: https://markets.newyorkfed.org/static/docs/markets-api.html
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)

_BASE = "https://markets.newyorkfed.org/api"


def fetch_latest_repo(timeout: int = 20) -> dict[str, Any]:
    url = f"{_BASE}/rp/results/latest.json"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise ProviderError(f"NY Fed repo HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ProviderError(f"NY Fed repo request failed: {exc}") from exc


def fetch_latest_reverse_repo(timeout: int = 20) -> dict[str, Any]:
    url = f"{_BASE}/rp/reverserepo/results/latest.json"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise ProviderError(f"NY Fed reverse repo HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ProviderError(f"NY Fed reverse repo request failed: {exc}") from exc


def normalize_repo_payload(raw: dict[str, Any], operation_type: str) -> dict[str, Any]:
    """Best-effort flatten — API shape varies; keep raw_note for UI."""
    return {
        "operation_date": _pick(raw, "operationDate", "date", "tradeDate"),
        "operation_type": operation_type,
        "accepted_amount": _pick(raw, "totalAccepted", "acceptedAmount", "accepted"),
        "submitted_amount": _pick(raw, "totalSubmitted", "submittedAmount", "submitted"),
        "rate": _pick(raw, "weightedAverageRate", "rate", "avgRate"),
        "maturity": _pick(raw, "maturity", "term", "operationMaturity"),
        "source_timestamp": _pick(raw, "time", "asOf", "lastUpdated"),
        "raw_note": None,
    }


def _pick(raw: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = raw.get(k)
        if v is not None and str(v).strip() != "":
            return str(v)
    return None
