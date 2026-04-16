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
            {"meeting_label": "2026-03", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2026-06", "expected_end_rate_mid": 3.875},
            {"meeting_label": "2026-09", "expected_end_rate_mid": 3.625},
            {"meeting_label": "2026-12", "expected_end_rate_mid": 3.375},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("free"),
        valuation=_valuation(24.0, "Green"),
    )

    assert result.easing.expected_cut_bps_12m == 100.0
    assert result.easing.expected_cut_count_12m == 4.0
    assert result.easing.pricing_stretch_active is False


def test_late_2025_two_cuts_plus_high_valuation_is_stretch() -> None:
    snapshot = {
        "as_of": "2025-09-20",
        "source_mode": "manual_snapshot",
        "current_target_mid": 4.375,
        "meetings": [
            {"meeting_label": "2025-11", "expected_end_rate_mid": 4.125},
            {"meeting_label": "2025-12", "expected_end_rate_mid": 3.875},
        ],
    }

    result = compute_market_priced_easing(
        fedwatch_snapshot=snapshot,
        policy_optionality=_policy("limited"),
        valuation=_valuation(30.0, "Red"),
    )

    assert result.easing.expected_cut_bps_12m == 50.0
    assert result.easing.expected_cut_count_12m == 2.0
    assert result.easing.pricing_stretch_active is True


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
    )

    assert result.easing.expected_cut_bps_12m is None
    assert result.easing.pricing_stretch_active is False
    assert "unavailable" in (result.easing.note or "").lower()
