"""
Macro expectations / event prep overlay — TTL file caches, multi-provider assembly.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas.indicator_snapshot import IndicatorSnapshot
from app.schemas.macro_expectations import (
    FedPricingTableRow,
    MacroExpectationsState,
    MacroSourceAttribution,
    SurpriseRow,
    UpcomingEventRow,
)
from app.services.macro_expectations_derivations import (
    build_regime_impact_narrative,
    compute_surprise_row,
    compute_tactical_posture_modifier,
    fed_easing_mass,
    fed_hawk_mass,
    repricing_delta_label,
)
from app.services.providers import cme_fedwatch_client as cme
from app.services.providers import ny_fed_markets_client as ny_fed
from app.services.providers import trading_economics_client as te
from app.services.providers.base import ProviderError
from app.services.rules.stagflation import inflation_inputs_incomplete

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
_CAL_CACHE = _CACHE_DIR / "macro_te_calendar.json"
_NY_CACHE = _CACHE_DIR / "macro_ny_fed_ops.json"
_FW_CACHE = _CACHE_DIR / "macro_fedwatch_meetings.json"
_FW_PREV = _CACHE_DIR / "macro_fedwatch_prev.json"

_TTL_CAL = 30 * 60
_TTL_FW = 6 * 3600
_TTL_NY = 3600


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_disk(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_disk(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=str), encoding="utf-8")


def _ttl_expired(stored_at: float, ttl: int) -> bool:
    return (time.monotonic() - stored_at) > ttl


def _wrap_cache_payload(data: Any, ttl: int) -> dict[str, Any]:
    return {"_stored_mono": time.monotonic(), "_ttl": ttl, "data": data}


def _read_cache(path: Path, ttl: int, force_refresh: bool) -> tuple[Any | None, bool, float | None]:
    """Returns (data, stale, stored_mono)."""
    raw = _load_disk(path)
    if not raw or force_refresh:
        return None, False, None
    sm = raw.get("_stored_mono")
    t = raw.get("_ttl", ttl)
    data = raw.get("data")
    if not isinstance(sm, (int, float)):
        return data, True, None
    if _ttl_expired(float(sm), int(t)):
        return data, True, float(sm)
    return data, False, float(sm)


def _fed_target_bps(snapshot: IndicatorSnapshot | None) -> int | None:
    if snapshot is None:
        return None
    r = snapshot.liquidity.fed_funds_rate
    if r is None:
        return None
    return int(round(float(r) * 100))


def _load_manual_fed_pricing() -> dict[str, Any] | None:
    path = Path(__file__).resolve().parents[1] / "data" / "fed_pricing_manual.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _normalize_meetings_from_manual(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for m in obj.get("meetings") or []:
        if not isinstance(m, dict):
            continue
        rows.append({
            "meeting_date": str(m.get("meeting_date", "")),
            "source_timestamp": str(m.get("source_timestamp", obj.get("as_of", ""))),
            "probability_hold": m.get("probability_hold"),
            "probability_cut_25": m.get("probability_cut_25"),
            "probability_cut_50": m.get("probability_cut_50"),
            "probability_hike_25": m.get("probability_hike_25"),
            "repricing_delta_label": str(m.get("repricing_delta_label", "little changed")),
        })
    return rows


def _meetings_from_cme_api(fed_bps: int | None) -> list[dict[str, Any]]:
    raw_list = cme.fetch_forecasts_raw(timeout=settings.http_timeout_seconds)
    out: list[dict[str, Any]] = []
    for item in raw_list[:8]:
        if not isinstance(item, dict):
            continue
        norm = cme.normalize_forecast_entry(item)
        ranges = norm.get("rate_ranges") or []
        h, c25, c50, h25, _ = cme.bucket_probabilities(ranges, fed_bps)
        out.append({
            "meeting_date": norm["meeting_date"],
            "source_timestamp": norm["source_timestamp"],
            "probability_hold": h,
            "probability_cut_25": c25,
            "probability_cut_50": c50,
            "probability_hike_25": h25,
            "repricing_delta_label": "little changed",
        })
    return out


def _apply_repricing_deltas(
    meetings: list[dict[str, Any]],
) -> None:
    prev_raw = _load_disk(_FW_PREV)
    prev_meetings = (prev_raw or {}).get("meetings") if isinstance(prev_raw, dict) else None
    if not isinstance(prev_meetings, list) or not prev_meetings:
        return
    prev_by_date = {str(m.get("meeting_date")): m for m in prev_meetings if isinstance(m, dict)}
    for m in meetings:
        md = str(m.get("meeting_date", ""))
        pm = prev_by_date.get(md)
        if not pm:
            continue
        pe = fed_easing_mass(
            float(pm.get("probability_hold") or 0),
            float(pm.get("probability_cut_25") or 0),
            float(pm.get("probability_cut_50") or 0),
        )
        ce = fed_easing_mass(
            float(m.get("probability_hold") or 0),
            float(m.get("probability_cut_25") or 0),
            float(m.get("probability_cut_50") or 0),
        )
        ph = fed_hawk_mass(
            float(pm.get("probability_hike_25") or 0),
            float(pm.get("probability_hold") or 0),
        )
        ch = fed_hawk_mass(
            float(m.get("probability_hike_25") or 0),
            float(m.get("probability_hold") or 0),
        )
        m["repricing_delta_label"] = repricing_delta_label(pe, ce, ph, ch)


def _persist_fedwatch_prev(meetings: list[dict[str, Any]]) -> None:
    _save_disk(_FW_PREV, {"meetings": meetings, "saved_at": _now_iso()})


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def get_macro_expectations_state(
    snapshot: IndicatorSnapshot | None = None,
    force_refresh: bool = False,
    base_posture: str = "See regime framework",
) -> MacroExpectationsState:
    sources: list[MacroSourceAttribution] = []
    now_iso = _now_iso()
    fed_bps = _fed_target_bps(snapshot)
    inflation_incomplete = (
        inflation_inputs_incomplete(snapshot.inflation)
        if snapshot is not None
        else True
    )

    # --- Trading Economics calendar ---
    cal_rows: list[dict[str, Any]] = []
    cached_cal, cal_stale_disk, _ = _read_cache(_CAL_CACHE, _TTL_CAL, force_refresh)
    if cached_cal is not None and isinstance(cached_cal, list) and not force_refresh and not cal_stale_disk:
        cal_rows = cached_cal
        sources.append(MacroSourceAttribution(
            provider="Trading Economics (cache)",
            fetched_at=now_iso,
            stale=False,
        ))
    elif te.is_available(settings.trading_economics_api_key):
        try:
            start, end = te.default_us_date_window(14)
            raw = te.fetch_us_calendar_range(
                settings.trading_economics_api_key,
                start,
                end,
                timeout=settings.http_timeout_seconds,
            )
            cal_rows = [te.normalize_calendar_row(x) for x in raw if isinstance(x, dict)]
            _save_disk(_CAL_CACHE, _wrap_cache_payload(cal_rows, _TTL_CAL))
            sources.append(MacroSourceAttribution(
                provider="Trading Economics",
                fetched_at=now_iso,
                stale=False,
                note=None,
            ))
        except ProviderError as exc:
            logger.warning("TE calendar failed: %s", exc)
            if isinstance(cached_cal, list):
                cal_rows = cached_cal
            sources.append(MacroSourceAttribution(
                provider="Trading Economics",
                fetched_at=now_iso,
                stale=True,
                note=str(exc),
            ))
    else:
        if isinstance(cached_cal, list):
            cal_rows = cached_cal
        sources.append(MacroSourceAttribution(
            provider="Trading Economics",
            fetched_at=now_iso,
            stale=True,
            note="API key not configured — using cache if any",
        ))

    us_important = [
        r for r in cal_rows
        if str(r.get("country", "")).lower() in ("united states", "us", "usa")
        and int(r.get("importance") or 0) >= 2
    ]
    us_important.sort(key=lambda x: str(x.get("release_datetime", "")))

    upcoming: list[UpcomingEventRow] = []
    for r in us_important:
        if r.get("status") != "upcoming":
            continue
        upcoming.append(UpcomingEventRow(
            event_name=str(r.get("event_name", "")),
            release_time=str(r.get("release_datetime", "")),
            previous=r.get("previous") or "—",
            consensus=r.get("consensus") or "—",
            importance=int(r.get("importance") or 0),
            status="upcoming",
        ))
        if len(upcoming) >= 10:
            break
    if len(upcoming) < 10:
        for r in us_important:
            if any(u.event_name == r.get("event_name") for u in upcoming):
                continue
            if r.get("status") == "upcoming":
                continue
            upcoming.append(UpcomingEventRow(
                event_name=str(r.get("event_name", "")),
                release_time=str(r.get("release_datetime", "")),
                previous=r.get("previous") or "—",
                consensus=r.get("consensus") or "—",
                importance=int(r.get("importance") or 0),
                status=str(r.get("status", "released")),
            ))
            if len(upcoming) >= 10:
                break

    released_sorted = [
        r for r in us_important if r.get("status") == "released"
    ]
    released_sorted.sort(key=lambda x: str(x.get("release_datetime", "")), reverse=True)
    surprises: list[SurpriseRow] = []
    for r in released_sorted[:5]:
        sr = compute_surprise_row(
            str(r.get("event_name", "")),
            r.get("actual"),
            r.get("consensus"),
        )
        surprises.append(SurpriseRow(**sr))

    # Major event in 24h + unclear consensus
    has_major_24h = False
    unclear_consensus = False
    try:
        now = datetime.now(timezone.utc)
        for r in us_important:
            if int(r.get("importance") or 0) < 3:
                continue
            dt_s = str(r.get("release_datetime", ""))
            try:
                dt = datetime.fromisoformat(dt_s.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if now <= dt <= now + timedelta(hours=24):
                has_major_24h = True
                c = r.get("consensus")
                if c is None or str(c).strip() == "":
                    unclear_consensus = True
    except Exception:
        pass

    latest_adverse = False
    latest_favorable = False
    if surprises:
        d0 = surprises[0].direction
        if d0 in ("hotter", "weaker"):
            latest_adverse = True
        if d0 in ("cooler", "stronger"):
            latest_favorable = True

    # --- Fed pricing ---
    meetings: list[dict[str, Any]] = []
    cached_fw, fw_stale_disk, _ = _read_cache(_FW_CACHE, _TTL_FW, force_refresh)
    if cached_fw is not None and isinstance(cached_fw, list) and not force_refresh and not fw_stale_disk:
        meetings = cached_fw
        sources.append(MacroSourceAttribution(
            provider="CME FedWatch (cache)",
            fetched_at=now_iso,
            stale=False,
        ))
    else:
        got = False
        try:
            if cme.is_api_configured():
                meetings = _meetings_from_cme_api(fed_bps)
                _apply_repricing_deltas(meetings)
                _persist_fedwatch_prev(meetings)
                _save_disk(_FW_CACHE, _wrap_cache_payload(meetings, _TTL_FW))
                sources.append(MacroSourceAttribution(
                    provider="CME FedWatch",
                    fetched_at=now_iso,
                    stale=False,
                ))
                got = True
        except (ProviderError, Exception) as exc:
            logger.warning("CME FedWatch failed: %s", exc)
        if not got:
            manual = _load_manual_fed_pricing()
            if manual:
                meetings = _normalize_meetings_from_manual(manual)
                fw_note = "Source: manual entry — as of " + str(manual.get("as_of", "unknown"))
                _apply_repricing_deltas(meetings)
                _persist_fedwatch_prev(meetings)
                sources.append(MacroSourceAttribution(
                    provider="Fed pricing (manual JSON)",
                    fetched_at=now_iso,
                    stale=False,
                    note=fw_note,
                ))
                got = True
            elif isinstance(cached_fw, list):
                meetings = cached_fw
                sources.append(MacroSourceAttribution(
                    provider="CME FedWatch (stale cache)",
                    fetched_at=now_iso,
                    stale=True,
                ))
            else:
                sources.append(MacroSourceAttribution(
                    provider="CME FedWatch",
                    fetched_at=now_iso,
                    stale=True,
                    note="No API, no manual file, no cache",
                ))

    fed_rows: list[FedPricingTableRow] = []
    fed_shift_hawk = False
    fed_shift_dove = False
    for m in meetings[:4]:
        lbl = str(m.get("repricing_delta_label", "little changed"))
        if "hawkish" in lbl.lower():
            fed_shift_hawk = True
        if "dovish" in lbl.lower():
            fed_shift_dove = True
        fed_rows.append(FedPricingTableRow(
            meeting_date=str(m.get("meeting_date", "")),
            hold_pct=_fmt_pct(m.get("probability_hold")),
            cut_25_pct=_fmt_pct(m.get("probability_cut_25")),
            cut_50_pct=_fmt_pct(m.get("probability_cut_50")),
            hike_25_pct=_fmt_pct(m.get("probability_hike_25")),
            delta_vs_prior=lbl,
        ))

    # --- NY Fed (optional one-liner) ---
    ny_line: str | None = None
    cached_ny, ny_stale_disk, _ = _read_cache(_NY_CACHE, _TTL_NY, force_refresh)
    ny_payload = None
    if cached_ny is not None and not force_refresh and not ny_stale_disk:
        ny_payload = cached_ny
    else:
        try:
            rr = ny_fed.fetch_latest_reverse_repo(timeout=settings.http_timeout_seconds)
            if isinstance(rr, list) and rr:
                rr = rr[0] if isinstance(rr[0], dict) else {}
            if not isinstance(rr, dict):
                rr = {}
            ny_payload = {"reverse_repo": rr}
            _save_disk(_NY_CACHE, _wrap_cache_payload(ny_payload, _TTL_NY))
            sources.append(MacroSourceAttribution(
                provider="NY Fed Markets",
                fetched_at=now_iso,
                stale=False,
            ))
        except ProviderError as exc:
            logger.warning("NY Fed failed: %s", exc)
            if isinstance(cached_ny, dict):
                ny_payload = cached_ny
            sources.append(MacroSourceAttribution(
                provider="NY Fed Markets",
                fetched_at=now_iso,
                stale=True,
                note=str(exc),
            ))
    if isinstance(ny_payload, dict) and ny_payload.get("reverse_repo"):
        raw = ny_payload["reverse_repo"]
        if isinstance(raw, dict):
            ny_line = "Latest Desk context (ON RRP / operations): data on file — see NY Fed Markets API for detail."

    tactical = compute_tactical_posture_modifier(
        has_major_event_24h=has_major_24h,
        unclear_consensus_near_event=unclear_consensus,
        latest_surprise_adverse=latest_adverse,
        latest_surprise_favorable=latest_favorable,
        fed_shift_hawkish=fed_shift_hawk,
        fed_shift_dovish=fed_shift_dove,
    )

    narrative = build_regime_impact_narrative(
        base_posture=base_posture,
        tactical=tactical,
        upcoming_highlight=(
            f"Upcoming releases within the window include {upcoming[0].event_name}."
            if upcoming
            else None
        ),
        fed_line=(
            "FedWatch-implied probabilities moved versus the prior stored snapshot."
            if fed_rows and any(r.delta_vs_prior.lower() != "little changed" for r in fed_rows)
            else None
        ),
        inflation_incomplete=inflation_incomplete,
    )

    return MacroExpectationsState(
        upcoming_events=upcoming,
        fed_pricing=fed_rows,
        recent_surprises=surprises,
        regime_impact_narrative=narrative,
        tactical_posture_modifier=tactical,
        sources=sources,
        generated_at=now_iso,
    )
