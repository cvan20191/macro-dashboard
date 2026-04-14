from __future__ import annotations

from datetime import datetime, timezone

from app.services.providers.fmp_client import _get_price, select_speaker_forward_estimate


def test_get_price_does_not_use_last_annual_dividend() -> None:
    assert _get_price({"lastAnnualDividend": 4.25}) is None


def test_selects_current_fy_when_not_near_year_end() -> None:
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    estimates = [
        {"date": "2026-12-31", "epsAvg": 10.0},
        {"date": "2027-12-31", "epsAvg": 12.0},
    ]

    selected_eps, selected_date, horizon_label, fy1_eps, fy2_eps = select_speaker_forward_estimate(
        estimates,
        now=now,
        switch_days=100,
    )

    assert selected_eps == 10.0
    assert selected_date is not None
    assert selected_date.strftime("%Y-%m-%d") == "2026-12-31"
    assert horizon_label == "current_fy"
    assert fy1_eps == 10.0
    assert fy2_eps == 12.0


def test_selects_next_fy_near_year_end() -> None:
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    estimates = [
        {"date": "2026-12-31", "epsAvg": 10.0},
        {"date": "2027-12-31", "epsAvg": 12.0},
    ]

    selected_eps, selected_date, horizon_label, fy1_eps, fy2_eps = select_speaker_forward_estimate(
        estimates,
        now=now,
        switch_days=100,
    )

    assert selected_eps == 12.0
    assert selected_date is not None
    assert selected_date.strftime("%Y-%m-%d") == "2027-12-31"
    assert horizon_label == "next_fy"
    assert fy1_eps == 10.0
    assert fy2_eps == 12.0
