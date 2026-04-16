from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.schemas.dashboard_state import (
    MarketEasingExpectations,
    MarketPricedCutPoint,
    PolicyOptionality,
    Valuation,
)

_MAX_HARD_ACTIONABLE_AGE_DAYS = 7
_TWELVE_MONTH_HORIZON_DAYS = 370


@dataclass(frozen=True)
class MarketPricedEasingResult:
    easing: MarketEasingExpectations


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None

    raw = str(value)[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_market_priced_easing(
    *,
    fedwatch_snapshot: dict,
    policy_optionality: PolicyOptionality | None,
    valuation: Valuation | None,
    current_as_of: date | None,
) -> MarketPricedEasingResult:
    current_target_mid = _to_float(fedwatch_snapshot.get("current_target_mid"))
    source_mode = str(fedwatch_snapshot.get("source_mode") or "manual_snapshot")
    as_of = fedwatch_snapshot.get("as_of")
    snapshot_as_of = _to_date(as_of)

    data_age_days: int | None = None
    freshness_status = "unknown"
    if snapshot_as_of is None:
        freshness_status = "unavailable"
    elif current_as_of is None:
        freshness_status = "unknown"
    else:
        data_age_days = (current_as_of - snapshot_as_of).days
        if 0 <= data_age_days <= _MAX_HARD_ACTIONABLE_AGE_DAYS:
            freshness_status = "fresh"
        else:
            freshness_status = "stale"

    raw_meetings = fedwatch_snapshot.get("meetings", [])
    parsed_meetings: list[tuple[date | None, MarketPricedCutPoint]] = []

    for row in raw_meetings:
        meeting_label = str(row.get("meeting_label") or "")
        meeting_date = _to_date(row.get("meeting_date"))
        expected_end_rate_mid = _to_float(row.get("expected_end_rate_mid"))

        cumulative_cut_bps = None
        if current_target_mid is not None and expected_end_rate_mid is not None:
            cumulative_cut_bps = max(
                0.0,
                round((current_target_mid - expected_end_rate_mid) * 100.0, 1),
            )

        parsed_meetings.append(
            (
                meeting_date,
                MarketPricedCutPoint(
                    meeting_label=meeting_label,
                    meeting_date=row.get("meeting_date"),
                    expected_end_rate_mid=expected_end_rate_mid,
                    cumulative_cut_bps=cumulative_cut_bps,
                ),
            )
        )

    parsed_meetings.sort(key=lambda item: (item[0] is None, item[0] or date.max))
    meeting_points = [point for _, point in parsed_meetings]

    expected_cut_bps_12m: float | None = None
    if current_as_of is not None:
        horizon_candidates = [
            point
            for meeting_date, point in parsed_meetings
            if meeting_date is not None
            and 0 <= (meeting_date - current_as_of).days <= _TWELVE_MONTH_HORIZON_DAYS
        ]
        if horizon_candidates:
            expected_cut_bps_12m = horizon_candidates[-1].cumulative_cut_bps

    expected_cut_count_12m = None
    if expected_cut_bps_12m is not None:
        expected_cut_count_12m = round(expected_cut_bps_12m / 25.0, 1)

    constraint_level = (
        policy_optionality.constraint_level if policy_optionality is not None else "unknown"
    )
    free_backdrop = constraint_level == "free"

    valuation_stretched = False
    if valuation is not None:
        zone = (valuation.zone or "").lower()
        valuation_stretched = zone == "red" or (
            valuation.forward_pe is not None and valuation.forward_pe >= 30.0
        )

    pricing_stretch_active = False
    if expected_cut_bps_12m is not None:
        if expected_cut_bps_12m >= 50.0 and constraint_level in {"limited", "trapped", "unknown"}:
            pricing_stretch_active = True
        if expected_cut_bps_12m >= 50.0 and valuation_stretched:
            pricing_stretch_active = True
        if expected_cut_bps_12m >= 75.0 and not free_backdrop:
            pricing_stretch_active = True

    dated_meetings_available = any(meeting_date is not None for meeting_date, _ in parsed_meetings)
    hard_actionable = (
        pricing_stretch_active
        and freshness_status == "fresh"
        and dated_meetings_available
        and expected_cut_bps_12m is not None
    )

    if expected_cut_bps_12m is None and not dated_meetings_available:
        note = (
            "Market-priced easing snapshot lacks machine-readable meeting dates, "
            "so the 12-month read is unavailable."
        )
    elif expected_cut_bps_12m is None:
        note = "Market-priced easing snapshot is unavailable."
    elif pricing_stretch_active and not hard_actionable:
        note = (
            f"The market is pricing about {expected_cut_count_12m} cuts / "
            f"{expected_cut_bps_12m:.0f} bps, but the FedWatch read is not "
            "hard-actionable, so this is descriptive only."
        )
    elif pricing_stretch_active:
        note = (
            f"The market is pricing about {expected_cut_count_12m} cuts / "
            f"{expected_cut_bps_12m:.0f} bps, which looks stretched relative "
            "to the current backdrop."
        )
    else:
        note = (
            f"The market is pricing about {expected_cut_count_12m} cuts / "
            f"{expected_cut_bps_12m:.0f} bps over the next 12 months."
        )

    return MarketPricedEasingResult(
        easing=MarketEasingExpectations(
            source_mode=source_mode,
            as_of=as_of,
            current_target_mid=current_target_mid,
            expected_cut_bps_12m=expected_cut_bps_12m,
            expected_cut_count_12m=expected_cut_count_12m,
            pricing_stretch_active=pricing_stretch_active,
            freshness_status=freshness_status,
            data_age_days=data_age_days,
            hard_actionable=hard_actionable,
            note=note,
            meetings=meeting_points,
        )
    )
