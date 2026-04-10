import { useMemo, useState } from 'react';
import {
  Clock, Layers, AlertCircle, ChevronDown, ChevronRight,
  FileText, File, TriangleAlert, BarChart3, Brain, ScrollText,
} from 'lucide-react';
import type { QueryResponse } from '../types';
import VerificationCard from './VerificationCard';
import PapersTable from './PapersTable';
import { downloadReport, extractErrorMessage } from '../services/api';
import { useWorkspace } from '../state/workspace';

interface Props { result: QueryResponse; }

interface ParsedEvidenceUnit {
  section: string;
  location: string;
  relevance: string;
  subqSimilarity: string;
  confidence: string;
  confidenceBand: string;
  text: string;
}
interface ParsedPaper { title: string; units: ParsedEvidenceUnit[]; }
interface ParsedSubQuestion {
  title: string;
  papers: ParsedPaper[];
  conflict: string;
  comparison: string;
  synthesis: string;
}

function confidenceBadgeClass(band: string): string {
  const b = band.toLowerCase();
  if (b.includes('high')) return 'badge-high';
  if (b.includes('medium')) return 'badge-medium';
  return 'badge-low';
}

function parseGroupedAnswer(text: string): ParsedSubQuestion[] {
  const sections = text.split(/🔹\s*Sub-question:?/).slice(1);
  const parsed: ParsedSubQuestion[] = [];
  for (const sec of sections) {
    const trimmed = sec.trim();
    if (!trimmed) continue;

    const firstLineBreak = trimmed.indexOf('\n');
    const title = (firstLineBreak >= 0 ? trimmed.slice(0, firstLineBreak) : trimmed).trim();

    const paperBlocks = trimmed.split(/📄\s*Paper:?/).slice(1);
    const papers: ParsedPaper[] = [];
    for (const pb of paperBlocks) {
      const ptrim = pb.trim();
      if (!ptrim) continue;
      const pLineBreak = ptrim.indexOf('\n');
      const paperTitle = (pLineBreak >= 0 ? ptrim.slice(0, pLineBreak) : ptrim).trim();

      const units: ParsedEvidenceUnit[] = [];
      const unitRegex = /\[(\d+)\]\s*Section:\s*(.+?)\n\s*Location:\s*(.+?)(?:\n\[[^\]]+\])*\n\s*Relevance:\s*([0-9.]+)\s*\|?\s*SubQ\s*Similarity:\s*([0-9.]+)\s*\|?\s*Confidence:\s*([0-9.]+)\s*\((.+?)\)\s*(?:\n)+Text:\s*\n\s*"([\s\S]*?)"\s*(?=(?:\n)+---)/g;
      let m: RegExpExecArray | null;
      const regexState = { lastIndex: 0 };
      while ((m = unitRegex.exec(ptrim)) !== null) {
        regexState.lastIndex = unitRegex.lastIndex;
        units.push({
          section: m[2].trim(),
          location: m[3].trim(),
          relevance: m[4].trim(),
          subqSimilarity: m[5].trim(),
          confidence: m[6].trim(),
          confidenceBand: m[7].trim(),
          text: m[8].trim(),
        });
      }
      
      if (units.length === 0) {
        const fallbackUnitRegex = /\[\d+\][^\n]*\n[^\n]*(?:\n\[[^\]]+\])*(?:\n)+Text:\s*\n\s*"([\s\S]*?)"\s*(?=(?:\n)+---)/g;
        let fm: RegExpExecArray | null;
        while ((fm = fallbackUnitRegex.exec(ptrim)) !== null) {
          units.push({
            section: 'unknown',
            location: 'unknown',
            relevance: '0.00',
            subqSimilarity: '0.00',
            confidence: '0.00',
            confidenceBand: 'Unknown',
            text: fm[1].trim(),
          });
        }
      }
      papers.push({ title: paperTitle, units });
    }

    const conflictStart = trimmed.search(/⚠️\s*Cross-Paper\s*Conflict/);
    const comparisonStart = trimmed.search(/📊\s*Comparison\s*Summary/);
    const synthesisStart = trimmed.search(/🧩\s*Final\s*Synthesis/);

    let conflict = '';
    let comparison = '';
    let synthesis = '';

    if (conflictStart >= 0) {
      const endIdx = comparisonStart > conflictStart ? comparisonStart : (synthesisStart > conflictStart ? synthesisStart : trimmed.length);
      conflict = trimmed.slice(conflictStart, endIdx).trim();
    }
    if (comparisonStart >= 0) {
      const endIdx = synthesisStart > comparisonStart ? synthesisStart : trimmed.length;
      comparison = trimmed.slice(comparisonStart, endIdx).trim();
    }
    if (synthesisStart >= 0) {
      synthesis = trimmed.slice(synthesisStart).trim();
    }

    parsed.push({ title, papers, conflict, comparison, synthesis });
  }
  
  if (parsed.length === 0 && text.trim()) {
    parsed.push({
      title: 'Research Synthesis',
      papers: [{
        title: 'Results',
        units: [{
          section: 'results',
          location: 'unknown',
          relevance: '0.00',
          subqSimilarity: '0.00',
          confidence: '0.00',
          confidenceBand: 'Unknown',
          text: text.slice(0, 500),
        }],
      }],
      conflict: '',
      comparison: '',
      synthesis: '',
    });
  }
  return parsed;
}

const card: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 10,
};

const subCard: React.CSSProperties = { ...card, overflow: 'hidden', marginBottom: 14 };

// ── Structured Summary Parser (Phase 5) ────────────────────────

const SECTION_DELIMITER = '━━━';

interface SummarySection {
  icon: React.ReactNode;
  title: string;
  type: 'topic' | 'comparison' | 'cross' | 'synthesis' | 'generic';
  content: string;
}

function parseSummarySections(text: string): SummarySection[] | null {
  if (!text) return null;

  // Clean legacy formatting artifacts from older queries
  let cleanText = text.replace(/={5,}\s*(📝\s*)?RESEARCH SUMMARY\s*={5,}/gi, '');
  cleanText = cleanText.replace(/RESEARCH SUMMARY/gi, '');

  if (!cleanText.includes(SECTION_DELIMITER)) return null;

  const parts = cleanText.split(/━{3,}/);
  const sections: SummarySection[] = [];

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Detect section type from emoji/header
    if (trimmed.includes('TOPIC OVERVIEW') || /TOPIC OVERVIEW/i.test(trimmed)) {
      sections.push({ icon: <FileText size={15} />, title: 'Topic Overview', type: 'topic', content: trimmed.replace(/(🔬\s*)?TOPIC OVERVIEW\s*/i, '').trim() });
    } else if (trimmed.includes('PAPER-BY-PAPER') || /PAPER.BY.PAPER/i.test(trimmed)) {
      sections.push({ icon: <BarChart3 size={15} />, title: 'Paper-by-Paper Comparison', type: 'comparison', content: trimmed.replace(/(📊\s*)?PAPER.BY.PAPER COMPARISON\s*/i, '').trim() });
    } else if (trimmed.includes('CROSS-PAPER') || /CROSS.PAPER/i.test(trimmed)) {
      sections.push({ icon: <Layers size={15} />, title: 'Cross-Paper Analysis', type: 'cross', content: trimmed.replace(/(🔁\s*)?CROSS.PAPER ANALYSIS\s*/i, '').trim() });
    } else if (trimmed.includes('SYNTHESIS') || /SYNTHESIS/i.test(trimmed)) {
      sections.push({ icon: <Brain size={15} />, title: 'Synthesis & Research Direction', type: 'synthesis', content: trimmed.replace(/(💡\s*)?SYNTHESIS.*?\n/i, '').trim() });
    } else if (trimmed.includes('Pipeline Confidence')) {
      // Confidence badge line — skip, handled separately
      continue;
    } else if (trimmed.length > 20) {
      sections.push({ icon: <ScrollText size={15} />, title: 'Analysis', type: 'generic', content: trimmed });
    }
  }

  return sections.length > 0 ? sections : null;
}

function extractConfidenceBadge(text: string): { score: string; level: string } | null {
  const match = text.match(/Pipeline Confidence:\s*([0-9.]+)\s*\((\w+)\)/);
  if (!match) return null;
  return { score: match[1], level: match[2] };
}

function renderSectionContent(section: SummarySection) {
  const paragraphs = section.content.split(/\n{2,}/).filter(Boolean);

  if (section.type === 'comparison') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {paragraphs.map((p, i) => (
          <div key={i} className="paper-card">
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, fontFamily: 'var(--font-display)' }}>
              {p}
            </p>
          </div>
        ))}
      </div>
    );
  }

  if (section.type === 'cross') {
    return (
      <div className="callout-cross-analysis">
        {paragraphs.map((p, i) => (
          <p key={i} style={{ margin: i < paragraphs.length - 1 ? '0 0 8px' : 0, fontFamily: 'var(--font-display)' }}>{p}</p>
        ))}
      </div>
    );
  }

  if (section.type === 'synthesis') {
    return (
      <div className="callout-synthesis">
        {paragraphs.map((p, i) => (
          <p key={i} style={{ margin: i < paragraphs.length - 1 ? '0 0 8px' : 0, fontFamily: 'var(--font-display)' }}>{p}</p>
        ))}
      </div>
    );
  }

  return (
    <div>
      {paragraphs.map((p, i) => (
        <p key={i} style={{ margin: i < paragraphs.length - 1 ? '0 0 8px' : 0, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, fontFamily: 'var(--font-display)' }}>{p}</p>
      ))}
    </div>
  );
}



function FinalAISummary({ summary }: { summary: string }) {
  const sections = parseSummarySections(summary);
  const confidence = extractConfidenceBadge(summary);

  // Fallback: render as single prose block if no structured sections
  if (!sections) {
    return (
      <p style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, fontFamily: 'var(--font-display)' }}>
        {summary}
      </p>
    );
  }

  return (
    <div>
      {sections.map((section, idx) => (
        <div key={idx} className="summary-section">
          <div className={`summary-section-header ${section.type}`}>
            <span>{section.icon}</span>
            <span>{section.title}</span>
          </div>
          {renderSectionContent(section)}
        </div>
      ))}

      {confidence && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`confidence-badge-${confidence.level.toLowerCase()}`}>
            Confidence Score: {confidence.score} — {confidence.level}
          </span>
        </div>
      )}
    </div>
  );
}

export default function ResultsPanel({ result }: Props) {
  const r = result;
  const { currentProject, currentQuery } = useWorkspace();
  const parsed = useMemo(() => parseGroupedAnswer(r.grouped_answer), [r.grouped_answer]);
  const [openSubq, setOpenSubq] = useState<Record<number, boolean>>({});
  const [downloading, setDownloading] = useState<'pdf' | 'md' | null>(null);
  const [downloadError, setDownloadError] = useState('');

  const toggleSubq = (idx: number) => setOpenSubq(prev => ({ ...prev, [idx]: !prev[idx] }));

  const onDownload = async (format: 'pdf' | 'md') => {
    setDownloadError('');
    setDownloading(format);
    try {
      await downloadReport(r.execution_id, format, {
        projectName: currentProject?.name,
        queryText: currentQuery?.query_text || r.query,
        timestamp: currentQuery?.timestamp,
      });
    } catch (err: unknown) {
      setDownloadError(extractErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  };

  const confidenceValue = r.verification?.confidence_score || 0;
  const confidenceBand = confidenceValue >= 0.75 ? 'High' : confidenceValue >= 0.6 ? 'Medium' : 'Low';

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ ...card, overflow: 'hidden' }}>
        <div style={{ padding: '22px 26px 18px', borderBottom: '1px solid var(--border)' }}>
          <p style={{ margin: '0 0 10px', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--text-muted)' }}>
            Research Synthesis — {new Date().toLocaleDateString()}
          </p>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 56, lineHeight: 1, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
            {r.planning.main_question || r.query}
          </h1>
        </div>

        <div style={{ padding: '14px 26px', display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 12 }}>
          <div>
            <p style={{ margin: '0 0 4px', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Confidence Score</p>
            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 12 }} className={confidenceBadgeClass(confidenceBand)}>
              {Math.round(confidenceValue * 100)}% {confidenceBand.toUpperCase()}
            </span>
          </div>
          <div>
            <p style={{ margin: '0 0 4px', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Verified Sources</p>
            <p style={{ margin: 0, fontSize: 14, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>{r.papers_found.length} referenced papers</p>
          </div>
          <div>
            <p style={{ margin: '0 0 4px', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Primary Analyst</p>
            <p style={{ margin: 0, fontSize: 14, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>Blues Engine</p>
          </div>
        </div>
      </div>

      <div style={{ ...card, padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '4px 8px', borderRadius: 12, border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            <Clock size={10} /> {(r.total_time_ms / 1000).toFixed(1)}s
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '4px 8px', borderRadius: 12, border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            <Layers size={10} /> {r.chunks_used} chunks
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button id="export-btn" onClick={() => onDownload('pdf')} disabled={downloading !== null}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 11px', borderRadius: 7, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
            <File size={11} />{downloading === 'pdf' ? 'Preparing…' : 'Download PDF'}
          </button>
          <button onClick={() => onDownload('md')} disabled={downloading !== null}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 11px', borderRadius: 7, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
            <FileText size={11} />{downloading === 'md' ? 'Preparing…' : 'Download Markdown'}
          </button>
        </div>
      </div>

      {downloadError && (
        <div style={{ padding: '8px 12px', fontSize: 11, color: '#b42318', background: 'rgba(180,35,24,0.08)', border: '1px solid rgba(180,35,24,0.2)', borderRadius: 8 }}>
          {downloadError}
        </div>
      )}

      {r.warnings.length > 0 && r.warnings.map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(180,35,24,0.2)', background: 'rgba(180,35,24,0.06)', fontSize: 13, color: '#b42318' }}>
          <AlertCircle size={14} style={{ flexShrink: 0 }} />{w}
        </div>
      ))}

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 18, alignItems: 'start' }}>
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 10 }}>
          <div style={{ ...card, padding: '12px 14px' }}>
            <p style={{ margin: '0 0 6px', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Abstract</p>
            <p style={{ margin: 0, fontSize: 12, lineHeight: 1.7, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
              This synthesis organizes evidence by sub-question, highlights methodological patterns, and surfaces conflict signals across papers.
            </p>
          </div>

          <div style={{ ...card, padding: '12px 14px' }}>
            <p style={{ margin: '0 0 6px', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Conflict Resolution Map</p>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
              Contradictory claims are flagged and explained with type + strength for interpretability.
            </p>
          </div>
        </aside>

        <main>
          {parsed.map((sub, idx) => {
            const open = openSubq[idx] ?? true;
            return (
              <section key={idx} style={subCard}>
                <button
                  onClick={() => toggleSubq(idx)}
                  style={{ width: '100%', padding: '13px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', borderBottom: open ? '1px solid var(--border)' : 'none' }}
                >
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{String(idx + 1).padStart(2, '0')}</span>
                  <span style={{ flex: 1, marginLeft: 10, fontSize: 20, fontFamily: 'var(--font-display)', color: 'var(--text-primary)', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sub.title}</span>
                  {open ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
                </button>

                {open && (
                  <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {sub.papers.map((paper, pIdx) => (
                      <article key={pIdx} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', background: '#fff' }}>
                        <h3 style={{ margin: '0 0 10px', fontSize: 20, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
                          📄 {paper.title}
                        </h3>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                          {paper.units.map((u, uIdx) => (
                            <div key={uIdx} style={{ padding: '10px 12px', borderRadius: 7, background: '#f7f8fa', border: '1px solid var(--border)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 7, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 12 }} className="badge-neutral">{u.section}</span>
                                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 12 }} className={confidenceBadgeClass(u.confidenceBand)}>{u.confidenceBand}</span>
                                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{u.location}</span>
                              </div>
                              <p style={{ margin: '0 0 6px', fontSize: 10, color: 'var(--text-muted)' }}>
                                Relevance: {u.relevance} · SubQ Similarity: {u.subqSimilarity} · Confidence: {u.confidence}
                              </p>
                              <p style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, fontFamily: 'var(--font-display)' }}>{u.text}</p>
                            </div>
                          ))}
                        </div>
                      </article>
                    ))}

                    {sub.conflict && (
                      <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(180,35,24,0.28)', background: 'rgba(180,35,24,0.05)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: '#b42318' }}>
                          <TriangleAlert size={13} /> ⚠ Conflict Analysis
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: '#7a1f17', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{sub.conflict}</p>
                      </div>
                    )}

                    {sub.comparison && (
                      <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(15,38,92,0.18)', background: 'rgba(15,38,92,0.04)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: '#0f265c' }}>
                          <BarChart3 size={13} /> 📊 Comparison Summary
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{sub.comparison}</p>
                      </div>
                    )}

                    {sub.synthesis && (
                      <div style={{ padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(29,121,72,0.2)', background: 'rgba(29,121,72,0.05)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12, fontWeight: 600, color: '#1d7948' }}>
                          <Brain size={13} /> 🧠 Final Synthesis
                        </div>
                        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{sub.synthesis}</p>
                      </div>
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </main>
      </div>

      {r.summary && (
        <div style={{ ...card, padding: '14px 18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 12, fontWeight: 600, color: '#0f265c' }}>
            <ScrollText size={13} /> Final AI Summary
          </div>
          <FinalAISummary summary={r.summary} />
        </div>
      )}

      <div style={{ ...card, padding: '14px 18px' }}>
        <p style={{ margin: '0 0 8px', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Evidence Repository</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 12 }}>
          <div>
            <p style={{ margin: '0 0 5px', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Scientific Papers</p>
            {r.papers_found.slice(0, 4).map((p, i) => (
              <p key={p.paper_id || i} style={{ margin: '0 0 4px', fontSize: 12, color: 'var(--text-secondary)' }}>📄 {p.title} ({p.year})</p>
            ))}
          </div>
          <div>
            <p style={{ margin: '0 0 5px', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Methodology</p>
            <p style={{ margin: '0 0 4px', fontSize: 12, color: 'var(--text-secondary)' }}>• Hybrid BM25 + Semantic + RRF</p>
            <p style={{ margin: '0 0 4px', fontSize: 12, color: 'var(--text-secondary)' }}>• Sub-question evidence mapping</p>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>• Conflict trace verification</p>
          </div>
          <div>
            <p style={{ margin: '0 0 5px', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Session</p>
            <p style={{ margin: '0 0 4px', fontSize: 12, color: 'var(--text-secondary)' }}>Execution ID: {r.execution_id}</p>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>Mode: {r.mode}</p>
          </div>
        </div>
      </div>

      {r.verification && r.verification.confidence_score !== undefined && <VerificationCard verification={r.verification} />}
      {r.papers_found.length > 0 && <PapersTable papers={r.papers_found} />}
    </div>
  );
}
