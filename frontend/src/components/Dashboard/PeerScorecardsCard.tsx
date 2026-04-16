import type { CSSProperties } from 'react'

import type { DashboardState, PeerScoreMetric } from '../../types/summary'
import { Card } from '../ui/Card'

interface Props {
  state?: DashboardState | null
}

function verdictColor(verdict?: string): string {
  if (verdict === 'leader') return 'var(--green)'
  if (verdict === 'fragile') return 'var(--yellow)'
  if (verdict === 'balanced') return 'var(--text-primary)'
  return 'var(--text-muted)'
}

function formatMetric(label: string, metric?: PeerScoreMetric): string {
  return (
    `${label}: ${metric?.value ?? '—'} · ` +
    `Peer median: ${metric?.peer_median ?? '—'} · ` +
    `Favorable percentile: ${metric?.favorable_percentile ?? '—'}`
  )
}

export default function PeerScorecardsCard({ state }: Props) {
  const cards = state?.peer_scorecards
  if (!cards || cards.length === 0) return null

  const ordered = [...cards].sort((a, b) => {
    const rank = (value?: string) => (
      value === 'leader' ? 0 : value === 'balanced' ? 1 : value === 'fragile' ? 2 : 3
    )
    return rank(a.verdict) - rank(b.verdict)
  })

  return (
    <Card title="Same-Sector Peer Scorecards">
      <p style={styles.note}>
        Revenue growth, earnings growth, forward P/E, and debt/EBITDA versus peers.
      </p>

      <div style={styles.stack}>
        {ordered.map((card) => (
          <div key={card.ticker} style={styles.item}>
            <div style={styles.itemHeader}>
              <div>
                <div style={styles.itemTitle}>{card.ticker}</div>
                <div style={styles.meta}>{card.industry ?? card.sector ?? 'Unknown industry'}</div>
              </div>
              <div style={{ ...styles.verdict, color: verdictColor(card.verdict) }}>
                {card.verdict ?? 'insufficient'}
              </div>
            </div>

            <div style={styles.metrics}>
              <div style={styles.metric}>{formatMetric('Revenue growth', card.revenue_growth)}</div>
              <div style={styles.metric}>{formatMetric('Earnings growth', card.earnings_growth)}</div>
              <div style={styles.metric}>{formatMetric('Forward P/E', card.forward_pe)}</div>
              <div style={styles.metric}>{formatMetric('Debt / EBITDA', card.debt_to_ebitda)}</div>
            </div>

            {card.peer_tickers && card.peer_tickers.length > 0 ? (
              <div style={styles.meta}>Peers: {card.peer_tickers.join(', ')}</div>
            ) : null}

            {card.note ? <div style={styles.reason}>{card.note}</div> : null}
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
    gap: '8px',
  },
  itemHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '12px',
  },
  itemTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  verdict: {
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
  metrics: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  metric: {
    fontSize: '12px',
    lineHeight: 1.5,
    color: 'var(--text-secondary)',
  },
  reason: {
    fontSize: '13px',
    lineHeight: 1.6,
    color: 'var(--text-secondary)',
  },
}
