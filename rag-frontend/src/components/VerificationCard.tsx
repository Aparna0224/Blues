import { ShieldCheck, ShieldAlert, ShieldX, AlertTriangle, ChevronDown } from 'lucide-react';
import type { VerificationResult } from '../types';

interface Props {
  verification: VerificationResult;
}

function getConfidenceLabel(score: number): string {
  if (score >= 0.75) return 'HIGH';
  if (score >= 0.50) return 'MEDIUM';
  return 'LOW';
}

function getConfidenceMeta(label: string) {
  switch (label) {
    case 'HIGH':
      return {
        icon: ShieldCheck,
        color: 'text-emerald-700',
        bg: 'from-emerald-50 to-green-50',
        border: 'border-emerald-200',
        bar: 'from-emerald-500 to-green-400',
        badge: 'bg-emerald-100 text-emerald-800',
      };
    case 'MEDIUM':
      return {
        icon: ShieldAlert,
        color: 'text-amber-700',
        bg: 'from-amber-50 to-yellow-50',
        border: 'border-amber-200',
        bar: 'from-amber-500 to-yellow-400',
        badge: 'bg-amber-100 text-amber-800',
      };
    default:
      return {
        icon: ShieldX,
        color: 'text-red-700',
        bg: 'from-red-50 to-rose-50',
        border: 'border-red-200',
        bar: 'from-red-500 to-rose-400',
        badge: 'bg-red-100 text-red-800',
      };
  }
}

export default function VerificationCard({ verification }: Props) {
  const v = verification;
  const m = v.metrics;
  const confidenceLabel = getConfidenceLabel(v.confidence_score);
  const meta = getConfidenceMeta(confidenceLabel);
  const Icon = meta.icon;
  const pct = Math.round(v.confidence_score * 100);
  const conflicts = m.conflicts_detected ?? [];

  return (
    <div className={`rounded-2xl border ${meta.border} bg-gradient-to-br ${meta.bg} overflow-hidden shadow-sm animate-fade-in`}>
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Icon size={20} className={meta.color} />
          <h3 className="text-sm font-semibold text-slate-800">Verification Report</h3>
          <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Stage 4</span>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-bold ${meta.badge}`}>
          {pct}% {confidenceLabel}
        </span>
      </div>

      {/* Progress bar */}
      <div className="px-6 pb-5">
        <div className="w-full h-2.5 bg-white/70 rounded-full overflow-hidden shadow-inner">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${meta.bar} transition-all duration-1000 ease-out`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Metric grid */}
      <div className="px-6 pb-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricBox label="Avg. Similarity" value={m.avg_similarity} />
        <MetricBox label="Source Diversity" value={m.normalized_source_diversity} suffix={`${m.source_diversity} papers`} />
        <MetricBox label="Evidence Density" value={m.evidence_density} />
        <MetricBox label="Claims Used" value={v.audit.claims_used_for_scoring} isInt />
      </div>

      {/* Warnings */}
      {v.warnings.length > 0 && (
        <div className="mx-6 mb-4 space-y-2">
          {v.warnings.map((w, i) => (
            <div key={i} className="flex items-center gap-2 bg-amber-100/80 rounded-lg px-3 py-2 text-sm text-amber-800">
              <AlertTriangle size={14} className="text-amber-500 shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Conflict warning */}
      {conflicts.length > 0 && (
        <div className="mx-6 mb-4 flex items-start gap-2.5 bg-amber-100/80 rounded-xl p-4">
          <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold mb-1">Conflicting evidence detected</p>
            <ul className="space-y-0.5 text-amber-700">
              {conflicts.map((d, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-amber-400 mt-1">•</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Audit details */}
      {v.audit && <AuditDetails audit={v.audit} />}
    </div>
  );
}

/* ── Metric box ──────────────────────────────────────────────── */

function MetricBox({
  label,
  value,
  isInt = false,
  suffix,
}: {
  label: string;
  value: number;
  isInt?: boolean;
  suffix?: string;
}) {
  const display = isInt ? String(value) : (value * 100).toFixed(1) + '%';
  return (
    <div className="bg-white/60 backdrop-blur-sm rounded-xl p-3.5 text-center border border-white/80">
      <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-800">{display}</p>
      {suffix && <p className="text-[10px] text-slate-400 mt-0.5">{suffix}</p>}
    </div>
  );
}

/* ── Audit details ───────────────────────────────────────────── */

function AuditDetails({ audit }: { audit: Props['verification']['audit'] }) {
  return (
    <details className="group border-t border-white/60">
      <summary className="px-6 py-3 flex items-center gap-1.5 text-xs font-medium text-slate-500 cursor-pointer select-none hover:text-slate-700">
        <ChevronDown size={13} className="transition-transform group-open:rotate-180" />
        Filtering audit log
      </summary>
      <div className="px-6 pb-4 grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-600">
        <AuditItem label="Total received" value={audit.total_claims_received} />
        <AuditItem label="After dedup" value={audit.claims_after_dedup} />
        <AuditItem label="After relevance" value={audit.claims_after_relevance_filter} />
        <AuditItem label="Above similarity" value={audit.claims_above_similarity_threshold} />
        <AuditItem label="Used for scoring" value={audit.claims_used_for_scoring} />
        <AuditItem label="Rejected" value={audit.claims_rejected} highlight />
      </div>
    </details>
  );
}

function AuditItem({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number | string;
  highlight?: boolean;
}) {
  return (
    <div className="bg-white/50 rounded-lg px-3 py-2">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p className={`text-sm font-semibold ${highlight ? 'text-red-600' : 'text-slate-700'}`}>
        {value}
      </p>
    </div>
  );
}
