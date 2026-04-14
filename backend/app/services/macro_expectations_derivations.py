"""Pure functions for macro expectations — unit-tested without HTTP."""

from __future__ import annotations


def parse_te_number(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).replace("%", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _is_inflation_event(name: str) -> bool:
    n = name.lower()
    return any(
        k in n
        for k in (
            "cpi",
            "pce",
            "inflation",
            "consumer price",
            "producer price",
            "ppi",
        )
    )


def surprise_direction_label(event_name: str, surprise: float) -> str:
    if surprise == 0:
        return "in line"
    if _is_inflation_event(event_name):
        return "hotter" if surprise > 0 else "cooler"
    return "stronger" if surprise > 0 else "weaker"


def build_impact_note(event_name: str, direction: str, surprise_mag: float) -> str:
    """Template-based one-liner; no LLM."""
    if direction in ("—", "in line") or surprise_mag == 0:
        return f"In-line {event_name} leaves the current policy path largely intact."
    inf = _is_inflation_event(event_name)
    if inf:
        if direction == "hotter":
            return (
                f"Hotter-than-expected {event_name} reduced rate-cut odds and "
                "modestly weakened the inflation backdrop."
            )
        return (
            f"Cooler-than-expected {event_name} improved rate-cut odds and "
            "modestly strengthened the inflation backdrop."
        )
    if direction == "stronger":
        return (
            f"Stronger-than-expected {event_name} modestly strengthened the growth backdrop "
            "and shifted rate-cut odds."
        )
    return (
        f"Weaker-than-expected {event_name} modestly weakened the growth backdrop "
        "and shifted rate-cut odds."
    )


def compute_surprise_row(event_name: str, actual: str | None, consensus: str | None) -> dict[str, str]:
    act = parse_te_number(actual)
    con = parse_te_number(consensus)
    if act is None or con is None:
        return {
            "event": event_name,
            "actual": actual or "—",
            "consensus": consensus or "—",
            "surprise": "—",
            "direction": "—",
            "impact_note": "Insufficient data to compute surprise.",
        }
    surprise = act - con
    direction = surprise_direction_label(event_name, surprise)
    impact = build_impact_note(event_name, direction, abs(surprise))
    sur_str = f"{surprise:+.2f}"
    if abs(con) > 1e-9:
        pct = (surprise / abs(con)) * 100.0
        sur_str = f"{surprise:+.2f} ({pct:+.1f}% vs consensus)"
    return {
        "event": event_name,
        "actual": str(actual),
        "consensus": str(consensus),
        "surprise": sur_str,
        "direction": direction,
        "impact_note": impact,
    }


def fed_easing_mass(_hold: float, cut25: float, cut50: float) -> float:
    return float(cut25) + float(cut50) * 1.2


def fed_hawk_mass(hike25: float, hold: float) -> float:
    return float(hike25) + float(hold) * 0.1


def repricing_delta_label(
    prev_easing: float | None,
    curr_easing: float | None,
    prev_hawk: float | None,
    curr_hawk: float | None,
    threshold: float = 0.05,
) -> str:
    if prev_easing is None or curr_easing is None:
        return "little changed"
    de = curr_easing - prev_easing
    dh = (curr_hawk or 0) - (prev_hawk or 0)
    if de > threshold and de >= dh:
        return "more dovish"
    if dh > threshold and dh > de:
        return "more hawkish"
    if de < -threshold or dh < -threshold:
        return "more hawkish" if de < -threshold else "more dovish"
    return "little changed"


def compute_tactical_posture_modifier(
    *,
    has_major_event_24h: bool,
    unclear_consensus_near_event: bool,
    latest_surprise_adverse: bool,
    latest_surprise_favorable: bool,
    fed_shift_hawkish: bool,
    fed_shift_dovish: bool,
) -> str:
    if has_major_event_24h and unclear_consensus_near_event:
        return "mixed — event risk elevated"
    if latest_surprise_adverse and fed_shift_hawkish:
        return "caution after adverse surprise"
    if latest_surprise_adverse:
        return "supportive but deteriorating"
    if latest_surprise_favorable and fed_shift_dovish and not has_major_event_24h:
        return "supportive"
    if fed_shift_hawkish:
        return "supportive but deteriorating"
    if has_major_event_24h:
        return "mixed — event risk elevated"
    return "mixed — event risk elevated"


def build_regime_impact_narrative(
    *,
    base_posture: str,
    tactical: str,
    upcoming_highlight: str | None,
    fed_line: str | None,
    inflation_incomplete: bool,
) -> str:
    parts: list[str] = []
    parts.append(f"Base posture from the durable framework remains: {base_posture}.")
    if inflation_incomplete:
        parts.append(
            "Inflation confirmation is incomplete — treat headline macro catalysts as higher-uncertainty."
        )
    if upcoming_highlight:
        parts.append(upcoming_highlight)
    if fed_line:
        parts.append(fed_line)
    parts.append(f"Tactical overlay: {tactical} — warning lights, not timers.")
    return " ".join(parts)
