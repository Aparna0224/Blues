import { useState } from 'react';
import { BookOpen, TrendingUp, Brain, ChevronDown, Activity } from 'lucide-react';
import type { QueryResponse } from '../types';

interface Props {
    result: QueryResponse;
    showSummary?: boolean;
}

export default function AnalysisHealthPanel({ result, showSummary = true }: Props) {
    const [summaryOpen, setSummaryOpen] = useState(false);

    const papersCount = result.papers_found.length;
    const trustScore = result.verification?.confidence_score;
    const trustPct = trustScore != null ? (trustScore * 100).toFixed(0) : null;
    const trustColor = trustScore == null ? '#94a3b8' : trustScore >= 0.75 ? '#34d399' : trustScore >= 0.5 ? '#fbbf24' : '#f87171';

    return (
        <div className="animate-slide-right space-y-4">
            {/* ── Analysis Health ────────────────────────── */}
            <div className="glass-card overflow-hidden">
                <div className="accent-bar" />
                <div className="p-4">
                    <div className="flex items-center gap-2 mb-4">
                        <Activity size={14} style={{ color: 'var(--teal)' }} />
                        <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--teal)' }}>
                            Analysis Health
                        </span>
                    </div>

                    {/* Metric: Total Papers Cited */}
                    <div className="mb-5">
                        <p className="text-[10px] font-medium uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                            <BookOpen size={10} className="inline mr-1" />
                            Total Papers Cited
                        </p>
                        <div className="flex items-end gap-2">
                            <span className="text-4xl font-bold" style={{ color: 'var(--text-primary)' }}>
                                {papersCount}
                            </span>
                        </div>
                        <div className="mt-1.5 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                            <div
                                className="h-full rounded-full transition-all duration-1000"
                                style={{
                                    width: `${Math.min(papersCount * 4, 100)}%`,
                                    background: 'linear-gradient(90deg, var(--teal), var(--cyan))',
                                }}
                            />
                        </div>
                    </div>

                    {/* Metric: Trust Correlation */}
                    {trustPct != null && (
                        <div className="mb-5">
                            <p className="text-[10px] font-medium uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                                <TrendingUp size={10} className="inline mr-1" />
                                Trust Correlation
                            </p>
                            <div className="flex items-end gap-2">
                                <span className="text-4xl font-bold" style={{ color: trustColor }}>
                                    {(parseFloat(trustPct) / 100).toFixed(2)}
                                </span>
                            </div>
                            <div className="mt-1.5 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                                <div
                                    className="h-full rounded-full transition-all duration-1000"
                                    style={{ width: `${trustPct}%`, background: `linear-gradient(90deg, ${trustColor}, ${trustColor}88)` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Chunks used */}
                    <div className="flex items-center justify-between py-2 px-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Evidence chunks</span>
                        <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{result.chunks_used}</span>
                    </div>
                </div>
            </div>

            {/* ── AI Research Summary ────────────────────── */}
            {showSummary && result.summary && (
                <div className="glass-card overflow-hidden animate-fade-in">
                    <button
                        onClick={() => setSummaryOpen(!summaryOpen)}
                        className="w-full flex items-center justify-between p-4 text-left transition-colors"
                        style={{ background: summaryOpen ? 'rgba(94,234,212,0.05)' : 'transparent' }}
                    >
                        <div className="flex items-center gap-2">
                            <Brain size={14} style={{ color: 'var(--purple)' }} />
                            <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>AI Research Summary</span>
                        </div>
                        <ChevronDown
                            size={13}
                            style={{ color: 'var(--text-muted)', transform: summaryOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
                        />
                    </button>
                    {summaryOpen && (
                        <div className="px-4 pb-4 animate-fade-in">
                            <div className="prose text-sm leading-relaxed">
                                {result.summary.split('\n').map((line, i) =>
                                    line.trim() ? <p key={i}>{line}</p> : null
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
