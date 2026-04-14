"""
Provider base helpers — shared data containers and exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.doctrine import SourceClass


class ProviderError(Exception):
    """Raised when a provider cannot return usable data."""


@dataclass
class FetchResult:
    """Holds a single fetched value plus provenance."""
    value: float | None
    observed_at: str | None          # ISO date string of the observation
    series: list[tuple[str, float]]  # [(date_str, value), ...] recent window
    provider: str
    series_id: str
    series_name: str
    frequency: str = "unknown"
    note: str | None = None
    status: str = "fresh"            # fresh | stale | missing | error | fallback
    source_class: SourceClass | None = None
    confidence_weight: float | None = None
    release_date: str | None = None
    last_revised_at: str | None = None
    staleness_bucket: str | None = None
    extra: dict = field(default_factory=dict)
