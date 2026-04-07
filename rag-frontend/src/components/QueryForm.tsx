import { useState } from 'react';
import { Search, Settings2, Zap, Database, Sparkles, Filter } from 'lucide-react';
import type { QueryRequest, QueryFilters } from '../types';

interface Props {
  onSubmit: (req: QueryRequest) => void;
  loading: boolean;
}

export default function QueryForm({ onSubmit, loading }: Props) {
  const [query, setQuery] = useState('');
  const [userLevel, setUserLevel] = useState<'auto' | 'beginner' | 'intermediate' | 'advanced'>('auto');
  const [numDocs, setNumDocs] = useState(10);
  const [mode, setMode] = useState<'dynamic' | 'cached'>('dynamic');
  const [paperSource, setPaperSource] = useState<'openalex' | 'semantic_scholar' | 'arxiv' | 'both' | 'all'>('all');
  const [includeSummary, setIncludeSummary] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [filterSection, setFilterSection] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterTags, setFilterTags] = useState('');
  const [filterYearMin, setFilterYearMin] = useState('');
  const [filterYearMax, setFilterYearMax] = useState('');
  const [filterTitleContains, setFilterTitleContains] = useState('');
  const [filterSource, setFilterSource] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    const filters: QueryFilters = {};
    if (filterSection) filters.section = filterSection;
    if (filterCategory) filters.category = filterCategory;
    if (filterTags.trim()) {
      filters.tags = filterTags.split(',').map(t => t.trim()).filter(Boolean);
    }
    if (filterYearMin || filterYearMax) {
      filters.year = {};
      if (filterYearMin) filters.year.min = Number(filterYearMin);
      if (filterYearMax) filters.year.max = Number(filterYearMax);
    }
    if (filterTitleContains) filters.title_contains = filterTitleContains;
    if (filterSource) filters.source = filterSource;

    onSubmit({
      query: query.trim(),
      num_documents: numDocs,
      mode,
      paper_source: paperSource,
      include_summary: includeSummary,
      user_level: userLevel,
      filters: Object.keys(filters).length ? filters : undefined,
    });
  };

  const inputBase: React.CSSProperties = {
    width: '100%', padding: '8px 12px', borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
    color: 'var(--text-primary)', fontSize: 13, outline: 'none',
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* ── Main search row ── */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Ask a research question…"
            disabled={loading}
            style={{
              ...inputBase,
              paddingLeft: 40, paddingRight: 16,
              paddingTop: 13, paddingBottom: 13,
              fontSize: 14,
              border: '1px solid rgba(255,255,255,0.09)',
              background: 'rgba(255,255,255,0.04)',
              transition: 'border-color 0.15s',
            }}
          />
        </div>

        {/* Dynamic mode toggle pill */}
        <button
          type="button"
          onClick={() => setMode(m => m === 'dynamic' ? 'cached' : 'dynamic')}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '10px 14px',
            borderRadius: 9, border: '1px solid rgba(94,234,212,0.25)',
            background: mode === 'dynamic' ? 'rgba(94,234,212,0.1)' : 'rgba(255,255,255,0.05)',
            color: mode === 'dynamic' ? 'var(--teal)' : 'var(--text-muted)',
            cursor: 'pointer', fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', transition: 'all 0.15s',
          }}
        >
          {mode === 'dynamic' ? <Zap size={12} /> : <Database size={12} />}
          {mode === 'dynamic' ? 'Dynamic Mode' : 'Cached Mode'}
        </button>

        {/* Run Analysis button */}
        <button
          type="submit"
          disabled={!query.trim() || loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 7, padding: '11px 20px',
            borderRadius: 9, border: 'none', cursor: (!query.trim() || loading) ? 'not-allowed' : 'pointer',
            background: (!query.trim() || loading) ? 'rgba(94,234,212,0.25)' : 'linear-gradient(135deg, #5eead4, #38bdf8)',
            color: '#0b0f1e', fontWeight: 700, fontSize: 13, whiteSpace: 'nowrap', transition: 'all 0.15s',
            opacity: (!query.trim() || loading) ? 0.5 : 1,
          }}
        >
          {loading ? (
            <>
              <span style={{ width: 12, height: 12, border: '2px solid rgba(11,15,30,0.3)', borderTop: '2px solid #0b0f1e', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
              Running…
            </>
          ) : (
            <>Run Analysis</>
          )}
        </button>

        {/* Advanced toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          style={{
            width: 38, height: 38, borderRadius: 9, border: '1px solid rgba(255,255,255,0.1)',
            background: showAdvanced ? 'rgba(94,234,212,0.08)' : 'rgba(255,255,255,0.03)',
            color: showAdvanced ? 'var(--teal)' : 'var(--text-muted)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.15s',
          }}
          title="Pipeline options"
        >
          <Settings2 size={14} />
        </button>
      </div>

      <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '200px 1fr', gap: 10, alignItems: 'center' }}>
        <label style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>Research Level</label>
        <div>
          <select
            value={userLevel}
            onChange={e => setUserLevel(e.target.value as 'auto' | 'beginner' | 'intermediate' | 'advanced')}
            disabled={loading}
            style={{ ...inputBase, fontSize: 12, maxWidth: 220 }}
          >
            <option value="auto">Auto</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
          <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--text-muted)' }}>
            Auto infers depth from your query; choose manually for more control.
          </p>
        </div>
      </div>

      {/* ── Advanced panel ── */}
      {showAdvanced && (
        <div className="animate-fade-in" style={{ marginTop: 14, padding: 18, borderRadius: 12, border: '1px solid rgba(255,255,255,0.07)', background: 'rgba(255,255,255,0.03)' }}>
          {/* Num docs slider */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8 }}>
              <span>Documents to retrieve</span>
              <span style={{ padding: '0 8px', borderRadius: 12, background: 'rgba(94,234,212,0.15)', color: 'var(--teal)', fontSize: 11, fontWeight: 700 }}>{numDocs}</span>
            </label>
            <input type="range" min={1} max={50} value={numDocs} onChange={e => setNumDocs(Number(e.target.value))} style={{ width: '100%' }} />
          </div>

          {/* Include summary toggle */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 9, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={13} style={{ color: 'var(--purple)' }} />
              <div>
                <p style={{ margin: 0, fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>AI Research Summary</p>
                <p style={{ margin: 0, fontSize: 10, color: 'var(--text-muted)' }}>Generate narrative (Stage 5)</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIncludeSummary(!includeSummary)}
              style={{
                position: 'relative', width: 38, height: 21, borderRadius: 12, border: 'none',
                background: includeSummary ? 'var(--teal)' : 'rgba(255,255,255,0.15)', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0,
              }}
            >
              <span style={{
                position: 'absolute', top: 3, left: 3, width: 15, height: 15, borderRadius: '50%', background: '#fff',
                transition: 'transform 0.2s', transform: includeSummary ? 'translateX(17px)' : 'none',
              }} />
            </button>
          </div>

          {/* Paper source */}
          <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '200px 1fr', gap: 10, alignItems: 'center' }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>Paper Source</label>
            <select
              value={paperSource}
              onChange={e => setPaperSource(e.target.value as 'openalex' | 'semantic_scholar' | 'arxiv' | 'both' | 'all')}
              disabled={loading || mode !== 'dynamic'}
              style={{ ...inputBase, fontSize: 12, maxWidth: 260 }}
            >
              <option value="all">All (OpenAlex + Semantic Scholar + arXiv)</option>
              <option value="openalex">OpenAlex</option>
              <option value="semantic_scholar">Semantic Scholar</option>
              <option value="arxiv">arXiv</option>
              <option value="both">OpenAlex + Semantic Scholar</option>
            </select>
          </div>

          {/* Metadata filters */}
          <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 9, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10 }}>
              <Filter size={11} /> Metadata Filters
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                {
                  label: 'Section',
                  isSelect: true,
                  options: ['Any', 'abstract', 'introduction', 'related_work', 'methodology', 'dataset', 'results', 'discussion', 'limitations', 'conclusion', 'body'],
                  val: filterSection,
                  set: setFilterSection,
                  optVals: ['', 'abstract', 'introduction', 'related_work', 'methodology', 'dataset', 'results', 'discussion', 'limitations', 'conclusion', 'body'],
                },
                { label: 'Category', isSelect: false, placeholder: 'e.g., rag', val: filterCategory, set: setFilterCategory },
                { label: 'Tags', isSelect: false, placeholder: 'comma-separated', val: filterTags, set: setFilterTags },
                { label: 'Title contains', isSelect: false, placeholder: 'keyword', val: filterTitleContains, set: setFilterTitleContains },
                { label: 'Source', isSelect: false, placeholder: 'journal or database', val: filterSource, set: setFilterSource },
              ].map(({ label, isSelect, val, set, placeholder, options, optVals }) => (
                <div key={label}>
                  <label style={{ display: 'block', fontSize: 10, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</label>
                  {isSelect ? (
                    <select value={val} onChange={e => set(e.target.value)} style={{ ...inputBase, fontSize: 12 }}>
                      {(options || []).map((o: string, i: number) => <option key={o} value={(optVals || [])[i]}>{o}</option>)}
                    </select>
                  ) : (
                    <input type="text" value={val} onChange={e => set(e.target.value)} placeholder={placeholder} style={{ ...inputBase, fontSize: 12 }} />
                  )}
                </div>
              ))}
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 4 }}>Year min</label>
                <input type="number" value={filterYearMin} onChange={e => setFilterYearMin(e.target.value)} placeholder="2018" style={{ ...inputBase, fontSize: 12 }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 4 }}>Year max</label>
                <input type="number" value={filterYearMax} onChange={e => setFilterYearMax(e.target.value)} placeholder="2024" style={{ ...inputBase, fontSize: 12 }} />
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </form>
  );
}
