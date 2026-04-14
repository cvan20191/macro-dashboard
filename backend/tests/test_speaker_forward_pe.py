from __future__ import annotations

from datetime import date

from app.services.rules.speaker_forward_pe import compute_speaker_forward_pe


def _payload(ticker: str, current_eps: float | None, next_eps: float | None) -> dict:
    annual_eps_by_year: dict[int, float] = {}
    if current_eps is not None:
        annual_eps_by_year[2026] = current_eps
    if next_eps is not None:
        annual_eps_by_year[2027] = next_eps
    return {
        "ticker": ticker,
        "price": 100.0,
        "shares": 10.0,
        "market_cap": 1_000.0,
        "annual_eps_by_year": annual_eps_by_year,
        "estimate_as_of": "2026-04-14",
    }


def test_computes_current_and_next_year_forward_pe_and_selects_current_before_q4() -> None:
    payloads = [_payload(f"T{i}", 5.0, 6.0) for i in range(5)]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 6, 1), switch_month=10)

    assert result.current_year_forward_pe == 20.0
    assert result.next_year_forward_pe == round(100.0 / 6.0, 4)
    assert result.speaker_forward_pe == 20.0
    assert result.selected_year == 2026
    assert result.horizon_label == "speaker_calendar_current_year"
    assert result.valid is True


def test_selects_next_year_near_year_end() -> None:
    payloads = [_payload(f"T{i}", 5.0, 6.0) for i in range(5)]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 11, 15), switch_month=10)

    assert result.current_year_forward_pe == 20.0
    assert result.next_year_forward_pe == round(100.0 / 6.0, 4)
    assert result.speaker_forward_pe == round(100.0 / 6.0, 4)
    assert result.selected_year == 2027
    assert result.horizon_label == "speaker_calendar_next_year"
    assert result.valid is True


def test_falls_back_to_current_year_when_next_year_is_missing_after_switch_month() -> None:
    payloads = [_payload(f"T{i}", 5.0, None) for i in range(5)]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 11, 15), switch_month=10)

    assert result.speaker_forward_pe == 20.0
    assert result.selected_year == 2026
    assert result.horizon_label == "speaker_calendar_current_year_fallback"
