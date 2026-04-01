import { useState, useEffect } from 'react';
import {
  BookOpen, BarChart2, FileText, GitBranch, AlertTriangle,
  HelpCircle, Download, Bell, Settings, Plus, Wifi, WifiOff,
  FlaskConical
} from 'lucide-react';
import QueryForm from './components/QueryForm';
import FileUpload from './components/FileUpload';
import ResultsPanel from './components/ResultsPanel';
import LoadingSpinner from './components/LoadingSpinner';
import AnalysisHealthPanel from './components/AnalysisHealthPanel';
import StatusBar from './components/StatusBar';
import { runQuery, getStatus, extractErrorMessage } from './services/api';
import type { QueryRequest, QueryResponse } from './types';

const NAV_ITEMS = [
  { id: 'research', label: 'Research', icon: BookOpen },
  { id: 'neural', label: 'Neural Maps', icon: BarChart2 },
  { id: 'citations', label: 'Citations', icon: FileText },
  { id: 'methodology', label: 'Methodology', icon: GitBranch },
  { id: 'conflicts', label: 'Conflict Logs', icon: AlertTriangle },
];

const TOP_TABS = ['Dashboard', 'Archive', 'Collections', 'XAI Workbench'];

function App() {
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [activeNav, setActiveNav] = useState('research');
  const [activeTab, setActiveTab] = useState('Dashboard');

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
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>

      {/* ── Left Sidebar ─────────────────────────────── */}
      <aside style={{ width: 'var(--sidebar-width)', background: 'var(--bg-sidebar)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        {/* Project header */}
        <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: 'linear-gradient(135deg, #5eead4, #818cf8)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <FlaskConical size={16} color="#0b0f1e" />
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Project Alpha
              </p>
              <p style={{ fontSize: 9, color: 'var(--text-muted)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                XAI Archive
              </p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 8px', overflowY: 'auto' }}>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
            const active = activeNav === id;
            return (
              <button
                key={id}
                onClick={() => setActiveNav(id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '9px 12px', borderRadius: 9,
                  border: 'none', cursor: 'pointer', textAlign: 'left', marginBottom: 2,
                  transition: 'all 0.15s',
                  background: active ? 'rgba(94,234,212,0.08)' : 'transparent',
                  color: active ? 'var(--teal)' : 'var(--text-muted)',
                  boxShadow: active ? '0 0 0 1px rgba(94,234,212,0.2)' : 'none',
                }}
              >
                <Icon size={14} />
                <span style={{ fontSize: 12.5, fontWeight: active ? 600 : 400 }}>{label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar footer */}
        <div style={{ padding: '12px 8px', borderTop: '1px solid var(--border)' }}>
          <StatusBar />
          <button
            onClick={() => result && document.getElementById('export-btn')?.click()}
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 10, padding: '9px 12px', borderRadius: 9, border: '1px solid rgba(94,234,212,0.3)', background: 'rgba(94,234,212,0.06)', color: 'var(--teal)', cursor: 'pointer', justifyContent: 'center', fontSize: 12, fontWeight: 600, transition: 'all 0.15s' }}
          >
            <Download size={13} />
            Export Report
          </button>
          <button
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 6, padding: '9px 12px', borderRadius: 9, border: 'none', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12, transition: 'all 0.15s' }}
          >
            <HelpCircle size={13} />
            Help Center
          </button>
        </div>
      </aside>

      {/* ── Right content area ───────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>

        {/* ── Top Nav Bar ───────────────────────────── */}
        <header style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', padding: '0 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56, flexShrink: 0 }}>
          {/* Brand + tabs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
            <div>
              <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Blues</span>
              <span style={{ display: 'block', fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', lineHeight: 1, marginTop: 1 }}>
                Explainable AI Research Assistant
              </span>
            </div>
            <nav style={{ display: 'flex', gap: 4 }}>
              {TOP_TABS.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 500, transition: 'all 0.15s',
                    background: activeTab === tab ? 'rgba(94,234,212,0.1)' : 'transparent',
                    color: activeTab === tab ? 'var(--teal)' : 'var(--text-muted)',
                  }}
                >
                  {tab}
                </button>
              ))}
            </nav>
          </div>

          {/* Toolbar right */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {backendOnline !== null && (
              <span style={{
                display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 500,
                padding: '4px 10px', borderRadius: 20,
                background: backendOnline ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
                color: backendOnline ? '#34d399' : '#f87171',
                border: `1px solid ${backendOnline ? 'rgba(52,211,153,0.25)' : 'rgba(248,113,113,0.25)'}`,
              }}>
                {backendOnline ? <Wifi size={11} /> : <WifiOff size={11} />}
                {backendOnline ? 'API Connected' : 'API Offline'}
              </span>
            )}
            <button style={{ width: 32, height: 32, borderRadius: 9, border: '1px solid var(--border)', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <Bell size={14} />
            </button>
            <button style={{ width: 32, height: 32, borderRadius: 9, border: '1px solid var(--border)', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <Settings size={14} />
            </button>
            <button
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 9, border: 'none', background: 'linear-gradient(135deg, #5eead4, #38bdf8)', color: '#0b0f1e', fontWeight: 700, fontSize: 12, cursor: 'pointer', transition: 'all 0.15s' }}
              onClick={() => { setResult(null); setError(''); }}
            >
              <Plus size={13} />
              New Analysis
            </button>
          </div>
        </header>

        {/* ── Scrollable main area ──────────────────── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '28px' }}>

          {/* Search / query card */}
          <div className="glass-card" style={{ overflow: 'hidden', marginBottom: 24 }}>
            <div className="accent-bar" />
            <div style={{ padding: '20px 24px' }}>
              <FileUpload />
              <div style={{ marginTop: 14 }}>
                <QueryForm onSubmit={handleSubmit} loading={loading} />
              </div>
            </div>
          </div>

          {/* Loading */}
          {loading && <LoadingSpinner />}

          {/* Error */}
          {error && (
            <div className="animate-fade-in" style={{ display: 'flex', alignItems: 'flex-start', gap: 12, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 12, padding: '14px 18px', marginBottom: 24 }}>
              <AlertTriangle size={16} style={{ color: '#f87171', flexShrink: 0, marginTop: 1 }} />
              <div>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#f87171' }}>Pipeline Error</p>
                <p style={{ margin: '2px 0 0', fontSize: 13, color: '#fca5a5' }}>{error}</p>
              </div>
              <button onClick={() => setError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#f87171', marginLeft: 'auto' }}>✕</button>
            </div>
          )}

          {/* Results split layout */}
          {result && !loading && (
            <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20, alignItems: 'start' }}>
              <div>
                <ResultsPanel result={result} />
              </div>
              <div style={{ position: 'sticky', top: 0 }}>
                <AnalysisHealthPanel result={result} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
