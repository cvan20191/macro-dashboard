import type { DashboardState } from '../../types/summary'

import CohortRotationCard from './CohortRotationCard'
import PeerScorecardsCard from './PeerScorecardsCard'

interface Props {
  state?: DashboardState | null
}

export function WatchlistCard({ state }: Props) {
  if (!state) return null

  return (
    <div style={styles.wrapper}>
      <CohortRotationCard state={state} />
      <PeerScorecardsCard state={state} />
    </div>
  )
}

const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '16px',
  },
}
