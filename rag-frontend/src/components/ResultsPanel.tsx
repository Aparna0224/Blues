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

      {/* ── Inference & Extraction Details ──────────────────── */}
      {r.inference_summary && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="text-base font-semibold text-slate-900">🧠 Inference Extraction</h3>
            <p className="text-xs text-slate-600 mt-1">Inferences extracted from {r.chunks_used} chunks</p>
          </div>
          <div className="px-6 py-5 space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-blue-50 rounded-lg p-3">
                <p className="text-xs text-slate-600">Methodology Insights</p>
                <p className="text-lg font-bold text-blue-700">{r.inference_summary.methodology_insights_count}</p>
              </div>
              <div className="bg-green-50 rounded-lg p-3">
                <p className="text-xs text-slate-600">Experimental Findings</p>
                <p className="text-lg font-bold text-green-700">{r.inference_summary.experimental_findings_count}</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-3">
                <p className="text-xs text-slate-600">Inference Chains</p>
                <p className="text-lg font-bold text-purple-700">{r.inference_summary.inference_chains_count}</p>
              </div>
              <div className="bg-amber-50 rounded-lg p-3">
                <p className="text-xs text-slate-600">Confidence</p>
                <p className="text-lg font-bold text-amber-700">{(r.inference_summary.overall_confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Methodology Insights ────────────────────────────── */}
      {r.methodology_insights && r.methodology_insights.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="text-base font-semibold text-slate-900">📊 Methodology Insights</h3>
          </div>
          <div className="px-6 py-5 space-y-3">
            {r.methodology_insights.map((insight, i) => (
              <div key={i} className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                <p className="font-semibold text-slate-900 text-sm">{insight.technique}</p>
                {insight.assumptions && insight.assumptions.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-700 mb-1">Assumptions:</p>
                    <ul className="text-xs text-slate-600 space-y-1 ml-4">
                      {insight.assumptions.map((a, j) => <li key={j}>• {a}</li>)}
                    </ul>
                  </div>
                )}
                {insight.constraints && insight.constraints.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-700 mb-1">Constraints:</p>
                    <ul className="text-xs text-slate-600 space-y-1 ml-4">
                      {insight.constraints.map((c, j) => <li key={j}>• {c}</li>)}
                    </ul>
                  </div>
                )}
                <p className="text-xs text-slate-700 mt-2"><strong>Scope:</strong> {insight.scope}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Experimental Findings ───────────────────────────── */}
      {r.experimental_findings && r.experimental_findings.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="text-base font-semibold text-slate-900">🔬 Experimental Findings</h3>
          </div>
          <div className="px-6 py-5 space-y-3">
            {r.experimental_findings.map((finding, i) => (
              <div key={i} className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                <p className="font-semibold text-slate-900 text-sm">{finding.finding}</p>
                {Object.keys(finding.metrics).length > 0 && (
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(finding.metrics).map(([key, value]) => (
                      <div key={key} className="bg-white rounded p-2 border border-slate-200">
                        <p className="text-xs text-slate-600 capitalize">{key}</p>
                        <p className="font-semibold text-slate-900">{typeof value === 'number' ? value.toFixed(3) : value}</p>
                      </div>
                    ))}
                  </div>
                )}
                {finding.conditions && finding.conditions.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-700 mb-1">Conditions:</p>
                    <ul className="text-xs text-slate-600 space-y-1 ml-4">
                      {finding.conditions.map((c, j) => <li key={j}>• {c}</li>)}
                    </ul>
                  </div>
                )}
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-slate-700"><strong>Generalizability:</strong> {finding.generalizability}</span>
                  {finding.exceptions && <span className="text-xs text-amber-700 italic">⚠️ {finding.exceptions}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Inference Chains ────────────────────────────────── */}
      {r.inference_chains && r.inference_chains.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="text-base font-semibold text-slate-900">⛓️ Inference Chains</h3>
          </div>
          <div className="px-6 py-5 space-y-3">
            {r.inference_chains.map((chain, i) => (
              <div key={i} className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                <div className="flex items-start justify-between">
                  <p className="font-semibold text-slate-900 text-sm flex-1">{chain.claim}</p>
                  <span className={`ml-3 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${
                    chain.confidence >= 0.8 ? 'bg-green-100 text-green-700' :
                    chain.confidence >= 0.6 ? 'bg-amber-100 text-amber-700' :
                    'bg-orange-100 text-orange-700'
                  }`}>
                    {(chain.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {chain.inference_path && chain.inference_path.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-700 mb-1">Inference Path:</p>
                    <ol className="text-xs text-slate-600 space-y-1 ml-4 list-decimal">
                      {chain.inference_path.map((step, j) => <li key={j}>{step}</li>)}
                    </ol>
                  </div>
                )}
                {chain.methodology_support && (
                  <p className="text-xs text-slate-700 mt-2"><strong>Methodology Support:</strong> {chain.methodology_support}</p>
                )}
                {chain.limitation && (
                  <p className="text-xs text-amber-700 mt-2 italic">⚠️ <strong>Limitation:</strong> {chain.limitation}</p>
                )}
                {chain.implication && (
                  <p className="text-xs text-slate-700 mt-2"><strong>Implication:</strong> {chain.implication}</p>
                )}
              </div>
            ))}
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
