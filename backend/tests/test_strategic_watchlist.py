from app.schemas.dashboard_state import LiquidityPlumbing, PolicyOptionality
from app.services.rules.dashboard_state_builder import build_dashboard_state_with_conclusion
from app.services.rules.strategic_watchlist import compute_strategic_watchlist

from .test_doctrine_regression_cases import make_snapshot


def test_trapped_or_weird_labor_inflation_becomes_warning() -> None:
    policy = PolicyOptionality(
        constraint_level="trapped",
        labor_slack_state="absent",
        labor_balance_state="weak_jobs_tight_ur",
        inflation_state="sticky_or_hot",
        fed_can_ease=False,
        fed_trapped=True,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=True,
        note="Weird-cut / low-room setup is active.",
    )
    plumbing = LiquidityPlumbing(
        state="normal",
        state_label="Normal",
        balance_sheet_expansion_not_qe=False,
    )

    result = compute_strategic_watchlist(
        policy_optionality=policy,
        liquidity_plumbing=plumbing,
        registry=[],
    )

    item_map = {item.code: item for item in result.watchlist.items}
    assert item_map["labor_inflation"].status == "warning"
    assert item_map["bank_reserves_repo_rrp"].status == "supportive"


def test_plumbing_not_qe_becomes_warning() -> None:
    policy = PolicyOptionality(
        constraint_level="limited",
        labor_slack_state="mixed",
        labor_balance_state="mixed",
        inflation_state="mixed",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=False,
        rate_cut_weirdness_active=False,
        note=None,
    )
    plumbing = LiquidityPlumbing(
        state="severe",
        state_label="Funding stress",
        balance_sheet_expansion_not_qe=True,
        caution_note="Balance-sheet support here is plumbing support, not QE.",
    )

    result = compute_strategic_watchlist(
        policy_optionality=policy,
        liquidity_plumbing=plumbing,
        registry=[],
    )

    item_map = {item.code: item for item in result.watchlist.items}
    assert item_map["bank_reserves_repo_rrp"].status == "warning"
    assert "not QE" in (item_map["bank_reserves_repo_rrp"].note or "")


def test_manual_event_items_are_present() -> None:
    policy = PolicyOptionality(
        constraint_level="free",
        labor_slack_state="present",
        labor_balance_state="clean_slack",
        inflation_state="cooling",
        fed_can_ease=True,
        fed_trapped=False,
        bad_data_is_good_enabled=True,
        rate_cut_weirdness_active=False,
        note="Fed has room to ease.",
    )
    plumbing = LiquidityPlumbing(
        state="normal",
        state_label="Normal",
        balance_sheet_expansion_not_qe=False,
    )
    registry = [
        {
            "code": "new_fed_chair",
            "label": "New Fed Chair",
            "kind": "manual_event",
            "status": "watch",
            "priority": 2,
            "note": "Await policy lean.",
        },
        {
            "code": "spacex_ipo",
            "label": "SpaceX IPO / Elon Signal",
            "kind": "manual_event",
            "status": "watch",
            "priority": 2,
            "note": "Monitor timing and demand.",
        },
    ]

    result = compute_strategic_watchlist(
        policy_optionality=policy,
        liquidity_plumbing=plumbing,
        registry=registry,
    )

    codes = [item.code for item in result.watchlist.items]
    assert "new_fed_chair" in codes
    assert "spacex_ipo" in codes
    assert "labor_inflation" in codes
    assert "bank_reserves_repo_rrp" in codes


def test_items_are_priority_sorted_and_available_in_built_state() -> None:
    snapshot = make_snapshot(
        as_of="2026-04-15T00:00:00Z",
        fed_funds_rate=4.50,
        rate_direction_medium_term="tightening",
        rate_impulse_short="stable",
        balance_sheet_direction_medium_term="contracting",
        balance_sheet_pace="contracting_slower",
        forward_pe=23.0,
        current_year_forward_pe=23.0,
        next_year_forward_pe=21.0,
        selected_year=2026,
        core_cpi_yoy=2.9,
        unemployment_rate=4.4,
        plumbing_state="severe",
        walcl_trend_1m="up",
        reserves_trend_1m="down",
        repo_trend_1m="up",
        reverse_repo_trend_1m="down",
        repo_spike_ratio=2.0,
        reverse_repo_buffer_ratio=0.3,
    )

    state, _ = build_dashboard_state_with_conclusion(snapshot)

    assert state.strategic_watchlist is not None
    codes = [item.code for item in state.strategic_watchlist.items]
    assert codes == [
        "bank_reserves_repo_rrp",
        "labor_inflation",
        "ai_ipos",
        "new_fed_chair",
        "spacex_ipo",
    ]
    item_map = {item.code: item for item in state.strategic_watchlist.items}
    assert item_map["bank_reserves_repo_rrp"].status == "warning"
    assert item_map["labor_inflation"].status in {"mixed", "warning", "supportive"}
