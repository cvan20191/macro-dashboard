from __future__ import annotations

import asyncio
import os

os.environ.setdefault("OPENAI_API_KEY", "test")

from app.config import settings
from app.services.ingestion.live_snapshot_service import get_live_snapshot
from app.services.ingestion.normalizer import build_indicator_snapshot
from app.services.providers.base import FetchResult


def _result(
    value: float | None,
    observed_at: str | None,
    series: list[tuple[str, float]],
    *,
    provider: str = "FRED",
    series_id: str,
    series_name: str,
    frequency: str = "daily",
    extra: dict | None = None,
) -> FetchResult:
    return FetchResult(
        value=value,
        observed_at=observed_at,
        series=series,
        provider=provider,
        series_id=series_id,
        series_name=series_name,
        frequency=frequency,
        status="fresh",
        extra=extra or {},
    )


def _live_raw_fixture() -> dict[str, FetchResult]:
    return {
        "fed_funds_rate": _result(
            4.5,
            "2026-04-15",
            [
                ("2026-03-01", 4.8),
                ("2026-03-15", 4.7),
                ("2026-04-01", 4.6),
                ("2026-04-15", 4.5),
            ],
            series_id="DFEDTARU",
            series_name="Fed Funds Upper Bound",
        ),
        "balance_sheet": _result(
            6_900_000.0,
            "2026-04-15",
            [
                ("2026-03-01", 6_850_000.0),
                ("2026-04-15", 6_900_000.0),
            ],
            series_id="WALCL",
            series_name="Fed Balance Sheet",
            frequency="weekly",
        ),
        "forward_pe": _result(
            23.0,
            "2026-04-15",
            [],
            provider="FMP",
            series_id="MAG7_BASKET",
            series_name="Mag 7 Forward P/E Basket",
            extra={
                "pe_basis": "forward",
                "metric_name": "Mag 7 Forward P/E",
                "object_label": "Mag 7 Basket",
                "provider": "fmp",
                "coverage_count": 7,
                "coverage_ratio": 1.0,
                "signal_mode": "actionable",
                "basis_confidence": 1.0,
                "estimate_as_of": "2026-04-15",
                "horizon_label": "speaker_fye_proximity_current_year",
                "horizon_coverage_ratio": 1.0,
                "current_year_forward_pe": 23.0,
                "next_year_forward_pe": 21.0,
                "selected_year": 2026,
                "constituents": [],
            },
        ),
        "core_cpi": _result(
            320.0,
            "2026-04-15",
            [
                ("2025-03-01", 300.0),
                ("2026-03-01", 319.0),
                ("2026-04-15", 320.0),
            ],
            series_id="CPILFESL",
            series_name="Core CPI",
            frequency="monthly",
        ),
        "pmi_manufacturing": _result(
            51.0,
            "2026-04-15",
            [],
            provider="stub",
            series_id="PMI_MANUFACTURING",
            series_name="pmi_manufacturing",
            frequency="monthly",
        ),
        "pmi_services": _result(
            52.0,
            "2026-04-15",
            [],
            provider="stub",
            series_id="PMI_SERVICES",
            series_name="pmi_services",
            frequency="monthly",
        ),
    }


class _DummyCache:
    def get(self) -> dict | None:
        return None

    def load_from_disk(self) -> dict | None:
        return None

    def clear(self) -> None:
        return None

    def set(self, payload: dict) -> None:
        _ = payload

    def save_to_disk(self, payload: dict) -> None:
        _ = payload


def test_build_indicator_snapshot_does_not_infer_fed_put_from_falling_rates() -> None:
    snapshot = build_indicator_snapshot(_live_raw_fixture(), {}, [], "fresh")

    assert snapshot.liquidity.rate_direction_medium_term == "easing"
    assert snapshot.liquidity.rate_impulse_short == "confirming_easing"
    assert snapshot.policy_support.fed_put is False
    assert snapshot.policy_support.treasury_put is False
    assert snapshot.policy_support.political_put is False


def test_get_live_snapshot_ignores_default_policy_support_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "default_fed_put", True)
    monkeypatch.setattr(settings, "default_treasury_put", True)
    monkeypatch.setattr(settings, "default_political_put", True)
    monkeypatch.setattr(
        "app.services.ingestion.live_snapshot_service._run_full_fetch",
        lambda *args, **kwargs: _live_raw_fixture(),
    )
    monkeypatch.setattr(
        "app.services.ingestion.live_snapshot_service.get_snapshot_cache",
        lambda: _DummyCache(),
    )

    response = asyncio.run(get_live_snapshot(force_refresh=True))

    assert response.snapshot.policy_support.fed_put is False
    assert response.snapshot.policy_support.treasury_put is False
    assert response.snapshot.policy_support.political_put is False
