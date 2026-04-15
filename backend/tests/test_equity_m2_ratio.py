"""Equity/M2 ratio: precedence, Z.1 unit conversion, and normalizer wiring."""

from __future__ import annotations

import json

import pytest

from app.services.ingestion import normalizer
from app.services.ingestion.normalizer import (
    build_indicator_snapshot,
    compute_equity_m2_views,
    equity_m2_ratio_core,
)
from app.services.providers.base import FetchResult


def _fred_result(
    key_val: float,
    observed_at: str = "2025-10-01",
    series_id: str = "X",
    name: str = "x",
    status: str = "fresh",
) -> FetchResult:
    return FetchResult(
        value=key_val,
        observed_at=observed_at,
        series=[],
        provider="FRED",
        series_id=series_id,
        series_name=name,
        status=status,
    )


def test_equity_m2_manual_over_z1_and_spy() -> None:
    m2 = 10_000.0
    z1_m = 40_000_000.0  # 40_000 B if used
    spy = 400.0
    r_manual, src = equity_m2_ratio_core(50_000.0, z1_m, m2, spy)
    assert src == "manual_override"
    assert r_manual == 5.0

    r_z1, src_z1 = equity_m2_ratio_core(None, z1_m, m2, spy)
    assert src_z1 == "fred_z1"
    assert r_z1 == round((z1_m / 1000.0) / m2, 3)

    r_spy, src_spy = equity_m2_ratio_core(None, None, m2, spy)
    assert src_spy == "spy_fallback"
    assert r_spy is not None


def test_bogz1_millions_to_billions_div_m2() -> None:
    """BOGZ1LM893064105Q is millions USD; divide by 1000 for billions."""
    z1_millions = 111_355_401.0
    m2_billions = 22_695.9
    ratio, src = equity_m2_ratio_core(None, z1_millions, m2_billions, 500.0)
    assert src == "fred_z1"
    equity_b = z1_millions / 1000.0
    assert ratio == round(equity_b / m2_billions, 3)


def test_build_snapshot_manual_file_precedence(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    manual_path = tmp_path / "manual_equity_m2_numerator.json"
    manual_path.write_text(
        json.dumps(
            {
                "equity_value_billions": 60_000.0,
                "as_of": "2025-12-31",
                "source": "fixture",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "_MANUAL_EQUITY_M2_PATH", manual_path)

    raw = {
        "m2": _fred_result(10_000.0, series_id="WM2NS", name="M2"),
        "equity_market_value_z1": _fred_result(
            999_999_999.0,
            observed_at="2025-09-30",
            series_id="BOGZ1LM893064105Q",
            name="Z.1",
        ),
        "sp500_etf": FetchResult(
            value=100.0,
            observed_at="2026-01-15",
            series=[],
            provider="Yahoo",
            series_id="SPY",
            series_name="SPY",
            status="fresh",
        ),
    }
    freshness = {"m2": "fresh", "equity_market_value_z1": "stale", "sp500_etf": "fresh"}
    snap = build_indicator_snapshot(raw, freshness, [], "fresh")
    ss = snap.systemic_stress
    assert ss.equity_m2_ratio_source == "manual_override"
    assert ss.market_cap_m2_ratio == 6.0
    assert ss.speaker_market_cap_m2_ratio == 6.0
    assert ss.speaker_market_cap_m2_source == "manual_override"
    assert ss.corporate_equities_m2_ratio == round((999_999_999.0 / 1000.0) / 10_000.0, 3)
    assert ss.corporate_equities_m2_source == "fred_z1"
    assert ss.equity_m2_numerator_as_of == "2025-12-31"
    assert ss.equity_m2_numerator_freshness == "manual"
    assert ss.corporate_equities_m2_numerator_as_of == "2025-09-30"
    assert ss.corporate_equities_m2_numerator_freshness == "stale"


def test_build_snapshot_z1_metadata_uses_fred_freshness(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No manual file: Z.1 observed_at + equity series freshness."""
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(normalizer, "_MANUAL_EQUITY_M2_PATH", missing)

    raw = {
        "m2": _fred_result(22_695.9, observed_at="2026-03-02", series_id="WM2NS", name="M2"),
        "equity_market_value_z1": _fred_result(
            111_355_401.0,
            observed_at="2025-10-01",
            series_id="BOGZ1LM893064105Q",
            name="Z.1 equities",
            status="stale",
        ),
    }
    freshness = {"m2": "fresh", "equity_market_value_z1": "stale"}
    snap = build_indicator_snapshot(raw, freshness, [], "fresh")
    ss = snap.systemic_stress
    assert ss.equity_m2_ratio_source == "fred_z1"
    assert ss.market_cap_m2_ratio == ss.corporate_equities_m2_ratio
    assert ss.corporate_equities_m2_source == "fred_z1"
    assert ss.speaker_market_cap_m2_ratio is None
    assert ss.equity_m2_numerator_as_of == "2025-10-01"
    assert ss.equity_m2_numerator_freshness == "stale"
    assert ss.corporate_equities_m2_numerator_as_of == "2025-10-01"
    assert ss.corporate_equities_m2_numerator_freshness == "stale"


def test_compute_equity_m2_views_returns_separated_paths() -> None:
    views = compute_equity_m2_views(
        manual_billions=45_000.0,
        z1_millions=5_400_000.0,
        m2_billions=20_000.0,
        sp500_price=600.0,
    )

    assert views["speaker_ratio"] == 2.25
    assert views["speaker_source"] == "manual_override"
    assert views["z1_ratio"] == 0.27
    assert views["spy_ratio"] is not None
    assert views["active_ratio"] == 2.25
    assert views["active_source"] == "manual_override"
