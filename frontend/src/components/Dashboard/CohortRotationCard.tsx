import type { CSSProperties } from 'react'

import type { DashboardState } from '../../types/summary'
import { Card } from '../ui/Card'

interface Props {
  state?: DashboardState | null
}

function stanceColor(stance?: string): string {
  if (stance === 'overweight') return 'var(--green)'
  if (stance === 'accumulate_slowly') return 'var(--blue)'
  if (stance === 'watch') return 'var(--blue-2, var(--blue))'
  if (stance === 'underweight' || stance === 'avoid') return 'var(--yellow)'
  return 'var(--text-secondary)'
}

export default function CohortRotationCard({ state }: Props) {
  const guide = state?.cohort_rotation_guidance
  if (!guide || !guide.items || guide.items.length === 0) return null

  return (
    <Card title="Cohort Rotation">
      {guide.note ? <p style={styles.note}>{guide.note}</p> : null}
      {guide.defensive_anchor_code ? (
        <p style={styles.anchor}>Defensive anchor: {guide.defensive_anchor_code}</p>
      ) : null}

      <div style={styles.stack}>
        {guide.items.map((item) => (
          <div key={item.cohort_code} style={styles.item}>
            <div style={styles.itemHeader}>
              <div style={styles.itemTitle}>{item.label}</div>
              <div style={{ ...styles.stance, color: stanceColor(item.stance) }}>
                {item.stance ?? 'neutral'}
              </div>
            </div>
            {item.forward_pe != null ? (
              <div style={styles.meta}>
                Forward P/E: {item.forward_pe} · Signal mode: {item.signal_mode ?? 'directional_only'}
              </div>
            ) : null}
            {item.reason ? <div style={styles.reason}>{item.reason}</div> : null}
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
  anchor: {
    margin: 0,
    fontSize: '12px',
    lineHeight: 1.6,
    color: 'var(--text-muted)',
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
  stance: {
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
