import asyncio

from app.schemas.catalysts import CatalystState
from app.schemas.dashboard_state import DashboardState, DataFreshness, DeterministicSummary
from app.schemas.indicator_snapshot import IndicatorSnapshot
from app.schemas.live_snapshot_response import LiveSnapshotResponse
from app.schemas.macro_expectations import MacroExpectationsState
from app.schemas.playbook_conclusion import PlaybookConclusion
from app.services.ingestion import live_snapshot_service


def test_live_playbook_returns_deterministic_summary_and_null_legacy_summary(
    monkeypatch,
) -> None:
    async def _fake_get_live_snapshot(*args, **kwargs):
        return LiveSnapshotResponse(
            snapshot=IndicatorSnapshot(as_of="2026-04-15T00:00:00Z"),
            sources={},
            overall_status="fresh",
            stale_series=[],
            generated_at="2026-04-15T00:00:00Z",
        )

    def _fake_build_dashboard_state_with_conclusion(snapshot):
        state = DashboardState(
            as_of="2026-04-15T00:00:00Z",
            data_freshness=DataFreshness(overall_status="fresh", stale_series=[]),
            primary_regime="Quadrant C / Liquidity Transition",
            current_posture="selective",
        )
        conclusion = PlaybookConclusion(
            conclusion_label="Transition regime",
            new_cash_action="hold_and_wait",
            warning_urgency="cautionary",
            why_now="liquidity_quadrant_c_transition",
        )
        return state, conclusion

    def _fake_build_deterministic_summary(state, conclusion):
        return DeterministicSummary(
            headline=state.primary_regime,
            subheadline="Liquidity is improving, but QT is still not fully over.",
            action_line="Action: hold and wait.",
        )

    def _fake_get_macro_expectations_state(*args, **kwargs):
        return MacroExpectationsState(
            regime_impact_narrative="Macro expectations unavailable for test.",
            tactical_posture_modifier="mixed — event risk elevated",
            generated_at="2026-04-15T00:00:00Z",
        )

    def _fake_build_catalyst_state(*args, **kwargs):
        return CatalystState()

    monkeypatch.setattr(live_snapshot_service, "get_live_snapshot", _fake_get_live_snapshot)
    monkeypatch.setattr(
        live_snapshot_service,
        "build_dashboard_state_with_conclusion",
        _fake_build_dashboard_state_with_conclusion,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "build_deterministic_summary",
        _fake_build_deterministic_summary,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "get_macro_expectations_state",
        _fake_get_macro_expectations_state,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "build_catalyst_state",
        _fake_build_catalyst_state,
    )

    result = asyncio.run(live_snapshot_service.get_live_playbook())

    assert result.summary is None
    assert result.state.deterministic_summary is not None
    assert result.state.deterministic_summary.headline == "Quadrant C / Liquidity Transition"
