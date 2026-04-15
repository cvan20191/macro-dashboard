from __future__ import annotations

from datetime import date, timedelta

from app.schemas.indicator_snapshot import PlumbingInput
from app.services.ingestion.normalizer import build_indicator_snapshot
from app.services.providers.base import FetchResult
from app.services.rules.liquidity_plumbing import compute_liquidity_plumbing


def _fred_result(
    value: float,
    observed_at: str,
    series: list[tuple[str, float]],
    *,
    series_id: str,
    name: str,
) -> FetchResult:
    return FetchResult(
        value=value,
        observed_at=observed_at,
        series=series,
        provider="FRED",
        series_id=series_id,
        series_name=name,
        frequency="weekly",
        status="fresh",
    )


def test_plumbing_stress_marks_walcl_uptick_as_not_qe() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=2800.0,
            reserves_trend_1m="down",
            reserves_buffer_ratio=0.96,
            repo_total=150.0,
            repo_trend_1m="up",
            repo_spike_ratio=2.75,
            reverse_repo_total=90.0,
            reverse_repo_trend_1m="down",
            reverse_repo_buffer_ratio=0.22,
            walcl_trend_1m="up",
        )
    )

    assert result.state == "severe"
    assert result.balance_sheet_expansion_not_qe is True
    assert result.plumbing.state == "severe"
    assert "not QE" in (result.plumbing.caution_note or "")


def test_plumbing_caution_when_repo_rises_and_reserves_fall() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=2950.0,
            reserves_trend_1m="down",
            reserves_buffer_ratio=0.99,
            repo_total=45.0,
            repo_trend_1m="up",
            repo_spike_ratio=1.25,
            reverse_repo_total=180.0,
            reverse_repo_trend_1m="flat",
            reverse_repo_buffer_ratio=0.80,
            walcl_trend_1m="flat",
        )
    )

    assert result.state == "elevated"
    assert result.balance_sheet_expansion_not_qe is False


def test_plumbing_normal_when_buffers_are_stable() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=3100.0,
            reserves_trend_1m="flat",
            reserves_buffer_ratio=1.01,
            repo_total=5.0,
            repo_trend_1m="flat",
            repo_spike_ratio=0.90,
            reverse_repo_total=250.0,
            reverse_repo_trend_1m="flat",
            reverse_repo_buffer_ratio=0.95,
            walcl_trend_1m="down",
        )
    )

    assert result.state == "normal"
    assert result.balance_sheet_expansion_not_qe is False


def test_plumbing_unknown_when_inputs_missing() -> None:
    result = compute_liquidity_plumbing(PlumbingInput())

    assert result.state == "unknown"
    assert result.plumbing.state == "unknown"


def test_weekly_reserve_balances_drive_live_plumbing_state() -> None:
    raw = {
        "balance_sheet": _fred_result(
            6_920_000.0,
            "2026-04-08",
            [
                ("2026-03-11", 6_860_000.0),
                ("2026-03-18", 6_875_000.0),
                ("2026-03-25", 6_890_000.0),
                ("2026-04-01", 6_905_000.0),
                ("2026-04-08", 6_920_000.0),
            ],
            series_id="WALCL",
            name="Fed Balance Sheet",
        ),
        "total_reserves": _fred_result(
            2_780_000.0,
            "2026-04-08",
            [
                ("2026-02-25", 3_050_000.0),
                ("2026-03-04", 3_020_000.0),
                ("2026-03-11", 2_980_000.0),
                ("2026-03-18", 2_920_000.0),
                ("2026-03-25", 2_880_000.0),
                ("2026-04-01", 2_830_000.0),
                ("2026-04-08", 2_780_000.0),
            ],
            series_id="WRESBAL",
            name="Reserve Balances",
        ),
        "repo_total": _fred_result(
            80.0,
            "2026-04-08",
            [
                ("2026-03-11", 38.0),
                ("2026-03-16", 44.0),
                ("2026-03-20", 48.0),
                ("2026-03-24", 54.0),
                ("2026-03-28", 60.0),
                ("2026-04-01", 68.0),
                ("2026-04-05", 74.0),
                ("2026-04-08", 80.0),
            ],
            series_id="RPTTLD",
            name="Repo Operations",
        ),
        "reverse_repo_total": _fred_result(
            160.0,
            "2026-04-08",
            [
                ("2026-03-11", 266.0),
                ("2026-03-16", 244.0),
                ("2026-03-20", 228.0),
                ("2026-03-24", 214.0),
                ("2026-03-28", 200.0),
                ("2026-04-01", 186.0),
                ("2026-04-05", 172.0),
                ("2026-04-08", 160.0),
            ],
            series_id="RRPTTLD",
            name="Reverse Repo Operations",
        ),
    }

    snapshot = build_indicator_snapshot(raw, {}, [], "fresh")
    result = compute_liquidity_plumbing(snapshot.plumbing)

    assert snapshot.plumbing.reserves_trend_1m == "down"
    assert snapshot.plumbing.reserves_buffer_ratio is not None
    assert snapshot.plumbing.reserves_buffer_ratio < 1.0
    assert result.state == "elevated"
    assert result.balance_sheet_expansion_not_qe is True


def test_weekly_reserve_buffer_ratio_uses_weekly_history_window() -> None:
    end_date = date(2026, 4, 8)
    reserve_series: list[tuple[str, float]] = []
    for weeks_ago in range(29, -1, -1):
        obs_date = end_date - timedelta(days=weeks_ago * 7)
        value = 2_700_000.0 if weeks_ago == 0 else 3_000_000.0
        reserve_series.append((obs_date.isoformat(), value))

    raw = {
        "total_reserves": _fred_result(
            2_700_000.0,
            end_date.isoformat(),
            reserve_series,
            series_id="WRESBAL",
            name="Reserve Balances",
        ),
    }

    snapshot = build_indicator_snapshot(raw, {}, [], "fresh")

    assert snapshot.plumbing.reserves_buffer_ratio == 0.9
