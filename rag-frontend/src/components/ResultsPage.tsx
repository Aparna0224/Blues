import { useState } from 'react';
import { ChevronDown, Download, FileText, Copy, CheckCircle2 } from 'lucide-react';
import type { QueryResponse } from '../types';
import VerificationCard from './VerificationCard';
import PapersTable from './PapersTable';
import SummaryPanel from './SummaryPanel';

interface Props {
  result: QueryResponse;
  onBack: () => void;
}

export default function ResultsPage({ result, onBack }: Props) {
  const r = result;
  const [expandedSections, setExpandedSections] = useState<{ [key: string]: boolean }>({
    research_plan: true,
    findings: true,
    verification: true,
    papers: false,
    summary: false,
  });
  const [copied, setCopied] = useState(false);

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const downloadAsJSON = () => {
    const dataStr = JSON.stringify(r, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `research-result-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadAsMarkdown = () => {
    let md = `# Research Results\n\n`;
    md += `**Query:** ${r.query}\n\n`;
    md += `**Execution Time:** ${(r.total_time_ms / 1000).toFixed(1)}s\n`;
    md += `**Documents:** ${r.chunks_used} chunks from ${r.papers_found.length} papers\n\n`;

    if (r.planning.sub_questions.length > 0) {
      md += `## Research Plan\n\n`;
      md += `**Main Question:** ${r.planning.main_question}\n\n`;
      r.planning.sub_questions.forEach((sq, i) => {
        md += `${i + 1}. ${sq}\n`;
      });
      md += '\n';
    }

    md += `## Key Findings\n\n${r.grouped_answer}\n\n`;

    if (r.verification) {
      md += `## Verification Results\n\n`;
      md += `**Confidence Score:** ${Math.round(r.verification.confidence_score * 100)}%\n`;
    }

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `research-result-${new Date().toISOString().split('T')[0]}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = () => {
    const text = `${r.query}\n\n${r.grouped_answer}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="px-4 py-2 rounded-lg text-slate-700 hover:bg-slate-100 font-medium transition-colors"
            >
              ← Back
            </button>
            <div className="border-l border-slate-200 pl-4">
              <h1 className="text-xl font-bold text-slate-900">Research Results</h1>
              <p className="text-sm text-slate-500 mt-1">"{r.query}"</p>
            </div>
          </div>

          {/* Export Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={copyToClipboard}
              className="p-2.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
              title="Copy to clipboard"
            >
              {copied ? <CheckCircle2 size={20} className="text-green-600" /> : <Copy size={20} />}
            </button>
            <div className="flex gap-1 border-l border-slate-200 pl-2">
              <button
                onClick={downloadAsJSON}
                className="p-2.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
                title="Download as JSON"
              >
                <FileText size={20} />
              </button>
              <button
                onClick={downloadAsMarkdown}
                className="p-2.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
                title="Download as Markdown"
              >
                <Download size={20} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 lg:px-8 py-12 space-y-4">
        
        {/* Meta Info */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-xs font-semibold text-slate-600 uppercase">Execution Time</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{(r.total_time_ms / 1000).toFixed(1)}s</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-xs font-semibold text-slate-600 uppercase">Evidence</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{r.chunks_used} chunks</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-xs font-semibold text-slate-600 uppercase">Sources</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{r.papers_found.length} papers</p>
          </div>
        </div>

        {/* Research Plan Section */}
        {r.planning.sub_questions.length > 0 && (
          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
            <button
              onClick={() => toggleSection('research_plan')}
              className="w-full px-6 py-5 flex items-center justify-between hover:bg-slate-50 transition-colors border-b border-slate-200"
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-green-600" />
                <h2 className="text-lg font-semibold text-slate-900">Research Plan</h2>
                <span className="text-xs font-medium text-slate-500 ml-2">
                  {r.planning.sub_questions.length} questions
                </span>
              </div>
              <ChevronDown
                size={20}
                className={`transition-transform ${
                  expandedSections['research_plan'] ? 'rotate-180' : ''
                } text-slate-600`}
              />
            </button>
            {expandedSections['research_plan'] && (
              <div className="px-6 py-5 space-y-4">
                <p className="text-slate-700 italic">
                  Main Question: <strong>"{r.planning.main_question}"</strong>
                </p>
                <ol className="space-y-2 ml-4">
                  {r.planning.sub_questions.map((sq, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="font-semibold text-green-600 min-w-fit">{i + 1}.</span>
                      <span className="text-slate-700">{sq}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}

        {/* Key Findings Section */}
        <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
          <button
            onClick={() => toggleSection('findings')}
            className="w-full px-6 py-5 flex items-center justify-between hover:bg-slate-50 transition-colors border-b border-slate-200"
          >
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-600" />
              <h2 className="text-lg font-semibold text-slate-900">Key Findings</h2>
            </div>
            <ChevronDown
              size={20}
              className={`transition-transform ${
                expandedSections['findings'] ? 'rotate-180' : ''
              } text-slate-600`}
            />
          </button>
          {expandedSections['findings'] && (
            <div className="px-6 py-5 prose prose-sm max-w-none">
              {r.grouped_answer.split('\n').map((line, i) => {
                if (!line.trim()) return null;
                if (line.startsWith('## ')) {
                  return (
                    <h3 key={i} className="font-semibold text-slate-900 mt-5 mb-3 text-base">
                      {line.replace(/^#+\s*/, '')}
                    </h3>
                  );
                }
                if (line.startsWith('- ') || line.startsWith('• ')) {
                  return (
                    <div key={i} className="flex gap-3 mb-2">
                      <span className="text-green-600 font-bold">•</span>
                      <p className="text-slate-700 m-0">{line.replace(/^[-•]\s*/, '')}</p>
                    </div>
                  );
                }
                return (
                  <p key={i} className="text-slate-700 mb-2">
                    {line}
                  </p>
                );
              })}
            </div>
          )}
        </div>

        {/* 5-Section Answer Display (NEW) */}
        {r.answer_structure === '5-section' && (
          <div className="border-2 border-green-200 rounded-lg overflow-hidden bg-green-50">
            <div className="px-6 py-5 bg-green-100 border-b border-green-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-green-600" />
                  <h2 className="text-lg font-bold text-green-900">Refined 5-Section Answer</h2>
                </div>
                {r.answer_confidence !== undefined && (
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-semibold text-green-800">
                      {Math.round((r.answer_confidence || 0) * 100)}% Confidence
                    </div>
                    <div className="w-32 h-2 bg-white rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-600 transition-all"
                        style={{ width: `${(r.answer_confidence || 0) * 100}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="p-6 space-y-4">
              {/* Inference Summary */}
              {r.inference_summary && (
                <div className="grid grid-cols-3 gap-3 p-4 bg-white rounded-lg border border-green-200">
                  <div className="text-center">
                    <p className="text-xs font-semibold text-slate-600 uppercase">Insights</p>
                    <p className="text-2xl font-bold text-green-600">
                      {r.inference_summary.methodology_insights_count}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-slate-600 uppercase">Findings</p>
                    <p className="text-2xl font-bold text-green-600">
                      {r.inference_summary.experimental_findings_count}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-slate-600 uppercase">Chains</p>
                    <p className="text-2xl font-bold text-green-600">
                      {r.inference_summary.inference_chains_count}
                    </p>
                  </div>
                </div>
              )}

              {/* 5 Sections */}
              {r.five_section_answer && [
                { key: 'executive_summary', title: '1. Executive Summary', icon: '📋' },
                { key: 'detailed_analysis', title: '2. Detailed Analysis', icon: '🔍' },
                { key: 'methodology', title: '3. Methodology', icon: '🔬' },
                { key: 'implications', title: '4. Implications', icon: '💡' },
                { key: 'research_gaps', title: '5. Research Gaps', icon: '❓' },
              ].map((section, idx) => {
                const sectionKey = section.key as keyof typeof r.five_section_answer;
                const content = r.five_section_answer?.[sectionKey];
                if (!content) return null;

                return (
                  <div key={idx} className="border border-green-200 rounded-lg overflow-hidden bg-white">
                    <button
                      onClick={() => toggleSection(`section_${idx}`)}
                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-green-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">{section.icon}</span>
                        <h3 className="font-semibold text-slate-900">{section.title}</h3>
                      </div>
                      <ChevronDown
                        size={18}
                        className={`transition-transform ${
                          expandedSections[`section_${idx}`] ? 'rotate-180' : ''
                        } text-slate-600`}
                      />
                    </button>
                    {expandedSections[`section_${idx}`] && (
                      <div className="px-4 py-4 border-t border-green-200 bg-green-50 prose prose-sm max-w-none">
                        {content.split('\n').map((line: string, i: number) => {
                          if (!line.trim()) return null;
                          if (line.startsWith('- ') || line.startsWith('• ')) {
                            return (
                              <div key={i} className="flex gap-3 mb-2">
                                <span className="text-green-600 font-bold">•</span>
                                <p className="text-slate-700 m-0">{line.replace(/^[-•]\s*/, '')}</p>
                              </div>
                            );
                          }
                          return (
                            <p key={i} className="text-slate-700 mb-2 leading-relaxed">
                              {line}
                            </p>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Verification Section */}
        {r.verification && r.verification.confidence_score !== undefined && (
          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
            <button
              onClick={() => toggleSection('verification')}
              className="w-full px-6 py-5 flex items-center justify-between hover:bg-slate-50 transition-colors border-b border-slate-200"
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-green-600" />
                <h2 className="text-lg font-semibold text-slate-900">Verification & Confidence</h2>
              </div>
              <ChevronDown
                size={20}
                className={`transition-transform ${
                  expandedSections['verification'] ? 'rotate-180' : ''
                } text-slate-600`}
              />
            </button>
            {expandedSections['verification'] && (
              <div className="px-6 py-5">
                <VerificationCard verification={r.verification} />
              </div>
            )}
          </div>
        )}

        {/* Papers Section */}
        {r.papers_found.length > 0 && (
          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
            <button
              onClick={() => toggleSection('papers')}
              className="w-full px-6 py-5 flex items-center justify-between hover:bg-slate-50 transition-colors border-b border-slate-200"
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-green-600" />
                <h2 className="text-lg font-semibold text-slate-900">Source Papers</h2>
                <span className="text-xs font-medium text-slate-500 ml-2">
                  {r.papers_found.length} papers
                </span>
              </div>
              <ChevronDown
                size={20}
                className={`transition-transform ${
                  expandedSections['papers'] ? 'rotate-180' : ''
                } text-slate-600`}
              />
            </button>
            {expandedSections['papers'] && (
              <div className="px-6 py-5">
                <PapersTable papers={r.papers_found} />
              </div>
            )}
          </div>
        )}

        {/* Summary Section */}
        {r.summary && (
          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
            <button
              onClick={() => toggleSection('summary')}
              className="w-full px-6 py-5 flex items-center justify-between hover:bg-slate-50 transition-colors border-b border-slate-200"
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-green-600" />
                <h2 className="text-lg font-semibold text-slate-900">AI Summary</h2>
              </div>
              <ChevronDown
                size={20}
                className={`transition-transform ${
                  expandedSections['summary'] ? 'rotate-180' : ''
                } text-slate-600`}
              />
            </button>
            {expandedSections['summary'] && (
              <div className="px-6 py-5">
                <SummaryPanel summary={r.summary} />
              </div>
            )}
          </div>
        )}

        {/* Trace Footer */}
        <div className="text-center pt-8 border-t border-slate-200 mt-12">
          <p className="text-xs text-slate-500 font-mono">
            Execution Trace ID: {r.execution_id}
          </p>
        </div>
      </main>
    </div>
  );
}
