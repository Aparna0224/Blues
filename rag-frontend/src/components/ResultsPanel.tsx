import { useMemo, useState } from 'react';
import {
  Clock, Layers, AlertCircle, CheckCircle2, ListOrdered,
  FileSearch, ChevronDown, ChevronRight, Download,
  FileText, File, TriangleAlert, BarChart3, Brain,
} from 'lucide-react';
import type { QueryResponse } from '../types';
import VerificationCard from './VerificationCard';
import PapersTable from './PapersTable';
import { downloadReport, extractErrorMessage } from '../services/api';

interface Props { result: QueryResponse; }

interface ParsedEvidenceUnit {
  section: string; location: string; relevance: string;
  subqSimilarity: string; confidence: string; confidenceBand: string; text: string;
}
interface ParsedPaper { title: string; units: ParsedEvidenceUnit[]; }
interface ParsedSubQuestion { title: string; papers: ParsedPaper[]; conflict: string; comparison: string; synthesis: string; }

function confidenceBadgeClass(band: string): string {
  const b = band.toLowerCase();
  if (b.includes('high')) return 'badge-high';
  if (b.includes('medium')) return 'badge-medium';
  return 'badge-low';
}

function parseGroupedAnswer(text: string): ParsedSubQuestion[] {
  const sections = text.split('🔹 Sub-question:').slice(1);
  const parsed: ParsedSubQuestion[] = [];
  for (const sec of sections) {
    const trimmed = sec.trim();
    if (!trimmed) continue;
    const firstLineBreak = trimmed.indexOf('\n');
    const title = (firstLineBreak >= 0 ? trimmed.slice(0, firstLineBreak) : trimmed).trim();
    const paperBlocks = trimmed.split('📄 Paper:').slice(1);
    const papers: ParsedPaper[] = [];
    for (const pb of paperBlocks) {
      const ptrim = pb.trim();
      if (!ptrim) continue;
      const pLineBreak = ptrim.indexOf('\n');
      const paperTitle = (pLineBreak >= 0 ? ptrim.slice(0, pLineBreak) : ptrim).trim();
      const units: ParsedEvidenceUnit[] = [];
      const unitRegex = /\[(\d+)\] Section:\s*(.+?)\nLocation:\s*(.+?)\nRelevance:\s*([0-9.]+)\s*\|\s*SubQ Similarity:\s*([0-9.]+)\s*\|\s*Confidence:\s*([0-9.]+)\s*\((.+?)\)\n\nText:\n"([\s\S]*?)"/g;
      let m: RegExpExecArray | null;
      while ((m = unitRegex.exec(ptrim)) !== null) {
        units.push({ section: m[2].trim(), location: m[3].trim(), relevance: m[4].trim(), subqSimilarity: m[5].trim(), confidence: m[6].trim(), confidenceBand: m[7].trim(), text: m[8].trim() });
      }
      papers.push({ title: paperTitle, units });
    }
    const conflictStart = trimmed.indexOf('⚠️ Cross-Paper Conflict Analysis');
    const comparisonStart = trimmed.indexOf('📊 Comparison Summary');
    const synthesisStart = trimmed.indexOf('🧩 Final Synthesis');
    let conflict = '', comparison = '', synthesis = '';
    if (conflictStart >= 0 && comparisonStart > conflictStart) conflict = trimmed.slice(conflictStart, comparisonStart).trim();
    if (comparisonStart >= 0 && synthesisStart > comparisonStart) comparison = trimmed.slice(comparisonStart, synthesisStart).trim();
    if (synthesisStart >= 0) { const end = trimmed.indexOf('🔹 Sub-question:', synthesisStart); synthesis = (end > synthesisStart ? trimmed.slice(synthesisStart, end) : trimmed.slice(synthesisStart)).trim(); }
    parsed.push({ title, papers, conflict, comparison, synthesis });
  }
  return parsed;
}

const card: React.CSSProperties = { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12 };
const subCard: React.CSSProperties = { ...card, overflow: 'hidden', marginBottom: 10 };

export default function ResultsPanel({ result }: Props) {
  const r = result;
  const parsed = useMemo(() => parseGroupedAnswer(r.grouped_answer), [r.grouped_answer]);
  const [openSubq, setOpenSubq] = useState<Record<number, boolean>>({});
  const [downloading, setDownloading] = useState<'pdf' | 'md' | null>(null);
  const [downloadError, setDownloadError] = useState('');

  const toggleSubq = (idx: number) => setOpenSubq(prev => ({ ...prev, [idx]: !prev[idx] }));

  const onDownload = async (format: 'pdf' | 'md') => {
    setDownloadError('');
    setDownloading(format);
    try { await downloadReport(r.execution_id, format); }
    catch (err: unknown) { setDownloadError(extractErrorMessage(err)); }
    finally { setDownloading(null); }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Status bar */}
      <div style={{ ...card, overflow: 'hidden' }}>
        <div className="accent-bar" />
        <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 9, background: 'rgba(52,211,153,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CheckCircle2 size={15} style={{ color: '#34d399' }} />
            </div>
            <div>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Analysis Complete</p>
              <p style={{ margin: 0, fontSize: 11, color: 'var(--text-muted)' }}>{r.query}</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '4px 10px', borderRadius: 16, border: '1px solid var(--border)', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.03)' }}>
              <Clock size={10} /> {(r.total_time_ms / 1000).toFixed(1)}s
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '4px 10px', borderRadius: 16, border: '1px solid var(--border)', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.03)' }}>
              <Layers size={10} /> {r.chunks_used} chunks · {r.papers_found.length} papers
            </span>
            <span style={{ fontSize: 11, padding: '4px 10px', borderRadius: 16, border: '1px solid rgba(94,234,212,0.25)', color: 'var(--teal)', background: 'rgba(94,234,212,0.08)', textTransform: 'capitalize', fontWeight: 600 }}>
              {r.mode}
            </span>

            {/* Download buttons */}
            <button id="export-btn" onClick={() => onDownload('pdf')} disabled={downloading !== null}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
              <File size={11} />{downloading === 'pdf' ? 'Preparing…' : 'PDF'}
            </button>
            <button onClick={() => onDownload('md')} disabled={downloading !== null}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
              <FileText size={11} />{downloading === 'md' ? 'Preparing…' : 'Markdown'}
            </button>
            <Download size={13} style={{ color: 'var(--text-muted)', display: 'none' }} />
          </div>
        </div>
        {downloadError && <div style={{ padding: '8px 20px', fontSize: 11, color: '#fca5a5', background: 'rgba(248,113,113,0.08)', borderTop: '1px solid rgba(248,113,113,0.15)' }}>{downloadError}</div>}
      </div>

      {/* Warnings */}
      {r.warnings.length > 0 && r.warnings.map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderRadius: 10, border: '1px solid rgba(251,191,36,0.2)', background: 'rgba(251,191,36,0.08)', fontSize: 13, color: '#fbbf24' }}>
          <AlertCircle size={14} style={{ flexShrink: 0 }} />{w}
        </div>
      ))}

      {/* Research Plan */}
      {r.planning.sub_questions.length > 0 && (
        <div style={card}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ListOrdered size={15} style={{ color: 'var(--indigo)' }} />
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Research Plan</h3>
          </div>
          <div style={{ padding: '14px 20px' }}>
            <p style={{ margin: '0 0 12px', fontSize: 13, fontStyle: 'italic', color: 'var(--text-secondary)' }}>"{r.planning.main_question}"</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {r.planning.sub_questions.map((sq, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(129,140,248,0.12)', color: 'var(--indigo)', fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>{i + 1}</span>
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{sq}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Research Findings */}
      <div style={card}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileSearch size={15} style={{ color: 'var(--cyan)' }} />
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Research Findings</h3>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {parsed.map((sub, idx) => {
            const open = openSubq[idx] ?? true;
            return (
              <div key={idx} style={subCard}>
                {/* Sub-question header */}
                <button
                  onClick={() => toggleSubq(idx)}
                  style={{ width: '100%', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.03)', border: 'none', cursor: 'pointer', textAlign: 'left', borderBottom: open ? '1px solid var(--border)' : 'none' }}
                >
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{sub.title}</span>
                  {open ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
                </button>

                {open && (
                  <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {/* Papers */}
                    {sub.papers.map((paper, pIdx) => (
                      <div key={pIdx} style={{ border: '1px solid rgba(255,255,255,0.07)', borderRadius: 10, padding: '12px 14px', background: 'rgba(255,255,255,0.02)' }}>
                        <p style={{ margin: '0 0 10px', fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 6, background: 'rgba(56,189,248,0.1)', color: 'var(--cyan)', border: '1px solid rgba(56,189,248,0.2)', marginRight: 8 }}>
                            Source Paper
                          </span>
                          {paper.title}
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {paper.units.map((u, uIdx) => (
                            <div key={uIdx} style={{ padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 12 }} className="badge-neutral">{u.section}</span>
                                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 12 }} className={confidenceBadgeClass(u.confidenceBand)}>{u.confidenceBand}</span>
                                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{u.location}</span>
                              </div>
                              <p style={{ margin: '0 0 5px', fontSize: 10, color: 'var(--text-muted)' }}>
                                Relevance: {u.relevance} · SubQ Sim: {u.subqSimilarity} · Conf: {u.confidence}
                              </p>
                              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{u.text}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}

                    {/* Conflict */}
                    {sub.conflict && (
                      <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(251,191,36,0.2)', background: 'rgba(251,191,36,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: '#fbbf24' }}>
                          <TriangleAlert size={13} /> Conflict
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: '#fde68a', whiteSpace: 'pre-wrap' }}>{sub.conflict}</p>
                      </div>
                    )}
                    {/* Comparison */}
                    {sub.comparison && (
                      <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(56,189,248,0.15)', background: 'rgba(56,189,248,0.05)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: 'var(--cyan)' }}>
                          <BarChart3 size={13} /> Comparison
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: '#bae6fd', whiteSpace: 'pre-wrap' }}>{sub.comparison}</p>
                      </div>
                    )}
                    {/* Synthesis */}
                    {sub.synthesis && (
                      <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(167,139,250,0.15)', background: 'rgba(167,139,250,0.05)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: 'var(--purple)' }}>
                          <Brain size={13} /> Synthesis
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: '#ddd6fe', whiteSpace: 'pre-wrap' }}>{sub.synthesis}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {r.verification && r.verification.confidence_score !== undefined && <VerificationCard verification={r.verification} />}
      {r.papers_found.length > 0 && <PapersTable papers={r.papers_found} />}

      <div style={{ textAlign: 'center' }}>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'monospace' }}>trace: {r.execution_id}</span>
      </div>
    </div>
  );
}
