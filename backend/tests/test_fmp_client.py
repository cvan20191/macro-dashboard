from __future__ import annotations

from app.services.providers.fmp_client import _get_price, calendarized_forward_eps


def test_get_price_does_not_use_last_annual_dividend() -> None:
    assert _get_price({"lastAnnualDividend": 4.25}) is None


def test_calendarized_forward_eps_blends_fy1_and_fy2() -> None:
    eps = calendarized_forward_eps(10.0, 14.0, 182)
    assert eps is not None
    assert round(eps, 2) == 12.01


def test_calendarized_forward_eps_falls_back_to_fy1() -> None:
    assert calendarized_forward_eps(8.5, None, None) == 8.5
