import type { ReactNode } from 'react'
import type { SystemicStress } from '../../types/summary'
import type { SourceMeta } from '../../types/playbook'
import { Card } from '../ui/Card'
import { fmtNum } from '../../lib/fmt'

interface Props {
  stress: SystemicStress
  /** Live/replay source row for Z.1 series id (optional). */
  sources?: Record<string, SourceMeta>
}

interface StressGaugeProps {
  label: string
  value: number | null | undefined
  displayValue: string
  zone: string
  zoneColor: string
  segments: { label: string; color: string; active: boolean }[]
  /** Provenance line (e.g. as-of + source + freshness) */
  meta?: ReactNode
  note?: string
}

function StressGauge({ label, value: _value, displayValue, zone, zoneColor, segments, meta, note }: StressGaugeProps) {
  return (
    <div style={s.gauge}>
      <div style={s.gaugeTop}>
        <span style={s.gaugeLabel}>{label}</span>
        <span style={{ fontSize: '16px', fontWeight: 800, color: zoneColor }}>{displayValue}</span>
        <span style={{ fontSize: '10px', fontWeight: 700, color: zoneColor, letterSpacing: '0.04em' }}>{zone}</span>
      </div>
      {meta != null && meta !== false && (
        <div style={{ marginTop: '1px' }}>{meta}</div>
      )}
      {/* Segment bar */}
      <div style={{ display: 'flex', gap: '2px', height: '6px', borderRadius: '3px', overflow: 'hidden' }}>
        {segments.map((seg, i) => (
          <div key={i} style={{
            flex: 1,
            background: seg.active ? seg.color : `${seg.color}30`,
            borderRadius: i === 0 ? '3px 0 0 3px' : i === segments.length - 1 ? '0 3px 3px 0' : '0',
          }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        {segments.map((seg, i) => (
          <span key={i} style={{ fontSize: '9px', color: seg.active ? seg.color : 'var(--text-muted)', fontWeight: seg.active ? 700 : 400 }}>
            {seg.label}
          </span>
        ))}
      </div>
      {note && (
        <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.5, marginTop: '2px' }}>{note}</p>
      )}
    </div>
  )
}

function _equityNumeratorStatusColor(fresh?: string): string {
  if (!fresh) return 'var(--text-muted)'
  if (fresh === 'fresh' || fresh === 'manual') return 'var(--green)'
  if (fresh === 'historical') return 'var(--text-muted)'
  if (fresh === 'stale') return 'var(--yellow)'
  if (fresh === 'missing' || fresh === 'error') return 'var(--red)'
  return 'var(--text-muted)'
}

function EquityNumeratorMetaBar({
  stress,
  sources,
}: {
  stress: SystemicStress
  sources?: Record<string, SourceMeta>
}) {
  const src = stress.equity_m2_ratio_source
  if (!src || stress.market_cap_m2_ratio == null) return null

  let sourceLabel: string
  if (src === 'manual_override') {
    sourceLabel = 'Manual file (manual_equity_m2_numerator.json)'
  } else if (src === 'fred_z1') {
    const sid = sources?.equity_market_value_z1?.series_id
    sourceLabel = sid ? `FRED ${sid}` : 'FRED BOGZ1LM893064105Q'
  } else {
    const sid = sources?.sp500_etf?.series_id
    sourceLabel = sid ? `Yahoo ${sid}` : 'Yahoo SPY proxy'
  }

  const asOf = stress.equity_m2_numerator_as_of?.trim() || '—'
  const fr = stress.equity_m2_numerator_freshness
  const statusText =
    fr === 'manual'
      ? 'override (local file, not FRED)'
      : (fr ?? '—')

  return (
    <p
      style={{
        margin: 0,
        fontSize: '10px',
        lineHeight: 1.5,
        color: 'var(--text-muted)',
        fontWeight: 500,
      }}
    >
      As-of <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{asOf}</span>
      {' · '}
      Source: {sourceLabel}
      {' · '}
      <span style={{ color: _equityNumeratorStatusColor(fr), fontWeight: 700 }}>
        Status: {statusText}
      </span>
    </p>
  )
}

export function SystemicStressCard({ stress, sources }: Props) {
  // Yield Curve
  const yc = stress.yield_curve_value ?? null
  const ycZone = stress.yield_curve_inverted ? 'Inverted' : 'Normal'
  const ycColor = stress.yield_curve_inverted ? 'var(--yellow)' : 'var(--green)'
  const ycSegments = [
    { label: 'Normal', color: 'var(--green)', active: !stress.yield_curve_inverted },
    { label: 'Inverted', color: 'var(--yellow)', active: !!stress.yield_curve_inverted },
  ]

  // NPL
  const npl = stress.npl_ratio ?? null
  const nplZone = stress.npl_zone ?? 'Normal'
  const nplColor = nplZone === 'Normal' ? 'var(--green)' : nplZone === 'Caution' ? 'var(--yellow)' : 'var(--red)'
  const nplSegments = [
    { label: 'Normal (<1%)', color: 'var(--green)', active: nplZone === 'Normal' },
    { label: 'Caution', color: 'var(--yellow)', active: nplZone === 'Caution' },
    { label: 'Warning (≥1.5%)', color: 'var(--red)', active: nplZone === 'Warning' },
  ]

  // Credit card charge-offs (CORCCACBN — quarterly %, annualized)
  const cc = stress.credit_card_chargeoff_rate ?? null
  const ccZone = stress.credit_card_chargeoff_zone ?? 'Normal'
  const ccColor = ccZone === 'Normal' ? 'var(--green)' : ccZone === 'Caution' ? 'var(--yellow)' : 'var(--red)'
  const ccSegments = [
    { label: 'Normal (<4.6%)', color: 'var(--green)', active: ccZone === 'Normal' },
    { label: 'Caution', color: 'var(--yellow)', active: ccZone === 'Caution' },
    { label: 'Warning (≥5.5%)', color: 'var(--red)', active: ccZone === 'Warning' },
  ]

  // Z.1 corporate equities / M2 (or legacy SPY proxy — different scale)
  const mcm2 = stress.market_cap_m2_ratio ?? null
  const mcm2Zone = stress.market_cap_m2_zone ?? 'Normal'
  const mcm2Color = mcm2Zone === 'Normal' ? 'var(--green)' : mcm2Zone === 'Warning' ? 'var(--yellow)' : 'var(--red)'
  const src = stress.equity_m2_ratio_source
  const isSpyFallback = src === 'spy_fallback'
  const isManualOverride = src === 'manual_override'
  const z1Scale = !isSpyFallback
  const mcm2Segments = z1Scale
    ? [
        { label: 'Normal (<5.8)', color: 'var(--green)', active: mcm2Zone === 'Normal' },
        { label: 'Warning', color: 'var(--yellow)', active: mcm2Zone === 'Warning' },
        { label: 'Extreme (≥6.8)', color: 'var(--red)', active: mcm2Zone === 'Extreme' },
      ]
    : [
        { label: 'Normal (<2)', color: 'var(--green)', active: mcm2Zone === 'Normal' },
        { label: 'Warning', color: 'var(--yellow)', active: mcm2Zone === 'Warning' },
        { label: 'Extreme (≥3)', color: 'var(--red)', active: mcm2Zone === 'Extreme' },
      ]

  const equityM2Title = isSpyFallback
    ? 'Equity / M2 (SPY proxy)'
    : isManualOverride
      ? 'Speaker market-cap / M2 (manual override)'
      : 'Z.1 corporate equities / M2'
  const equityM2Note = isSpyFallback
    ? 'Legacy SPY-scaled proxy when Z.1 is unavailable — not comparable to Z.1/M2 levels above.'
    : isManualOverride
      ? 'Manual speaker-style market-cap / M2 override. Use as a doctrine-facing proxy only when you explicitly trust the override source.'
      : 'Numerator: Fed Z.1 market value of corporate equities (L.223, quarterly, millions→billions). Denominator: WM2NS M2 (weekly, billions). Mixing quarterly stock with weekly money is intentional but stale vs spot markets — use as a slow liquidity-absorption gauge, not timing.'

  return (
    <Card title="Systemic Stress Gauges">
      <StressGauge
        label="10Y–2Y Yield Curve"
        value={yc}
        displayValue={yc !== null ? `${fmtNum(yc, 2)}%` : 'N/A'}
        zone={ycZone}
        zoneColor={ycColor}
        segments={ycSegments}
        note="An inverted yield curve has historically preceded recessions — it is a warning, not a timer."
      />

      <div style={{ height: '1px', background: 'var(--border-subtle)' }} />

      <StressGauge
        label="Bank NPL Ratio (Delinquency Proxy)"
        value={npl}
        displayValue={npl !== null ? `${fmtNum(npl, 2)}%` : 'N/A'}
        zone={nplZone ?? 'N/A'}
        zoneColor={nplColor}
        segments={nplSegments}
        note="NPL above 1.5% signals rising credit stress. This can be temporary — context matters."
      />

      <div style={{ height: '1px', background: 'var(--border-subtle)' }} />

      <StressGauge
        label="Credit card charge-off rate"
        value={cc}
        displayValue={cc !== null ? `${fmtNum(cc, 2)}%` : 'N/A'}
        zone={ccZone ?? 'N/A'}
        zoneColor={ccColor}
        segments={ccSegments}
        note="Fed H.8 charge-off rate (quarterly, annualized). Complements CRE delinquency for consumer-side stress."
      />

      <div style={{ height: '1px', background: 'var(--border-subtle)' }} />

      <StressGauge
        label={equityM2Title}
        value={mcm2}
        displayValue={mcm2 !== null ? fmtNum(mcm2, 2) : 'N/A'}
        zone={mcm2Zone ?? 'N/A'}
        zoneColor={mcm2Color}
        segments={mcm2Segments}
        meta={<EquityNumeratorMetaBar stress={stress} sources={sources} />}
        note={equityM2Note}
      />

      <div style={{
        padding: '8px 12px',
        background: 'var(--bg-card-raised)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '11px',
        color: 'var(--text-muted)',
        fontStyle: 'italic',
      }}>
        These are structural warning lights, not exact timing tools. Conditions can persist longer than expected.
      </div>
    </Card>
  )
}

const s: Record<string, React.CSSProperties> = {
  gauge: { display: 'flex', flexDirection: 'column', gap: '5px' },
  gaugeTop: { display: 'flex', alignItems: 'center', gap: '10px' },
  gaugeLabel: { fontSize: '11px', color: 'var(--text-muted)', flex: 1 },
}
