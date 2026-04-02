import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, HelpCircle, Plus, Wifi, WifiOff,
  Compass, Library, ShieldAlert, Bookmark
} from 'lucide-react';
import QueryForm from './components/QueryForm';
import FileUpload from './components/FileUpload';
import LoadingSpinner from './components/LoadingSpinner';
import StatusBar from './components/StatusBar';
import {
  ConflictMapView,
  CurrentQueryView,
  PipelineErrorCard,
  ProjectLibraryView,
  QueryHistoryPanel,
  SavedSynthesisView,
  XaiAnalysisView,
} from './components/WorkspacePanels';
import { runQuery, getStatus, getTrace, extractErrorMessage } from './services/api';
import type { QueryRequest } from './types';
import { useWorkspace } from './state/workspace';

const NAV_ITEMS = [
  { id: 'current', label: 'Current Query', icon: Compass },
  { id: 'library', label: 'Project Library', icon: Library },
  { id: 'analysis', label: 'XAI Analysis', icon: ShieldAlert },
  { id: 'conflicts', label: 'Conflict Map', icon: AlertTriangle },
  { id: 'saved', label: 'Saved Synthesis', icon: Bookmark },
];

function App() {
  const {
    currentProject,
    currentQuery,
    currentResult,
    currentQueryId,
    queryHistory,
    projects,
    createProject,
    switchProject,
    addQueryRecord,
    loadQuery,
  } = useWorkspace();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [activeNav, setActiveNav] = useState('current');
  const [loadingStage, setLoadingStage] = useState(0);

  const contentRef = useRef<HTMLDivElement>(null);
  const previousNavRef = useRef(activeNav);
  const scrollByTabRef = useRef<Record<string, number>>({});

  const loadingStages = useMemo(
    () => ['Stage 1 → Planning', 'Stage 2 → Retrieval', 'Stage 3 → Evidence', 'Stage 4 → Verification', 'Stage 5 → Summary'],
    [],
  );

  useEffect(() => {
    getStatus()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  useEffect(() => {
    const container = contentRef.current;
    if (!container) return;

    const previous = previousNavRef.current;
    scrollByTabRef.current[previous] = container.scrollTop;

    const nextScroll = scrollByTabRef.current[activeNav] ?? 0;
    requestAnimationFrame(() => {
      if (contentRef.current) {
        contentRef.current.scrollTop = nextScroll;
      }
    });

    previousNavRef.current = activeNav;
  }, [activeNav]);

  const handleSubmit = async (req: QueryRequest) => {
    setLoading(true);
    setLoadingStage(0);
    setError('');

    const stageTicker = window.setInterval(() => {
      setLoadingStage(prev => (prev < loadingStages.length - 1 ? prev + 1 : prev));
    }, 2500);

    try {
      const data = await runQuery(req);

      let trace: unknown | null = null;
      try {
        trace = await getTrace(data.execution_id);
      } catch {
        trace = null;
      }

      addQueryRecord({
        query_id: data.execution_id,
        query_text: req.query,
        result: data,
        trace,
        timestamp: new Date().toISOString(),
      });
      setActiveNav('current');
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    } finally {
      window.clearInterval(stageTicker);
      setLoading(false);
      setLoadingStage(loadingStages.length - 1);
    }
  };

  const renderActiveView = () => {
    switch (activeNav) {
      case 'current':
        return <CurrentQueryView result={currentResult} />;
      case 'analysis':
        return (
          <XaiAnalysisView
            queryHistory={queryHistory}
            currentQueryId={currentQueryId}
            onSelectQuery={loadQuery}
          />
        );
      case 'conflicts':
        return <ConflictMapView result={currentResult} />;
      case 'library':
        return (
          <ProjectLibraryView
            projects={projects}
            currentProjectId={currentProject?.id ?? ''}
            onSwitchProject={switchProject}
            onSelectQuery={loadQuery}
          />
        );
      case 'saved':
        return <SavedSynthesisView currentProject={currentProject} onSelectQuery={loadQuery} />;
      default:
        return <CurrentQueryView result={currentResult} />;
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
          <QueryHistoryPanel project={currentProject} currentQueryId={currentQueryId} onSelectQuery={loadQuery} />
          <button
            onClick={() => {
              createProject();
              setError('');
              setActiveNav('current');
            }}
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
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{currentProject?.name || 'Project'}</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>/</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{currentQuery?.query_text || 'No active query'}</span>
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

        <div ref={contentRef} style={{ flex: 1, overflowY: 'auto', padding: '26px 34px' }}>
          <div style={{ maxWidth: 960, margin: '0 auto' }}>
            <div className="glass-card" style={{ overflow: 'hidden', marginBottom: 24 }}>
              <div style={{ padding: '18px 22px' }}>
                <FileUpload />
                <div style={{ marginTop: 10 }}>
                  <QueryForm onSubmit={handleSubmit} loading={loading} />
                </div>
              </div>
            </div>

            <div style={{ minHeight: 540 }}>
              {loading && <LoadingSpinner currentStage={loadingStage} stages={loadingStages} />}

              {error && <PipelineErrorCard error={error} onDismiss={() => setError('')} />}

              {!loading && renderActiveView()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
