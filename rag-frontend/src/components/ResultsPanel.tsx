import { Clock, Layers, AlertCircle, CheckCircle2, ListOrdered, FileSearch } from 'lucide-react';
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
      {/* ── Success banner + meta ────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-lg shadow-slate-200/30 overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-emerald-500 via-blue-500 to-indigo-500" />
        <div className="px-6 py-4 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Analysis Complete</p>
              <p className="text-xs text-slate-400">{r.query}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200">
              <Clock size={11} />
              {(r.total_time_ms / 1000).toFixed(1)}s
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200">
              <Layers size={11} />
              {r.chunks_used} chunks · {r.papers_found.length} papers
            </span>
            <span className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 capitalize font-medium">
              {r.mode}
            </span>
          </div>
        </div>
      </div>

      {/* ── Warnings ─────────────────────────────────────────── */}
      {r.warnings.length > 0 && (
        <div className="space-y-2">
          {r.warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800"
            >
              <AlertCircle size={15} className="shrink-0 text-amber-500" />
              {w}
            </div>
          ))}
        </div>
      )}

      {/* ── Planning (sub-questions) ─────────────────────────── */}
      {r.planning.sub_questions.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
            <ListOrdered size={16} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-800">Research Plan</h3>
            <span className="ml-auto text-[10px] text-slate-400 font-medium uppercase tracking-wider">Stage 1</span>
          </div>
          <div className="px-6 py-4">
            <p className="text-sm font-medium text-slate-700 mb-3 italic">
              &ldquo;{r.planning.main_question}&rdquo;
            </p>
            <div className="space-y-2">
              {r.planning.sub_questions.map((sq, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="w-6 h-6 rounded-full bg-indigo-50 text-indigo-600 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-slate-600">{sq}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Grouped Answer (Stage 3 output) ──────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <FileSearch size={16} className="text-blue-500" />
          <h3 className="text-sm font-semibold text-slate-800">Research Findings</h3>
          <span className="ml-auto text-[10px] text-slate-400 font-medium uppercase tracking-wider">Stages 2–3</span>
        </div>
        <div className="px-6 py-5">
          <div className="prose text-sm text-slate-700">
            {r.grouped_answer.split('\n').map((line, i) => {
              if (!line.trim()) return null;
              if (line.startsWith('## ')) {
                return (
                  <h3 key={i} className="text-base font-semibold text-slate-800 mt-5 mb-2 first:mt-0 pb-1.5 border-b border-slate-100">
                    {line.replace(/^#+\s*/, '')}
                  </h3>
                );
              }
              if (line.startsWith('- ') || line.startsWith('• ')) {
                return (
                  <div key={i} className="flex items-start gap-2 pl-2 mb-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-2 shrink-0" />
                    <p className="text-slate-600 m-0">{line.replace(/^[-•]\s*/, '')}</p>
                  </div>
                );
              }
              return <p key={i}>{line}</p>;
            })}
          </div>
        </div>
      </div>

      {/* ── Verification (Stage 4 — PRIMARY) ─────────────────── */}
      {r.verification && r.verification.confidence_score !== undefined && (
        <VerificationCard verification={r.verification} />
      )}

      {/* ── Papers Table ─────────────────────────────────────── */}
      {r.papers_found.length > 0 && (
        <PapersTable papers={r.papers_found} />
      )}

      {/* ── LLM Summary (Stage 5 — on demand) ───────────────── */}
      {r.summary && (
        <SummaryPanel summary={r.summary} />
      )}

      {/* ── Trace ID footer ──────────────────────────────────── */}
      <div className="text-center">
        <span className="text-[10px] text-slate-400 font-mono">
          trace: {r.execution_id}
        </span>
      </div>
    </div>
  );
}
