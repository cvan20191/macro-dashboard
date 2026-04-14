import type { ReactNode } from 'react'
import { Card } from '../../ui/Card'
import type { MacroExpectationsState } from '../../../types/playbook'

interface Props {
  macro: MacroExpectationsState
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th style={{
      textAlign: 'left',
      fontSize: '10px',
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      padding: '6px 8px',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      {children}
    </th>
  )
}

function Td({ children, colSpan }: { children: ReactNode; colSpan?: number }) {
  return (
    <td
      colSpan={colSpan}
      style={{ fontSize: '11px', padding: '6px 8px', color: 'var(--text-secondary)', verticalAlign: 'top' }}
    >
      {children}
    </td>
  )
}

export function MacroExpectationsPanel({ macro }: Props) {
  return (
    <Card title="Macro Expectations / Event Prep" accent="var(--yellow)">
      <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
        Tactical prep layer — warning lights, not timers. Does not replace the durable regime framework.
      </p>

      <SectionTitle>A. Upcoming key events (US, importance ≥ 2)</SectionTitle>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <Th>Event</Th>
              <Th>Release</Th>
              <Th>Previous</Th>
              <Th>Consensus</Th>
              <Th>Imp.</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {macro.upcoming_events.length === 0 ? (
              <tr><Td colSpan={6}>No events in window — check API key or cache.</Td></tr>
            ) : (
              macro.upcoming_events.map((e, i) => (
                <tr key={`${e.event_name}-${i}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <Td>{e.event_name}</Td>
                  <Td>{e.release_time}</Td>
                  <Td>{e.previous}</Td>
                  <Td>{e.consensus}</Td>
                  <Td>{e.importance}</Td>
                  <Td>{e.status}</Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <SectionTitle>B. Fed pricing (next meetings)</SectionTitle>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <Th>Meeting</Th>
              <Th>Hold</Th>
              <Th>Cut 25</Th>
              <Th>Cut 50</Th>
              <Th>Hike 25</Th>
              <Th>Δ vs prior</Th>
            </tr>
          </thead>
          <tbody>
            {macro.fed_pricing.length === 0 ? (
              <tr><Td colSpan={6}>No FedWatch data — configure CME API or add fed_pricing_manual.json.</Td></tr>
            ) : (
              macro.fed_pricing.map((r, i) => (
                <tr key={`${r.meeting_date}-${i}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <Td>{r.meeting_date}</Td>
                  <Td>{r.hold_pct}</Td>
                  <Td>{r.cut_25_pct}</Td>
                  <Td>{r.cut_50_pct}</Td>
                  <Td>{r.hike_25_pct}</Td>
                  <Td>{r.delta_vs_prior}</Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <SectionTitle>C. Recent surprises (last released)</SectionTitle>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <Th>Event</Th>
              <Th>Actual</Th>
              <Th>Consensus</Th>
              <Th>Surprise</Th>
              <Th>Direction</Th>
              <Th>Impact note</Th>
            </tr>
          </thead>
          <tbody>
            {macro.recent_surprises.length === 0 ? (
              <tr><Td colSpan={6}>No recent releases in sample.</Td></tr>
            ) : (
              macro.recent_surprises.map((s, i) => (
                <tr key={`${s.event}-${i}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <Td>{s.event}</Td>
                  <Td>{s.actual}</Td>
                  <Td>{s.consensus}</Td>
                  <Td>{s.surprise}</Td>
                  <Td>{s.direction}</Td>
                  <Td>{s.impact_note}</Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <SectionTitle>D. Regime impact (overlay)</SectionTitle>
      <div style={{
        padding: '12px 14px',
        background: 'var(--bg-card-raised)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '12px',
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
      }}>
        {macro.regime_impact_narrative}
      </div>

      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '10px' }}>
        <strong>Sources</strong>
        {' '}
        {macro.sources.map((s) => (
          <span key={s.provider + s.fetched_at} style={{ marginRight: '12px' }}>
            {s.provider}
            {s.stale ? ' (stale)' : ''}
            {s.note ? ` — ${s.note}` : ''}
            {' · '}
            as-of {s.fetched_at}
          </span>
        ))}
        {' · '}
        Generated {macro.generated_at}
      </div>
    </Card>
  )
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div style={{
      fontSize: '11px',
      fontWeight: 700,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      marginTop: '14px',
      marginBottom: '6px',
    }}>
      {children}
    </div>
  )
}
