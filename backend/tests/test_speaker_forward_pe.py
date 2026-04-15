from datetime import date

from app.services.rules.speaker_forward_pe import compute_speaker_forward_pe


def _payload(
    ticker: str,
    price: float,
    shares: float,
    current_eps: float | None,
    next_eps: float | None,
) -> dict:
    annual_eps_by_year: dict[int, float] = {}
    estimate_dates_by_year: dict[int, str] = {}
    if current_eps is not None:
        annual_eps_by_year[2026] = current_eps
        estimate_dates_by_year[2026] = "2026-12-31"
    if next_eps is not None:
        annual_eps_by_year[2027] = next_eps
        estimate_dates_by_year[2027] = "2027-12-31"

    return {
        "ticker": ticker,
        "price": price,
        "shares": shares,
        "annual_eps_by_year": annual_eps_by_year,
        "estimate_dates_by_year": estimate_dates_by_year,
        "estimate_as_of": "2026-04-15",
    }


def test_current_year_is_selected_before_switch_month() -> None:
    payloads = [
        _payload("AAA", 100.0, 10.0, 5.0, 6.0),
        _payload("BBB", 200.0, 10.0, 10.0, 12.0),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 6, 1))

    assert result.selected_year == 2026
    assert result.current_year_forward_pe is not None
    assert result.speaker_forward_pe == result.current_year_forward_pe


def test_next_year_is_selected_from_switch_month_onward() -> None:
    payloads = [
        _payload("AAA", 100.0, 10.0, 5.0, 6.0),
        _payload("BBB", 200.0, 10.0, 10.0, 12.0),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.selected_year == 2027
    assert result.next_year_forward_pe is not None
    assert result.speaker_forward_pe == result.next_year_forward_pe


def test_directional_only_when_selected_year_is_incomplete() -> None:
    payloads = [
        _payload("AAA", 100.0, 10.0, 5.0, 6.0),
        _payload("BBB", 200.0, 10.0, 10.0, None),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.valid is True
    assert result.selected_year == 2027
    assert result.signal_mode == "directional_only"
    assert result.coverage_count == 1
    assert result.coverage_ratio < 1.0


def test_actionable_when_selected_year_is_complete() -> None:
    payloads = [
        _payload("AAA", 100.0, 10.0, 5.0, 6.0),
        _payload("BBB", 200.0, 10.0, 10.0, 12.0),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.valid is True
    assert result.selected_year == 2027
    assert result.signal_mode == "actionable"
    assert result.coverage_count == 2
    assert result.coverage_ratio == 1.0
