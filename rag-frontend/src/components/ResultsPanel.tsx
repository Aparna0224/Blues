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
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 flex items-start justify-between flex-wrap gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 size={20} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-base font-semibold text-slate-900">Research Complete</p>
              <p className="text-sm text-slate-600 mt-1">"{r.query}"</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
              <Clock size={13} />
              {(r.total_time_ms / 1000).toFixed(1)}s
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
              <Layers size={13} />
              {r.chunks_used} chunks
            </span>
            <span className="px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-medium capitalize">
              {r.papers_found.length} papers
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
              className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3"
            >
              <AlertCircle size={16} className="shrink-0 text-amber-600 mt-0.5" />
              <p className="text-sm text-amber-800">{w}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Planning (sub-questions) ─────────────────────────── */}
      {r.planning.sub_questions.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
            <ListOrdered size={18} className="text-blue-600" />
            <h3 className="text-base font-semibold text-slate-900">Research Plan</h3>
          </div>
          <div className="px-6 py-5">
            <p className="text-sm text-slate-600 mb-4 italic">
              "{r.planning.main_question}"
            </p>
            <div className="space-y-2.5">
              {r.planning.sub_questions.map((sq, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-slate-700 pt-0.5">{sq}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Grouped Answer (Stage 3 output) ──────────────────── */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
          <FileSearch size={18} className="text-blue-600" />
          <h3 className="text-base font-semibold text-slate-900">Key Findings</h3>
        </div>
        <div className="px-6 py-5">
          <div className="prose prose-sm max-w-none">
            {r.grouped_answer.split('\n').map((line, i) => {
              if (!line.trim()) return null;
              if (line.startsWith('## ')) {
                return (
                  <h3 key={i} className="text-sm font-semibold text-slate-800 mt-4 mb-2 first:mt-0">
                    {line.replace(/^#+\s*/, '')}
                  </h3>
                );
              }
              if (line.startsWith('- ') || line.startsWith('• ')) {
                return (
                  <div key={i} className="flex items-start gap-2 mb-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-2 shrink-0" />
                    <p className="text-sm text-slate-700 m-0">{line.replace(/^[-•]\s*/, '')}</p>
                  </div>
                );
              }
              return <p key={i} className="text-sm text-slate-700">{line}</p>;
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
      <div className="text-center pt-4 border-t border-slate-200">
        <a 
          href={`/trace/${r.execution_id}`} 
          className="text-xs text-blue-600 hover:text-blue-700 font-mono"
        >
          View trace: {r.execution_id}
        </a>
      </div>
    </div>
  );
}
