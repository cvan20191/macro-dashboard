"""Systemic stress zones: equity/M2 thresholds by source, card charge-off bands."""

from __future__ import annotations

import pytest

from app.schemas.indicator_snapshot import SystemicStressInput
from app.services.rules.stress import compute_stress


@pytest.mark.parametrize(
    ("ratio", "zone"),
    [
        (5.7, "Normal"),
        (5.8, "Warning"),
        (6.79, "Warning"),
        (6.8, "Extreme"),
    ],
)
def test_equity_m2_zones_fred_z1_scale(ratio: float, zone: str) -> None:
    r = compute_stress(
        SystemicStressInput(
            market_cap_m2_ratio=ratio,
            equity_m2_ratio_source="fred_z1",
        )
    )
    assert r.stress.market_cap_m2_zone == zone


@pytest.mark.parametrize(
    ("ratio", "zone"),
    [
        (1.99, "Normal"),
        (2.0, "Warning"),
        (2.99, "Warning"),
        (3.0, "Extreme"),
    ],
)
def test_equity_m2_zones_spy_fallback_scale(ratio: float, zone: str) -> None:
    r = compute_stress(
        SystemicStressInput(
            market_cap_m2_ratio=ratio,
            equity_m2_ratio_source="spy_fallback",
        )
    )
    assert r.stress.market_cap_m2_zone == zone


@pytest.mark.parametrize(
    ("rate", "zone"),
    [
        (4.5, "Normal"),
        (4.6, "Caution"),
        (5.49, "Caution"),
        (5.5, "Warning"),
        (6.0, "Warning"),
    ],
)
def test_credit_card_chargeoff_zones(rate: float, zone: str) -> None:
    r = compute_stress(SystemicStressInput(credit_card_chargeoff_rate=rate))
    assert r.stress.credit_card_chargeoff_zone == zone


def test_charge_off_warning_contributes_to_severe() -> None:
    r = compute_stress(SystemicStressInput(credit_card_chargeoff_rate=5.5))
    assert r.stress.credit_card_chargeoff_zone == "Warning"
    assert r.stress_severe is True
