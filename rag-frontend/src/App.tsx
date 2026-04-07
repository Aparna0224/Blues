import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, HelpCircle, Plus, Wifi, WifiOff,
  Compass, Library, ShieldAlert, Bookmark, Menu
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
    isLoading,
    projects,
  archivedProjects,
    createProject,
    switchProject,
    renameProject,
    deleteProject,
  restoreProject,
    clearCurrentQuery,
    updateQueryTrace,
    setIsLoading,
    addQueryRecord,
    loadQuery,
  } = useWorkspace();

  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [activeNav, setActiveNav] = useState('current');
  const [loadingStage, setLoadingStage] = useState(0);
  const [pausedActionsMessage, setPausedActionsMessage] = useState('');
  const [projectNameEditing, setProjectNameEditing] = useState(false);
  const [projectNameDraft, setProjectNameDraft] = useState('');
  const [isMobile, setIsMobile] = useState<boolean>(window.innerWidth <= 1024);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const contentRef = useRef<HTMLDivElement>(null);
  const previousNavRef = useRef(activeNav);
  const scrollByTabRef = useRef<Record<string, number>>({});

  const loadingStages = useMemo(
    () => ['Stage 1 → Planning', 'Stage 2 → Retrieval', 'Stage 3 → Ranking', 'Stage 4 → Evidence', 'Stage 5 → Summary'],
    [],
  );

  useEffect(() => {
    setProjectNameDraft(currentProject?.name ?? 'Project');
  }, [currentProject?.name]);

  useEffect(() => {
    getStatus()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth <= 1024;
      setIsMobile(mobile);
      if (!mobile) setMobileNavOpen(false);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    if (isLoading) {
      setPausedActionsMessage('Processing in progress — actions paused');
    } else {
      setPausedActionsMessage('');
    }
  }, [isLoading]);

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
    setIsLoading(true);
    setLoadingStage(0);
    setError('');

    const stageTicker = window.setInterval(() => {
      setLoadingStage(prev => (prev < loadingStages.length - 1 ? prev + 1 : prev));
    }, 2500);

    try {
      const data = await runQuery({
        ...req,
        user_id: 'local_user',
        project_id: currentProject?.id,
      });

      let trace: unknown | null = null;
      try {
        trace = await getTrace(data.execution_id);
      } catch {
        trace = null;
      }

      addQueryRecord({
        query_id: data.query_id || data.execution_id,
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
      setIsLoading(false);
      setLoadingStage(loadingStages.length - 1);
    }
  };

  const runWhenIdle = (action: () => void) => {
    if (isLoading) {
      setPausedActionsMessage('Processing in progress — actions paused');
      return;
    }
    action();
    if (isMobile) {
      setMobileNavOpen(false);
    }
  };

  const submitProjectRename = () => {
    if (!currentProject) return;
    renameProject(currentProject.id, projectNameDraft);
    setProjectNameEditing(false);
  };

  const handleSelectQuery = async (queryId: string, navigateToCurrent: boolean = false) => {
    if (navigateToCurrent) {
      setActiveNav('current');
    }
    const selected = await loadQuery(queryId);
    if (selected?.trace) return;

    try {
      const trace = await getTrace(selected?.result.execution_id || queryId);
      updateQueryTrace(queryId, trace);
    } catch {
      updateQueryTrace(queryId, null);
    }
  };

  const renderActiveView = () => {
    switch (activeNav) {
      case 'current':
        return <CurrentQueryView result={currentResult} />;
      case 'analysis':
        return (
          <XaiAnalysisView
            queries={currentProject?.queries ?? []}
            currentQueryId={currentQueryId}
            activeQuery={currentQuery}
            onSelectQuery={(queryId) => runWhenIdle(() => { void handleSelectQuery(queryId); })}
          />
        );
      case 'conflicts':
        return (
          <ConflictMapView
            result={currentResult}
            projectName={currentProject?.name ?? 'Project'}
            queryText={currentQuery?.query_text ?? 'New Query'}
          />
        );
      case 'library':
        return (
          <ProjectLibraryView
            projects={projects}
            archivedProjects={archivedProjects}
            currentProjectId={currentProject?.id ?? ''}
            onSwitchProject={(projectId) => runWhenIdle(() => switchProject(projectId))}
            onRenameProject={renameProject}
            onDeleteProject={(projectId) => runWhenIdle(() => deleteProject(projectId))}
            onRestoreProject={(projectId) => runWhenIdle(() => restoreProject(projectId))}
            onSelectQuery={(queryId) => runWhenIdle(() => { void handleSelectQuery(queryId, true); })}
            disableActions={isLoading}
          />
        );
      case 'saved':
        return <SavedSynthesisView projects={projects} onSelectQuery={(queryId) => runWhenIdle(() => { void handleSelectQuery(queryId, true); })} />;
      default:
        return <CurrentQueryView result={currentResult} />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>

      {/* Left sidebar */}
      <aside style={{ width: isMobile ? '100%' : 'var(--sidebar-width)', background: 'var(--bg-sidebar)', borderRight: isMobile ? 'none' : '1px solid var(--border)', borderBottom: isMobile ? '1px solid var(--border)' : 'none', display: (isMobile && !mobileNavOpen) ? 'none' : 'flex', flexDirection: 'column', flexShrink: 0, maxHeight: isMobile ? '50vh' : 'none' }}>
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
                onClick={() => runWhenIdle(() => setActiveNav(id))}
                disabled={isLoading}
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
          <QueryHistoryPanel
            project={currentProject}
            currentQueryId={currentQueryId}
            onSelectQuery={(queryId) => runWhenIdle(() => { void handleSelectQuery(queryId, true); })}
            disableActions={isLoading}
          />
          <button
            onClick={() => runWhenIdle(() => {
              createProject();
              setError('');
              setActiveNav('current');
            })}
            disabled={isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 4, padding: '9px 12px', borderRadius: 7, border: '1px solid rgba(15,38,92,0.18)', background: 'rgba(15,38,92,0.06)', color: '#0f265c', cursor: 'pointer', justifyContent: 'center', fontSize: 11, fontWeight: 700, transition: 'all 0.15s' }}
          >
            <Plus size={12} />
            NEW RESEARCH PROJECT
          </button>
          <StatusBar />
          <button
            disabled={isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', marginTop: 6, padding: '9px 12px', borderRadius: 7, border: 'none', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, transition: 'all 0.15s' }}
          >
            <HelpCircle size={12} />
            Help Center
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>

        {isLoading && (
          <div style={{ height: 4, background: 'rgba(15,38,92,0.1)', flexShrink: 0 }}>
            <div style={{ height: '100%', width: `${((loadingStage + 1) / loadingStages.length) * 100}%`, background: 'linear-gradient(90deg,#0f265c,#425d95)', transition: 'width 0.35s ease' }} />
          </div>
        )}

        <header style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56, flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {isMobile && (
              <button
                onClick={() => setMobileNavOpen(prev => !prev)}
                style={{ border: '1px solid rgba(15,38,92,0.2)', background: 'rgba(15,38,92,0.06)', borderRadius: 7, width: 30, height: 30, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                title="Toggle navigation"
              >
                <Menu size={14} />
              </button>
            )}
            <span style={{ fontSize: 12, fontWeight: 700, color: '#0f265c', letterSpacing: '0.04em' }}>BLUES</span>
            {projectNameEditing ? (
              <input
                value={projectNameDraft}
                onChange={e => setProjectNameDraft(e.target.value)}
                onBlur={submitProjectRename}
                onKeyDown={e => {
                  if (e.key === 'Enter') submitProjectRename();
                  if (e.key === 'Escape') {
                    setProjectNameDraft(currentProject?.name ?? 'Project');
                    setProjectNameEditing(false);
                  }
                }}
                autoFocus
                style={{ fontSize: 11, padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border)', background: '#fff', color: 'var(--text-primary)' }}
              />
            ) : (
              <button
                onClick={() => setProjectNameEditing(true)}
                style={{ fontSize: 11, color: 'var(--text-muted)', border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}
                title="Click to edit project name"
              >
                {currentProject?.name || 'Project'}
              </button>
            )}
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>/</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{currentQuery?.query_text || 'New Query'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              onClick={() => runWhenIdle(() => {
                clearCurrentQuery();
                setError('');
                setActiveNav('current');
              })}
              style={{ fontSize: 11, fontWeight: 700, color: '#0f265c', border: '1px solid rgba(15,38,92,0.2)', background: 'rgba(15,38,92,0.06)', borderRadius: 7, padding: '6px 10px', cursor: 'pointer' }}
            >
              New Query
            </button>
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

        <div ref={contentRef} style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '14px 12px' : '26px 34px' }}>
          <div style={{ maxWidth: isMobile ? '100%' : 960, margin: '0 auto' }}>
            {activeNav === 'current' && (
              <div className="glass-card" style={{ overflow: 'hidden', marginBottom: 24 }}>
                <div style={{ padding: '18px 22px' }}>
                  <FileUpload />
                  <div style={{ marginTop: 10 }}>
                    <QueryForm onSubmit={handleSubmit} loading={isLoading} />
                  </div>
                </div>
              </div>
            )}

            <div style={{ minHeight: 540 }}>
              {isLoading && <LoadingSpinner currentStage={loadingStage} stages={loadingStages} />}

              {error && <PipelineErrorCard error={error} onDismiss={() => setError('')} />}

              {pausedActionsMessage && (
                <div style={{ marginBottom: 14, border: '1px solid rgba(180,83,9,0.3)', background: 'rgba(180,83,9,0.08)', color: '#8a5300', borderRadius: 10, padding: '10px 12px', fontSize: 12, fontWeight: 600 }}>
                  {pausedActionsMessage}
                </div>
              )}

              {!isLoading && renderActiveView()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
