import { useState } from 'react';
import { Search, Settings2, Zap, Database, Sparkles, ArrowRight, Filter } from 'lucide-react';
import type { QueryRequest, QueryFilters } from '../types';

interface Props {
  onSubmit: (req: QueryRequest) => void;
  loading: boolean;
}

export default function QueryForm({ onSubmit, loading }: Props) {
  const [query, setQuery] = useState('');
  const [numDocs, setNumDocs] = useState(10);
  const [mode, setMode] = useState<'dynamic' | 'cached'>('dynamic');
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
      filters.tags = filterTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
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
      include_summary: includeSummary,
      filters: Object.keys(filters).length ? filters : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Main search input */}
      <div className="relative group">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-500 transition-colors"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are the main approaches to explainable AI in medical diagnosis?"
          disabled={loading}
          className="w-full pl-11 pr-32 py-4 rounded-xl border border-slate-200
                     bg-slate-50/50 text-sm text-slate-900 placeholder:text-slate-400
                     focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-400
                     focus:bg-white disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all"
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="absolute right-2 top-1/2 -translate-y-1/2
                     inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg
                     bg-gradient-to-r from-blue-600 to-indigo-600 text-white
                     hover:from-blue-700 hover:to-indigo-700 active:from-blue-800 active:to-indigo-800
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all shadow-md shadow-blue-600/20 hover:shadow-lg hover:shadow-blue-600/30"
        >
          {loading ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Running…
            </>
          ) : (
            <>
              Search
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </div>

      {/* Options toggle */}
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg
                     transition-all ${
                       showAdvanced
                         ? 'bg-blue-50 text-blue-700 border border-blue-200'
                         : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-transparent'
                     }`}
        >
          <Settings2 size={13} />
          Pipeline Options
        </button>
      </div>

      {/* Advanced options panel */}
      {showAdvanced && (
        <div className="bg-slate-50/80 border border-slate-200 rounded-xl p-5 space-y-5 animate-fade-in">
          {/* Num documents */}
          <div>
            <label className="flex items-center justify-between text-sm font-medium text-slate-700 mb-3">
              <span>Documents to retrieve</span>
              <span className="text-xs font-semibold text-white bg-blue-600 px-2.5 py-0.5 rounded-full">
                {numDocs}
              </span>
            </label>
            <input
              type="range"
              min={1}
              max={50}
              value={numDocs}
              onChange={(e) => setNumDocs(Number(e.target.value))}
              className="w-full accent-blue-600 h-1.5"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-1 px-0.5">
              <span>1</span>
              <span>10</span>
              <span>25</span>
              <span>50</span>
            </div>
          </div>

          {/* Mode toggle */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2.5">
              Retrieval mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setMode('dynamic')}
                className={`flex items-center gap-2 px-4 py-3 rounded-xl border text-left transition-all ${
                  mode === 'dynamic'
                    ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-200'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <Zap size={16} className={mode === 'dynamic' ? 'text-blue-600' : 'text-slate-400'} />
                <div>
                  <p className={`text-sm font-medium ${mode === 'dynamic' ? 'text-blue-900' : 'text-slate-700'}`}>
                    Dynamic
                  </p>
                  <p className="text-[11px] text-slate-400">Live OpenAlex + full text</p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setMode('cached')}
                className={`flex items-center gap-2 px-4 py-3 rounded-xl border text-left transition-all ${
                  mode === 'cached'
                    ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-200'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <Database size={16} className={mode === 'cached' ? 'text-blue-600' : 'text-slate-400'} />
                <div>
                  <p className={`text-sm font-medium ${mode === 'cached' ? 'text-blue-900' : 'text-slate-700'}`}>
                    Cached
                  </p>
                  <p className="text-[11px] text-slate-400">Pre-built FAISS index</p>
                </div>
              </button>
            </div>
          </div>

          {/* Include summary toggle */}
          <div className="flex items-center justify-between py-3 px-4 bg-white rounded-xl border border-slate-200">
            <div className="flex items-center gap-2.5">
              <Sparkles size={16} className="text-purple-500" />
              <div>
                <p className="text-sm font-medium text-slate-700">AI Research Summary</p>
                <p className="text-[11px] text-slate-400">Generate a narrative summary (Stage 5)</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIncludeSummary(!includeSummary)}
              className={`relative w-10 h-[22px] rounded-full transition-colors ${
                includeSummary ? 'bg-blue-600' : 'bg-slate-200'
              }`}
            >
              <span className={`absolute top-[3px] left-[3px] w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
                includeSummary ? 'translate-x-[18px]' : ''
              }`} />
            </button>
          </div>

          {/* Metadata filters */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Filter size={14} className="text-slate-500" />
              Metadata Filters
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Section</label>
                <select
                  value={filterSection}
                  onChange={(e) => setFilterSection(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                >
                  <option value="">Any</option>
                  <option value="abstract">Abstract</option>
                  <option value="body">Body</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Category</label>
                <input
                  type="text"
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  placeholder="e.g., rag, retrieval"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Tags</label>
                <input
                  type="text"
                  value={filterTags}
                  onChange={(e) => setFilterTags(e.target.value)}
                  placeholder="comma-separated tags"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Title contains</label>
                <input
                  type="text"
                  value={filterTitleContains}
                  onChange={(e) => setFilterTitleContains(e.target.value)}
                  placeholder="keyword in title"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Year min</label>
                <input
                  type="number"
                  value={filterYearMin}
                  onChange={(e) => setFilterYearMin(e.target.value)}
                  placeholder="2018"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Year max</label>
                <input
                  type="number"
                  value={filterYearMax}
                  onChange={(e) => setFilterYearMax(e.target.value)}
                  placeholder="2024"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Source</label>
                <select
                  value={filterSource}
                  onChange={(e) => setFilterSource(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                >
                  <option value="">Any</option>
                  <option value="openalex">OpenAlex</option>
                  <option value="semantic_scholar">Semantic Scholar</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}
    </form>
  );
}
