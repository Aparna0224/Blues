import { useState, useEffect } from 'react';
import { Beaker, Github, XCircle, Wifi, WifiOff } from 'lucide-react';
import QueryForm from './components/QueryForm';
import FileUpload from './components/FileUpload';
import ResultsPanel from './components/ResultsPanel';
import LoadingSpinner from './components/LoadingSpinner';
import StatusBar from './components/StatusBar';
import { runQuery, getStatus, extractErrorMessage } from './services/api';
import type { QueryRequest, QueryResponse } from './types';

function App() {
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  /* Check backend health on mount */
  useEffect(() => {
    getStatus()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  const handleSubmit = async (req: QueryRequest) => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await runQuery(req);
      setResult(data);
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="bg-white/80 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-600/20">
              <Beaker size={21} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 leading-tight tracking-tight">
                Blues RAG
              </h1>
              <p className="text-[11px] text-slate-400 font-medium tracking-wide uppercase">
                Agentic Research Assistant
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Connection indicator */}
            {backendOnline !== null && (
              <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
                backendOnline
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {backendOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
                {backendOnline ? 'API Connected' : 'API Offline'}
              </span>
            )}
            <a
              href="https://github.com/Aparna0224/Blues"
              target="_blank"
              rel="noopener noreferrer"
              className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200 hover:text-slate-700 transition-all"
            >
              <Github size={16} />
            </a>
          </div>
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────── */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-8 py-8 space-y-8">
        {/* Hero card — Upload + Query */}
        <div className="relative bg-white rounded-2xl border border-slate-200/80 shadow-xl shadow-slate-200/40 overflow-hidden">
          {/* Accent gradient bar */}
          <div className="h-1 bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-500" />
          <div className="p-6 sm:p-8 space-y-5">
            <div className="mb-1">
              <h2 className="text-lg font-semibold text-slate-900">Research Query</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Ask a biomedical research question — the pipeline will plan, retrieve, verify, and synthesize
              </p>
            </div>
            <FileUpload />
            <QueryForm onSubmit={handleSubmit} loading={loading} />
          </div>
        </div>

        {/* Loading */}
        {loading && <LoadingSpinner />}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4 animate-fade-in">
            <XCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">Pipeline Error</p>
              <p className="text-sm text-red-600 mt-0.5">{error}</p>
            </div>
            <button
              onClick={() => setError('')}
              className="text-red-400 hover:text-red-600 transition-colors"
            >
              <XCircle size={16} />
            </button>
          </div>
        )}

        {/* Results */}
        {result && !loading && <ResultsPanel result={result} />}
      </main>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer className="border-t border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-8 py-3.5 flex items-center justify-between">
          <StatusBar />
          <span className="text-[11px] text-slate-400 font-medium tracking-wide">
            5-Stage Agentic Pipeline
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
