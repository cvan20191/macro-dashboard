import type { CSSProperties } from 'react'

import type { DashboardState, StrategicWatchlistItem } from '../../types/summary'
import { Card } from '../ui/Card'

interface Props {
  state?: DashboardState | null
}

function statusColor(status?: string): string {
  if (status === 'supportive') return 'var(--green)'
  if (status === 'warning') return 'var(--yellow)'
  if (status === 'mixed') return 'var(--text-primary)'
  return 'var(--text-muted)'
}

export default function StrategicWatchlistCard({ state }: Props) {
  const watchlist = state?.strategic_watchlist
  if (!watchlist?.items || watchlist.items.length === 0) return null

  return (
    <Card title="2026 Strategic Watchlist">
      {watchlist.note ? <p style={styles.note}>{watchlist.note}</p> : null}

      <div style={styles.stack}>
        {watchlist.items.map((item: StrategicWatchlistItem) => (
          <div key={item.code} style={styles.item}>
            <div style={styles.itemHeader}>
              <div style={styles.itemTitle}>{item.label}</div>
              <div style={{ ...styles.status, color: statusColor(item.status) }}>
                {item.status ?? 'watch'}
              </div>
            </div>
            <div style={styles.meta}>
              Source: {item.source_mode ?? 'manual'} · Kind: {item.kind ?? 'manual_event'}
            </div>
            {item.note ? <div style={styles.reason}>{item.note}</div> : null}
          </div>
        ))}
      </div>
    </Card>
  )
}

const styles: Record<string, CSSProperties> = {
  note: {
    margin: 0,
    fontSize: '12px',
    lineHeight: 1.6,
    color: 'var(--text-secondary)',
  },
  stack: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  item: {
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 14px',
    background: 'var(--bg-card-raised)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  itemHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
  },
  itemTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  status: {
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'capitalize',
    whiteSpace: 'nowrap',
  },
  meta: {
    fontSize: '12px',
    lineHeight: 1.5,
    color: 'var(--text-muted)',
  },
  reason: {
    fontSize: '13px',
    lineHeight: 1.6,
    color: 'var(--text-secondary)',
  },
}
