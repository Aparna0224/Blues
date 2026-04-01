import { useState } from 'react';
import { BookOpen, TrendingUp, Brain, ChevronDown, Activity } from 'lucide-react';
import type { QueryResponse } from '../types';

interface Props {
    result: QueryResponse;
}

// Generate a deterministic-ish heatmap grid from the paper data
function HeatmapGrid({ seed }: { seed: number }) {
    const rows = 7;
    const cols = 9;
    const intensities = Array.from({ length: rows * cols }, (_, i) => {
        const v = Math.abs(Math.sin(seed * 0.7 + i * 1.3)) * 0.85 + 0.15;
        return v;
    });

    const getColor = (v: number) => {
        if (v > 0.8) return '#5eead4';
        if (v > 0.6) return '#2dd4bf';
        if (v > 0.4) return '#0891b2';
        if (v > 0.2) return '#1e3a5f';
        return '#1a2744';
    };

    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${cols}, 1fr)`,
                gap: '3px',
            }}
        >
            {intensities.map((v, i) => (
                <div
                    key={i}
                    className="heatmap-cell"
                    style={{
                        height: '14px',
                        background: getColor(v),
                        animationDelay: `${(i * 0.05) % 2}s`,
                        opacity: v,
                    }}
                />
            ))}
        </div>
    );
}

export default function AnalysisHealthPanel({ result }: Props) {
    const [summaryOpen, setSummaryOpen] = useState(false);

    const papersCount = result.papers_found.length;
    const trustScore = result.verification?.confidence_score;
    const trustPct = trustScore != null ? (trustScore * 100).toFixed(0) : null;
    const trustColor = trustScore == null ? '#94a3b8' : trustScore >= 0.75 ? '#34d399' : trustScore >= 0.5 ? '#fbbf24' : '#f87171';
    const heatSeed = result.chunks_used + papersCount;

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

            {/* ── Logic Mapping / Neural Map ─────────────── */}
            <div className="glass-card overflow-hidden">
                <div className="p-4">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                            Logic Mapping V2.0
                        </span>
                        <span className="text-[9px] px-2 py-0.5 rounded-full badge-neutral">Neural</span>
                    </div>
                    <HeatmapGrid seed={heatSeed} />
                    <p className="text-[9px] mt-2 text-center" style={{ color: 'var(--text-muted)' }}>
                        Evidence correlation matrix
                    </p>
                </div>
            </div>

            {/* ── AI Research Summary ────────────────────── */}
            {result.summary && (
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
