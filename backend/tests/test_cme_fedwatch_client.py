from __future__ import annotations

import pytest

from app.services.providers import cme_fedwatch_client as cme


def test_normalize_probability_percent() -> None:
    assert cme.normalize_probability(45) == pytest.approx(0.45)
    assert cme.normalize_probability(0.45) == pytest.approx(0.45)


def test_bucket_probabilities() -> None:
    ranges = [
        {"lower_rate_bps": 400, "upper_rate_bps": 425, "probability": 0.5},
        {"lower_rate_bps": 375, "upper_rate_bps": 400, "probability": 0.3},
        {"lower_rate_bps": 425, "upper_rate_bps": 450, "probability": 0.2},
    ]
    h, c25, c50, h25, implied = cme.bucket_probabilities(ranges, current_target_upper_bps=425)
    assert h is not None and h > 0
    assert implied is not None


def test_normalize_forecast_entry() -> None:
    raw = {
        "meetingDt": "2026-05-07",
        "reportingDt": "2026-04-07",
        "rateRange": [
            {"lowerRt": 400, "upperRt": 425, "probability": 60},
        ],
    }
    n = cme.normalize_forecast_entry(raw)
    assert n["meeting_date"] == "2026-05-07"
    assert len(n["rate_ranges"]) == 1
    assert n["rate_ranges"][0]["probability"] == pytest.approx(0.6)
