import { ShieldCheck, ShieldAlert, ShieldX, AlertTriangle, ChevronDown } from 'lucide-react';
import type { VerificationResult } from '../types';

interface Props { verification: VerificationResult; }

function getLabel(score: number) {
  if (score >= 0.75) return 'HIGH';
  if (score >= 0.50) return 'MEDIUM';
  return 'LOW';
}

function getMeta(label: string) {
  switch (label) {
    case 'HIGH': return { Icon: ShieldCheck, color: '#34d399', bg: 'rgba(52,211,153,0.08)', border: 'rgba(52,211,153,0.2)', bar: 'linear-gradient(90deg,#34d399,#6ee7b7)' };
    case 'MEDIUM': return { Icon: ShieldAlert, color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.2)', bar: 'linear-gradient(90deg,#fbbf24,#fde68a)' };
    default: return { Icon: ShieldX, color: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.2)', bar: 'linear-gradient(90deg,#f87171,#fca5a5)' };
  }
}

export default function VerificationCard({ verification }: Props) {
  const v = verification;
  const m = v.metrics;
  const label = getLabel(v.confidence_score);
  const meta = getMeta(label);
  const Icon = meta.Icon;
  const pct = Math.round(v.confidence_score * 100);
  const hasConflicts = m.conflicts_detected === true || (Array.isArray(m.conflicts_detected) && m.conflicts_detected.length > 0);
  const conflictDetails = Array.isArray(m.conflicts_detected) ? m.conflicts_detected : [];

  return (
    <div className="animate-fade-in" style={{ borderRadius: 13, border: `1px solid ${meta.border}`, background: meta.bg, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon size={18} style={{ color: meta.color }} />
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Verification Report</h3>
          <span style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Stage 4</span>
        </div>
        <span style={{ padding: '4px 12px', borderRadius: 16, fontSize: 13, fontWeight: 700, color: meta.color, background: `${meta.border}55`, border: `1px solid ${meta.border}` }}>
          {pct}% {label}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ paddingInline: 20, paddingBottom: 16 }}>
        <div style={{ height: 6, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
          <div style={{ height: '100%', borderRadius: 4, background: meta.bar, width: `${pct}%`, transition: 'width 1s ease-out' }} />
        </div>
      </div>

      {/* Metrics grid */}
      <div style={{ paddingInline: 20, paddingBottom: 16, display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 8 }}>
        {[
          { label: 'Avg. Similarity', val: (m.avg_similarity * 100).toFixed(1) + '%' },
          { label: 'Source Diversity', val: (m.normalized_source_diversity * 100).toFixed(1) + '%' },
          { label: 'Evidence Density', val: (m.evidence_density * 100).toFixed(1) + '%' },
          { label: 'Claims Used', val: String(v.audit.claims_used_for_scoring) },
        ].map(({ label: l, val }) => (
          <div key={l} style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{l}</p>
            <p style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>{val}</p>
          </div>
        ))}
      </div>

      {/* Warnings */}
      {v.warnings.length > 0 && (
        <div style={{ marginInline: 20, marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {v.warnings.map((w, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 8, background: 'rgba(251,191,36,0.1)', fontSize: 12, color: '#fbbf24' }}>
              <AlertTriangle size={12} style={{ flexShrink: 0 }} />{w}
            </div>
          ))}
        </div>
      )}

      {/* Conflicts */}
      {hasConflicts && (
        <div style={{ marginInline: 20, marginBottom: 12, padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(251,191,36,0.2)', background: 'rgba(251,191,36,0.07)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <AlertTriangle size={14} style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2 }} />
          <div>
            <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 600, color: '#fbbf24' }}>Conflicting evidence detected</p>
            {conflictDetails.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 14 }}>
                {conflictDetails.map((d, i) => <li key={i} style={{ fontSize: 12, color: '#fde68a', marginBottom: 2 }}>{d}</li>)}
              </ul>
            ) : (
              <p style={{ margin: 0, fontSize: 12, color: '#fde68a' }}>Multiple sources contain conflicting claims. Review evidence carefully.</p>
            )}
          </div>
        </div>
      )}

      {/* Audit log */}
      {v.audit && (
        <details className="group" style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          <summary style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer', listStyle: 'none' }}>
            <ChevronDown size={12} /> Filtering audit log
          </summary>
          <div style={{ padding: '4px 20px 16px', display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6 }}>
            {[
              ['Total received', v.audit.total_claims_received],
              ['After dedup', v.audit.claims_after_dedup],
              ['After relevance', v.audit.claims_after_relevance_filter],
              ['Above threshold', v.audit.claims_above_similarity_threshold],
              ['Used for scoring', v.audit.claims_used_for_scoring],
              ['Rejected', v.audit.claims_rejected],
            ].map(([l, val], i) => (
              <div key={String(l)} style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.04)' }}>
                <p style={{ margin: 0, fontSize: 9, color: 'var(--text-muted)', marginBottom: 2 }}>{l}</p>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: i === 5 ? '#f87171' : 'var(--text-primary)' }}>{val}</p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
