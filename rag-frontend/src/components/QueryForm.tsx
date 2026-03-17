import { useState } from 'react';
import { Search, Settings2, Zap, Database, Sparkles } from 'lucide-react';
import type { QueryRequest } from '../types';

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    onSubmit({
      query: query.trim(),
      num_documents: numDocs,
      mode,
      include_summary: includeSummary,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Main search input */}
      <div className="relative group">
        <Search
          size={20}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-500 transition-colors"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a research question..."
          disabled={loading}
          className="w-full pl-12 pr-28 py-3 rounded-lg border border-slate-200
                     bg-white text-base text-slate-900 placeholder:text-slate-400
                     focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-blue-500
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all shadow-sm"
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="absolute right-2 top-1/2 -translate-y-1/2
                     inline-flex items-center gap-2 px-4 py-1.5 text-sm font-semibold rounded-lg
                     bg-blue-600 text-white
                     hover:bg-blue-700 active:bg-blue-800
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all"
        >
          {loading ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            </>
          ) : (
            <>
              <Search size={16} />
            </>
          )}
        </button>
      </div>

      {/* Options toggle */}
      <div className="flex items-center pt-2">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg
                     transition-all ${
                       showAdvanced
                         ? 'bg-blue-100 text-blue-700'
                         : 'text-slate-600 hover:text-slate-800 hover:bg-slate-100'
                     }`}
        >
          <Settings2 size={13} />
          {showAdvanced ? 'Hide' : 'Show'} Options
        </button>
      </div>

      {/* Advanced options panel */}
      {showAdvanced && (
        <div className="bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-lg p-5 space-y-5 animate-fade-in">
          {/* Num documents */}
          <div>
            <label className="flex items-center justify-between text-sm font-medium text-slate-700 mb-3">
              <span>Documents to retrieve</span>
              <span className="text-xs font-semibold text-white bg-blue-500 px-2 py-0.5 rounded-full">
                {numDocs}
              </span>
            </label>
            <input
              type="range"
              min={1}
              max={50}
              value={numDocs}
              onChange={(e) => setNumDocs(Number(e.target.value))}
              className="w-full accent-blue-500 h-2 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-2 px-0.5">
              <span>1</span>
              <span>25</span>
              <span>50</span>
            </div>
          </div>

          {/* Mode toggle */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-3">
              Retrieval mode
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setMode('dynamic')}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all ${
                  mode === 'dynamic'
                    ? 'bg-blue-50 border-blue-200 ring-1 ring-blue-300'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <Zap size={16} className={mode === 'dynamic' ? 'text-blue-600' : 'text-slate-400'} />
                <div className="text-left">
                  <p className={`text-sm font-medium ${mode === 'dynamic' ? 'text-blue-900' : 'text-slate-700'}`}>
                    Dynamic
                  </p>
                  <p className="text-xs text-slate-500">Live search</p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setMode('cached')}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all ${
                  mode === 'cached'
                    ? 'bg-blue-50 border-blue-200 ring-1 ring-blue-300'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <Database size={16} className={mode === 'cached' ? 'text-blue-600' : 'text-slate-400'} />
                <div className="text-left">
                  <p className={`text-sm font-medium ${mode === 'cached' ? 'text-blue-900' : 'text-slate-700'}`}>
                    Cached
                  </p>
                  <p className="text-xs text-slate-500">Quick results</p>
                </div>
              </button>
            </div>
          </div>

          {/* Include summary toggle */}
          <div className="flex items-center justify-between p-4 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
            <div className="flex items-center gap-3">
              <Sparkles size={16} className="text-blue-500" />
              <div>
                <p className="text-sm font-medium text-slate-700">Generate Summary</p>
                <p className="text-xs text-slate-500">AI-synthesized findings</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIncludeSummary(!includeSummary)}
              className={`relative w-11 h-6 rounded-full transition-colors flex items-center px-0.5 ${
                includeSummary ? 'bg-blue-500' : 'bg-slate-300'
              }`}
            >
              <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                includeSummary ? 'translate-x-5' : ''
              }`} />
            </button>
          </div>
        </div>
      )}
    </form>
  );
}
