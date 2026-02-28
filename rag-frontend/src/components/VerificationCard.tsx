import { ShieldCheck, ShieldAlert, ShieldX, AlertTriangle, Info } from 'lucide-react';
import type { VerificationResult } from '../types';

interface Props {
  verification: VerificationResult;
}

function getConfidenceMeta(label: string) {
  switch (label) {
    case 'HIGH':
      return { icon: ShieldCheck, color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200', bar: 'bg-green-500' };
    case 'MEDIUM':
      return { icon: ShieldAlert, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', bar: 'bg-amber-500' };
    default:
      return { icon: ShieldX, color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200', bar: 'bg-red-500' };
  }
}

export default function VerificationCard({ verification }: Props) {
  const v = verification;
  const meta = getConfidenceMeta(v.confidence_label);
  const Icon = meta.icon;
  const pct = Math.round(v.confidence_score * 100);

  return (
    <div className={`rounded-xl border ${meta.border} ${meta.bg} p-5 animate-fade-in`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Icon size={22} className={meta.color} />
          <h3 className="font-semibold text-slate-800">Verification Report</h3>
        </div>
        <span className={`text-lg font-bold ${meta.color}`}>
          {pct}% {v.confidence_label}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-white/60 rounded-full mb-5 overflow-hidden">
        <div
          className={`h-full rounded-full ${meta.bar} transition-all duration-700`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <MetricBox label="Similarity" value={v.similarity_score} />
        <MetricBox label="Diversity" value={v.diversity_score} suffix={` / ${v.unique_papers} papers`} />
        <MetricBox label="Evidence Density" value={v.evidence_density} />
        <MetricBox label="Total Claims" value={v.total_claims} isInt />
      </div>

      {/* Conflict warning */}
      {v.conflict_detected && v.conflict_details.length > 0 && (
        <div className="flex items-start gap-2 bg-amber-100 rounded-lg p-3 mb-4">
          <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-medium mb-1">Conflicting evidence detected</p>
            <ul className="list-disc pl-4 space-y-0.5">
              {v.conflict_details.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Audit accordion */}
      {v.audit && <AuditDetails audit={v.audit} />}
    </div>
  );
}

/* ── Small metric box ────────────────────────────────────────── */

function MetricBox({
  label,
  value,
  isInt = false,
  suffix = '',
}: {
  label: string;
  value: number;
  isInt?: boolean;
  suffix?: string;
}) {
  const display = isInt ? value : (value * 100).toFixed(1) + '%';
  return (
    <div className="bg-white/70 rounded-lg p-3 text-center">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-lg font-semibold text-slate-800">
        {display}
        {suffix && <span className="text-xs font-normal text-slate-400">{suffix}</span>}
      </p>
    </div>
  );
}

/* ── Audit details (collapsible) ─────────────────────────────── */

function AuditDetails({ audit }: { audit: Props['verification']['audit'] }) {
  return (
    <details className="group">
      <summary className="flex items-center gap-1.5 text-xs font-medium text-slate-500 cursor-pointer select-none hover:text-slate-700">
        <Info size={13} />
        Filtering audit
        <span className="ml-auto text-slate-400 group-open:rotate-180 transition-transform">▾</span>
      </summary>
      <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-slate-600">
        <AuditItem label="Received" value={audit.total_claims_received} />
        <AuditItem label="After dedup" value={audit.claims_after_dedup} />
        <AuditItem label="After relevance" value={audit.claims_after_relevance_filter} />
        <AuditItem label="Above sim threshold" value={audit.claims_above_similarity_threshold} />
        <AuditItem label="Rejected" value={audit.claims_rejected} highlight />
        <AuditItem
          label="Calibration"
          value={audit.calibration_applied ? `${audit.calibration_multiplier}×` : 'none'}
        />
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
    <div className="bg-white/50 rounded px-2 py-1.5">
      <span className="text-slate-400">{label}: </span>
      <span className={highlight ? 'font-semibold text-red-600' : 'font-medium'}>
        {value}
      </span>
    </div>
  );
}
