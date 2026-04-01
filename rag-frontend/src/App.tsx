import { useState, useEffect } from 'react';
import {
  AlertTriangle, HelpCircle, Plus, Wifi, WifiOff,
  Compass, Library, ShieldAlert, Bookmark
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
  { id: 'current', label: 'Current Query', icon: Compass },
  { id: 'library', label: 'Project Library', icon: Library },
  { id: 'analysis', label: 'XAI Analysis', icon: ShieldAlert },
  { id: 'conflicts', label: 'Conflict Map', icon: AlertTriangle },
  { id: 'saved', label: 'Saved Synthesis', icon: Bookmark },
];

function App() {
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [activeNav, setActiveNav] = useState('analysis');

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

      {/* Left sidebar */}
      <aside style={{ width: 'var(--sidebar-width)', background: 'var(--bg-sidebar)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <div style={{ width: 30, height: 30, borderRadius: 7, background: '#0f265c', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700 }}>
              B
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', margin: 0, letterSpacing: '0.04em' }}>
                BLUES
              </p>
              <p style={{ fontSize: 9, color: 'var(--text-muted)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Deep Archive v1
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
                  width: '100%', padding: '9px 12px', borderRadius: 7,
                  border: 'none', cursor: 'pointer', textAlign: 'left', marginBottom: 2,
                  transition: 'all 0.15s',
                  background: active ? 'rgba(15, 38, 92, 0.08)' : 'transparent',
                  color: active ? '#0f265c' : 'var(--text-muted)',
                  boxShadow: active ? '0 0 0 1px rgba(15, 38, 92, 0.12)' : 'none',
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
          <button
            onClick={() => { setResult(null); setError(''); }}
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 4, padding: '9px 12px', borderRadius: 7, border: '1px solid rgba(15,38,92,0.18)', background: 'rgba(15,38,92,0.06)', color: '#0f265c', cursor: 'pointer', justifyContent: 'center', fontSize: 11, fontWeight: 700, transition: 'all 0.15s' }}
          >
            <Plus size={12} />
            NEW RESEARCH PROJECT
          </button>
          <StatusBar />
          <button
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 6, padding: '9px 12px', borderRadius: 7, border: 'none', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, transition: 'all 0.15s' }}
          >
            <HelpCircle size={12} />
            Help Center
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>

        <header style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#0f265c', letterSpacing: '0.04em' }}>BLUES</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Synthesis</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>/</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{result?.query || 'Neural Signal Analysis'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {backendOnline !== null && (
              <span style={{
                display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 500,
                padding: '4px 10px', borderRadius: 20,
                background: backendOnline ? 'rgba(52,211,153,0.12)' : 'rgba(248,113,113,0.12)',
                color: backendOnline ? '#34d399' : '#f87171',
                border: `1px solid ${backendOnline ? 'rgba(52,211,153,0.25)' : 'rgba(248,113,113,0.25)'}`,
              }}>
                {backendOnline ? <Wifi size={11} /> : <WifiOff size={11} />}
                {backendOnline ? 'API Connected' : 'API Offline'}
              </span>
            )}
          </div>
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '26px 34px' }}>
          <div style={{ maxWidth: 960, margin: '0 auto' }}>
            <div className="glass-card" style={{ overflow: 'hidden', marginBottom: 24 }}>
              <div style={{ padding: '18px 22px' }}>
                <FileUpload />
                <div style={{ marginTop: 10 }}>
                  <QueryForm onSubmit={handleSubmit} loading={loading} />
                </div>
              </div>
            </div>

            {loading && <LoadingSpinner />}

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
    </div>
  );
}

export default App;
