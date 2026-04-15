import type { DashboardState, PlaybookSummary } from '../../types/summary'
import { Card } from '../ui/Card'

interface Props {
  state?: DashboardState | null
  summary?: PlaybookSummary | null
}

function BulletSection({ title, items, accentColor }: { title: string; items: string[]; accentColor: string }) {
  return (
    <div>
      <div style={{
        fontSize: '11px', fontWeight: 700, letterSpacing: '0.07em',
        textTransform: 'uppercase', color: accentColor, marginBottom: '8px',
      }}>
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {items.length === 0
          ? <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>—</span>
          : items.map((item, i) => (
            <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <span style={{
                flexShrink: 0, marginTop: '2px',
                width: '5px', height: '5px', borderRadius: '50%',
                background: accentColor, marginLeft: '2px',
              }} />
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                {item}
              </span>
            </div>
          ))
        }
      </div>
    </div>
  )
}

export function WatchlistCard({ state, summary }: Props) {
  const watchNow = state?.top_watchpoints?.length ? state.top_watchpoints : (summary?.watch_now ?? [])
  const whatChanged = state?.what_changed?.length ? state.what_changed : (summary?.what_changed_bullets ?? [])
  const whatChangesCall = state?.what_changes_call?.length ? state.what_changes_call : (summary?.what_changes_call_bullets ?? [])

  return (
    <Card title="Watch Now · What Changed · What Changes the Call">
      <BulletSection title="Watch Now" items={watchNow} accentColor="var(--blue)" />
      <div style={{ height: '1px', background: 'var(--border-subtle)' }} />
      <BulletSection title="What Changed" items={whatChanged} accentColor="var(--yellow)" />
      <div style={{ height: '1px', background: 'var(--border-subtle)' }} />
      <BulletSection title="What Would Change the Call" items={whatChangesCall} accentColor="var(--green)" />
    </Card>
  )
}
