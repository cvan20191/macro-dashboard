from datetime import date

from app.schemas.dashboard_state import PolicyOptionality, Valuation
from app.services.rules.market_priced_easing import compute_market_priced_easing


def _policy(
    constraint_level: str,
    *,
    trapped: bool = False,
    weird: bool = False,
) -> PolicyOptionality:
    return PolicyOptionality(
        constraint_level=constraint_level,
        labor_slack_state="mixed",
        labor_balance_state="mixed",
        inflation_state="mixed",
        fed_can_ease=constraint_level in {"free", "limited"},
        fed_trapped=trapped,
        bad_data_is_good_enabled=constraint_level == "free",
        rate_cut_weirdness_active=weird,
        note=None,
    )


def _valuation(forward_pe: float, zone: str) -> Valuation:
    return Valuation(
        forward_pe=forward_pe,
        zone=zone,
        zone_label=zone,
        signal_mode="actionable",
    )


def test_free_backdrop_does_not_mark_100bps_as_stretch_by_itself() -> None:
    snapshot = {
        "as_of": "2026-01-10",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2026-03", "meeting_date": "2026-03-18", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2026-06", "meeting_date": "2026-06-17", "expected_end_rate_mid": 3.875},
            {"meeting_label": "2026-09", "meeting_date": "2026-09-16", "expected_end_rate_mid": 3.625},
            {"meeting_label": "2026-12", "meeting_date": "2026-12-09", "expected_end_rate_mid": 3.375},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("free"),
        valuation=_valuation(24.0, "Green"),
        current_as_of=date(2026, 1, 12),
    )

    assert result.easing.expected_cut_bps_12m == 100.0
    assert result.easing.expected_cut_count_12m == 4.0
    assert result.easing.pricing_stretch_active is False


def test_unsorted_meetings_still_compute_correct_12m_cuts() -> None:
    snapshot = {
        "as_of": "2025-09-30",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2026-12", "meeting_date": "2026-12-09", "expected_end_rate_mid": 3.375},
            {"meeting_label": "2025-11", "meeting_date": "2025-11-06", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2026-06", "meeting_date": "2026-06-17", "expected_end_rate_mid": 3.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
        current_as_of=date(2025, 10, 2),
    )

    assert result.easing.expected_cut_bps_12m == 50.0
    assert result.easing.expected_cut_count_12m == 2.0
    assert result.easing.meetings[-1].meeting_date == "2026-12-09"


def test_far_out_meetings_do_not_distort_12m_read() -> None:
    snapshot = {
        "as_of": "2025-09-30",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2025-11", "meeting_date": "2025-11-06", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2025-12", "meeting_date": "2025-12-17", "expected_end_rate_mid": 3.875},
            {"meeting_label": "2027-01", "meeting_date": "2027-01-27", "expected_end_rate_mid": 2.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
        current_as_of=date(2025, 10, 2),
    )

    assert result.easing.expected_cut_bps_12m == 50.0
    assert result.easing.expected_cut_count_12m == 2.0


def test_missing_meeting_dates_make_read_descriptive_only() -> None:
    snapshot = {
        "as_of": "2025-09-30",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2025-11", "meeting_date": None, "expected_end_rate_mid": 4.125},
            {"meeting_label": "2025-12", "meeting_date": None, "expected_end_rate_mid": 3.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
        current_as_of=date(2025, 10, 2),
    )

    assert result.easing.expected_cut_bps_12m is None
    assert result.easing.hard_actionable is False
    assert "meeting dates" in (result.easing.note or "").lower()


def test_fresh_snapshot_can_be_hard_actionable() -> None:
    snapshot = {
        "as_of": "2025-09-20",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2025-11", "meeting_date": "2025-11-06", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2025-12", "meeting_date": "2025-12-17", "expected_end_rate_mid": 3.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
        current_as_of=date(2025, 9, 22),
    )

    assert result.easing.expected_cut_bps_12m == 50.0
    assert result.easing.expected_cut_count_12m == 2.0
    assert result.easing.pricing_stretch_active is True
    assert result.easing.freshness_status == "fresh"
    assert result.easing.hard_actionable is True


def test_stale_snapshot_is_descriptive_only() -> None:
    snapshot = {
        "as_of": "2025-09-01",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2025-11", "meeting_date": "2025-11-06", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2025-12", "meeting_date": "2025-12-17", "expected_end_rate_mid": 3.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
        current_as_of=date(2025, 10, 2),
    )

    assert result.easing.pricing_stretch_active is True
    assert result.easing.freshness_status == "stale"
    assert result.easing.hard_actionable is False
    assert "descriptive only" in (result.easing.note or "")


def test_unavailable_snapshot_stays_nonfatal() -> None:
    snapshot = {
        "as_of": None,
        "source_mode": "manual_snapshot",
        "current_target_mid": None,
        "meetings": [],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("unknown"),
        valuation=_valuation(24.0, "Green"),
        current_as_of=date(2025, 10, 2),
    )

    assert result.easing.expected_cut_bps_12m is None
    assert result.easing.pricing_stretch_active is False
    assert result.easing.freshness_status == "unavailable"
    assert result.easing.hard_actionable is False
    assert "unavailable" in (result.easing.note or "").lower()
