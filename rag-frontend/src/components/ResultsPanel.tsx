import { Clock, Layers, AlertCircle } from 'lucide-react';
import type { QueryResponse } from '../types';
import VerificationCard from './VerificationCard';
import PapersTable from './PapersTable';
import SummaryPanel from './SummaryPanel';

interface Props {
  result: QueryResponse;
}

export default function ResultsPanel({ result }: Props) {
  const r = result;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Meta bar ─────────────────────────────────────────── */}
      <div className="flex items-center gap-4 flex-wrap text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <Clock size={13} />
          {(r.total_time_ms / 1000).toFixed(1)}s
        </span>
        <span className="flex items-center gap-1">
          <Layers size={13} />
          {r.chunks_used} chunks from {r.papers_found.length} papers
        </span>
        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 capitalize">
          {r.mode}
        </span>
        <span className="font-mono text-slate-400">
          {r.execution_id.slice(0, 8)}
        </span>
      </div>

      {/* ── Warnings ─────────────────────────────────────────── */}
      {r.warnings.length > 0 && (
        <div className="space-y-1">
          {r.warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm text-amber-800"
            >
              <AlertCircle size={14} className="shrink-0" />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* ── Planning (sub-questions) ─────────────────────────── */}
      {r.planning.sub_questions.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Research Plan
          </h3>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <p className="text-sm font-medium text-slate-700 mb-2">
              {r.planning.main_question}
            </p>
            <ol className="list-decimal pl-5 space-y-1 text-sm text-slate-600">
              {r.planning.sub_questions.map((sq, i) => (
                <li key={i}>{sq}</li>
              ))}
            </ol>
          </div>
        </section>
      )}

      {/* ── Grouped Answer (Stage 3 output) ──────────────────── */}
      <section>
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Research Findings
        </h3>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="prose text-sm text-slate-700">
            {r.grouped_answer.split('\n').map((line, i) => {
              if (!line.trim()) return null;
              // Detect sub-question headers (lines starting with ##)
              if (line.startsWith('## ')) {
                return (
                  <h3 key={i} className="text-base font-semibold text-slate-800 mt-4 mb-2 first:mt-0">
                    {line.replace(/^#+\s*/, '')}
                  </h3>
                );
              }
              if (line.startsWith('- ') || line.startsWith('• ')) {
                return (
                  <p key={i} className="pl-4 border-l-2 border-blue-200 text-slate-600 mb-1">
                    {line.replace(/^[-•]\s*/, '')}
                  </p>
                );
              }
              return <p key={i}>{line}</p>;
            })}
          </div>
        </div>
      </section>

      {/* ── Verification (Stage 4 — PRIMARY) ─────────────────── */}
      {r.verification && r.verification.confidence_score !== undefined && (
        <section>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Verification
          </h3>
          <VerificationCard verification={r.verification} />
        </section>
      )}

      {/* ── Papers Table ─────────────────────────────────────── */}
      {r.papers_found.length > 0 && (
        <section>
          <PapersTable papers={r.papers_found} />
        </section>
      )}

      {/* ── LLM Summary (Stage 5 — on demand) ───────────────── */}
      {r.summary && (
        <section>
          <SummaryPanel summary={r.summary} />
        </section>
      )}
    </div>
  );
}
