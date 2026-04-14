"""Unit tests for macro expectations pure derivations."""

from __future__ import annotations

import pytest

from app.services.macro_expectations_derivations import (
    build_regime_impact_narrative,
    compute_surprise_row,
    compute_tactical_posture_modifier,
    parse_te_number,
    repricing_delta_label,
    surprise_direction_label,
)


def test_parse_te_number() -> None:
    assert parse_te_number("3.2%") == pytest.approx(3.2)
    assert parse_te_number("1,234.5") == pytest.approx(1234.5)
    assert parse_te_number("") is None
    assert parse_te_number(None) is None


def test_surprise_direction_inflation() -> None:
    assert surprise_direction_label("CPI YoY", 0.1) == "hotter"
    assert surprise_direction_label("CPI YoY", -0.1) == "cooler"


def test_surprise_direction_growth() -> None:
    assert surprise_direction_label("Nonfarm Payrolls", 50) == "stronger"
    assert surprise_direction_label("GDP", -0.5) == "weaker"


def test_compute_surprise_missing() -> None:
    row = compute_surprise_row("CPI", None, "3.0")
    assert row["surprise"] == "—"
    assert "Insufficient" in row["impact_note"]


def test_compute_surprise_consensus_zero_no_pct_suffix() -> None:
    row = compute_surprise_row("Test", "1.0", "0")
    assert row["surprise"] == "+1.00"


def test_repricing_no_prior() -> None:
    assert repricing_delta_label(None, 0.5, None, None) == "little changed"


def test_repricing_dovish() -> None:
    assert repricing_delta_label(0.2, 0.35, 0.1, 0.1) == "more dovish"


def test_tactical_paths() -> None:
    assert (
        compute_tactical_posture_modifier(
            has_major_event_24h=True,
            unclear_consensus_near_event=True,
            latest_surprise_adverse=False,
            latest_surprise_favorable=False,
            fed_shift_hawkish=False,
            fed_shift_dovish=False,
        )
        == "mixed — event risk elevated"
    )
    assert (
        compute_tactical_posture_modifier(
            has_major_event_24h=False,
            unclear_consensus_near_event=False,
            latest_surprise_adverse=True,
            latest_surprise_favorable=False,
            fed_shift_hawkish=True,
            fed_shift_dovish=False,
        )
        == "caution after adverse surprise"
    )


def test_regime_impact_narrative() -> None:
    t = build_regime_impact_narrative(
        base_posture="Risk-on, selective accumulation",
        tactical="supportive",
        upcoming_highlight=None,
        fed_line=None,
        inflation_incomplete=True,
    )
    assert "durable framework" in t.lower()
    assert "incomplete" in t.lower()
