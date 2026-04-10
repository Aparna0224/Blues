import { memo, useMemo, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ChevronRight,
  FolderOpen,
  History,
  Sparkles,
  TriangleAlert,
  Trash2,
  X,
} from 'lucide-react';
import type { QueryResponse } from '../types';
import type { StoredQuery, WorkspaceProject } from '../state/workspace';
import ResultsPanel from './ResultsPanel';
import AnalysisHealthPanel from './AnalysisHealthPanel';

interface CurrentQueryViewProps {
  result: QueryResponse | null;
}

interface XaiAnalysisViewProps {
  queries: StoredQuery[];
  currentQueryId: string | null;
  activeQuery: StoredQuery | null;
  onSelectQuery: (queryId: string) => void;
}

interface ConflictMapViewProps {
  result: QueryResponse | null;
  projectName: string;
  queryText: string;
}

interface ProjectLibraryViewProps {
  projects: WorkspaceProject[];
  archivedProjects?: WorkspaceProject[];
  currentProjectId: string;
  onSwitchProject: (projectId: string) => void;
  onRenameProject: (projectId: string, name: string) => void;
  onDeleteProject: (projectId: string) => void;
  onRestoreProject?: (projectId: string) => void;
  onSelectQuery: (queryId: string) => void;
  disableActions?: boolean;
}

interface SavedSynthesisViewProps {
  projects: WorkspaceProject[];
  onSelectQuery: (queryId: string) => void;
}

function formatDate(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function extractConflictBlocks(groupedAnswer: string): string[] {
  const conflictMarker = /⚠️\s*Cross-Paper\s*Conflict/;
  const comparisonMarker = /📊\s*Comparison\s*Summary/;
  
  const blocks: string[] = [];
  let start = 0;
  
  while (start < groupedAnswer.length) {
    const conflictMatch = groupedAnswer.slice(start).search(conflictMarker);
    if (conflictMatch === -1) break;
    
    const actualConflictStart = start + conflictMatch;
    let end = groupedAnswer.length;
    
    const nextConflict = groupedAnswer.slice(actualConflictStart + 1).search(conflictMarker);
    const comparisonMatch = groupedAnswer.slice(actualConflictStart).search(comparisonMarker);
    
    if (nextConflict !== -1) {
      end = actualConflictStart + 1 + nextConflict;
    } else if (comparisonMatch !== -1) {
      end = actualConflictStart + comparisonMatch;
    }
    
    blocks.push(groupedAnswer.slice(actualConflictStart, end).trim());
    start = end;
  }
  
  return blocks;
}

export const CurrentQueryView = memo(function CurrentQueryView({ result }: CurrentQueryViewProps) {
  if (!result) {
    return (
      <div className="glass-card min-h-[420px] flex items-center justify-center p-8 text-center">
        <div>
          <p className="text-sm font-semibold text-slate-800">Start a new query</p>
          <p className="text-xs mt-1 text-slate-500">Use the input box to run analysis in this project workspace.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[1fr_260px] gap-5 items-start">
      <ResultsPanel result={result} />
      <div className="sticky top-0">
        <AnalysisHealthPanel result={result} showSummary={false} />
      </div>
    </div>
  );
});

export const XaiAnalysisView = memo(function XaiAnalysisView({ queries, currentQueryId, activeQuery, onSelectQuery }: XaiAnalysisViewProps) {
  const tracePretty = useMemo(() => {
    if (!activeQuery?.trace) return null;
    try {
      return JSON.stringify(activeQuery.trace, null, 2);
    } catch {
      return String(activeQuery.trace);
    }
  }, [activeQuery]);

  return (
    <div className="glass-card min-h-[460px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <History size={14} className="text-slate-700" />
        <h3 className="text-sm font-semibold text-slate-900">XAI Analysis (Project Scoped)</h3>
      </div>

      <div className="grid grid-cols-[300px_1fr] gap-4 min-h-[360px]">
        <div className="space-y-2 border-r border-slate-200 pr-3 overflow-auto max-h-[420px]">
          {queries.length === 0 ? (
            <p className="text-xs text-slate-500">No traces recorded in this project yet.</p>
          ) : (
            queries.slice().reverse().map(item => {
              const active = item.query_id === currentQueryId;
              return (
                <button
                  key={item.query_id}
                  onClick={() => onSelectQuery(item.query_id)}
                  className={`w-full text-left rounded-lg border p-3 transition ${active ? 'border-blue-900 bg-blue-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-slate-900">{item.query_text}</p>
                    <ChevronRight size={14} className="text-slate-400 mt-0.5" />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
                    <Calendar size={10} /> {formatDate(item.timestamp)}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">Trace: {item.trace ? 'available' : 'not available'}</p>
                </button>
              );
            })
          )}
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto max-h-[420px]">
          {!activeQuery ? (
            <p className="text-sm text-slate-500">Select a query to inspect its trace.</p>
          ) : !tracePretty ? (
            <p className="text-sm text-slate-500">Trace not available</p>
          ) : (
            <>
              <p className="text-xs font-semibold text-slate-700 mb-2">Trace for: {activeQuery.query_text}</p>
              <pre className="text-[11px] leading-5 text-slate-700 whitespace-pre-wrap">{tracePretty}</pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
});

export const ConflictMapView = memo(function ConflictMapView({ result, projectName, queryText }: ConflictMapViewProps) {
  const blocks = result ? extractConflictBlocks(result.grouped_answer) : [];

  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-1">
        <TriangleAlert size={14} className="text-amber-700" />
        <h3 className="text-sm font-semibold text-slate-900">Conflict Analysis — {queryText}</h3>
      </div>
      <p className="text-xs text-slate-500 mb-4">Project: {projectName}</p>

      {!result ? (
        <p className="text-xs text-slate-500">Run a query to analyze cross-paper conflicts.</p>
      ) : blocks.length === 0 ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 flex items-center gap-2">
          <CheckCircle2 size={14} /> No explicit conflicts were detected for the current query.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {blocks.map((block, idx) => (
            <article key={idx} className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="text-[11px] uppercase tracking-wide text-amber-700 font-semibold mb-2">Conflict {idx + 1}</p>
              <p className="text-sm leading-6 text-amber-900 whitespace-pre-wrap">{block}</p>
            </article>
          ))}
        </div>
      )}

      <p className="text-[11px] text-slate-500 mt-4">Future-ready: cards are structured for graph/heatmap upgrades.</p>
    </div>
  );
});

function EditableProjectTitle({
  project,
  onSwitchProject,
  onRenameProject,
  disableActions,
}: {
  project: WorkspaceProject;
  onSwitchProject: (projectId: string) => void;
  onRenameProject: (projectId: string, name: string) => void;
  disableActions?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState(project.name);

  const submit = () => {
    onRenameProject(project.id, nameDraft);
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        value={nameDraft}
        onChange={e => setNameDraft(e.target.value)}
        onBlur={submit}
        onKeyDown={e => {
          if (e.key === 'Enter') submit();
          if (e.key === 'Escape') {
            setNameDraft(project.name);
            setEditing(false);
          }
        }}
        autoFocus
        className="text-sm font-semibold text-slate-900 bg-white border border-slate-300 rounded px-2 py-1"
      />
    );
  }

  return (
    <button
      onClick={() => onSwitchProject(project.id)}
      onDoubleClick={() => {
        if (!disableActions) {
          setEditing(true);
          setNameDraft(project.name);
        }
      }}
      className="text-sm font-semibold text-slate-900 hover:underline"
      title="Double click to rename"
      disabled={disableActions}
    >
      {project.name}
    </button>
  );
}

export const ProjectLibraryView = memo(function ProjectLibraryView({
  projects,
  archivedProjects = [],
  currentProjectId,
  onSwitchProject,
  onRenameProject,
  onDeleteProject,
  onRestoreProject,
  onSelectQuery,
  disableActions,
}: ProjectLibraryViewProps) {
  const [confirmDeleteProjectId, setConfirmDeleteProjectId] = useState<string | null>(null);

  return (
    <div className="glass-card min-h-[420px] p-5 relative">
      <div className="flex items-center gap-2 mb-4">
        <FolderOpen size={14} className="text-slate-700" />
        <h3 className="text-sm font-semibold text-slate-900">Project Library</h3>
      </div>

      <div className="space-y-4">
        {projects.map(project => {
          const active = project.id === currentProjectId;
          const isOnlyProject = projects.length === 1;

          return (
            <section key={project.id} className={`rounded-lg border p-3 ${active ? 'border-blue-900 bg-blue-50' : 'border-slate-200 bg-white'}`}>
              <div className="flex items-center justify-between gap-2">
                <EditableProjectTitle
                  project={project}
                  onSwitchProject={onSwitchProject}
                  onRenameProject={onRenameProject}
                  disableActions={disableActions}
                />
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-500">{project.queries.length} queries</span>
                  <button
                    onClick={() => setConfirmDeleteProjectId(project.id)}
                    className="text-red-600 hover:text-red-700 disabled:opacity-50"
                    title={isOnlyProject ? 'At least one project must remain' : 'Delete project'}
                    disabled={disableActions || isOnlyProject}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              <div className="mt-2 space-y-1">
                {project.queries.slice().reverse().slice(0, 5).map(query => (
                  <button
                    key={query.query_id}
                    onClick={() => onSelectQuery(query.query_id)}
                    className="w-full text-left text-xs text-slate-700 hover:text-slate-900 rounded px-2 py-1 hover:bg-slate-100"
                    disabled={disableActions}
                  >
                    • {query.query_text}
                  </button>
                ))}
                {project.queries.length === 0 && <p className="text-xs text-slate-500">No queries yet.</p>}
              </div>
            </section>
          );
        })}
      </div>

      {archivedProjects.length > 0 && (
        <div className="mt-5 border-t border-slate-200 pt-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-2">Archived Projects</p>
          <div className="space-y-2">
            {archivedProjects.map(project => (
              <section key={project.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{project.name}</p>
                    <p className="text-[11px] text-slate-500">{project.queries.length} stored queries</p>
                  </div>
                  <button
                    onClick={() => onRestoreProject?.(project.id)}
                    className="px-2.5 py-1 text-[11px] font-semibold rounded border border-blue-300 text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                    disabled={disableActions || !onRestoreProject}
                  >
                    Restore
                  </button>
                </div>
              </section>
            ))}
          </div>
        </div>
      )}

      {confirmDeleteProjectId && (
        <div className="absolute inset-0 bg-black/25 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-lg max-w-sm w-full p-4">
            <div className="flex items-start justify-between gap-2 mb-2">
              <p className="text-sm font-semibold text-slate-900">Permanently delete project?</p>
              <button onClick={() => setConfirmDeleteProjectId(null)} className="text-slate-500"><X size={14} /></button>
            </div>
            <p className="text-xs text-slate-600 mb-3">This permanently removes the project and all associated queries/results. This action cannot be undone.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDeleteProjectId(null)} className="px-3 py-1.5 text-xs border border-slate-300 rounded">Cancel</button>
              <button
                onClick={() => {
                  onDeleteProject(confirmDeleteProjectId);
                  setConfirmDeleteProjectId(null);
                }}
                className="px-3 py-1.5 text-xs bg-red-700 text-white rounded"
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export const SavedSynthesisView = memo(function SavedSynthesisView({ projects, onSelectQuery }: SavedSynthesisViewProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const syntheses = projects.flatMap(project =>
    project.queries
      .filter(q => Boolean(q.result.summary))
      .map(q => ({
        ...q,
        projectName: project.name,
      })),
  );

  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={14} className="text-violet-700" />
        <h3 className="text-sm font-semibold text-slate-900">Saved Synthesis</h3>
      </div>

      {syntheses.length === 0 ? (
        <p className="text-xs text-slate-500">No saved summaries yet.</p>
      ) : (
        <div className="space-y-3">
          {syntheses.slice().reverse().map(item => (
            <article key={item.query_id} className="rounded-lg border border-violet-200 bg-violet-50 p-4">
              <button onClick={() => onSelectQuery(item.query_id)} className="text-left w-full">
                <p className="text-sm font-semibold text-slate-900">{item.query_text}</p>
                <p className="text-[11px] text-slate-500 mt-1">{item.projectName} • {formatDate(item.timestamp)}</p>
              </button>
              <div className="mt-2 border-t border-violet-200 pt-2">
                <p className={`text-sm text-slate-700 ${expanded[item.query_id] ? '' : 'line-clamp-4'}`}>{item.result.summary}</p>
                <button
                  onClick={() => setExpanded(prev => ({ ...prev, [item.query_id]: !prev[item.query_id] }))}
                  className="text-xs text-violet-700 font-semibold mt-2"
                >
                  {expanded[item.query_id] ? 'Collapse summary' : 'Expand full summary'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
});

interface QueryHistoryPanelProps {
  project: WorkspaceProject | null;
  currentQueryId: string | null;
  onSelectQuery: (queryId: string) => void;
  disableActions?: boolean;
}

export const QueryHistoryPanel = memo(function QueryHistoryPanel({ project, currentQueryId, onSelectQuery, disableActions }: QueryHistoryPanelProps) {
  const queries = project?.queries ?? [];

  return (
    <div className="px-2 pb-3">
      <div className="rounded-lg border border-slate-300/70 bg-white/70 p-2">
        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-1 mb-2">Project Query History</p>
        <div className="space-y-1 max-h-44 overflow-auto">
          {queries.slice().reverse().map(query => {
            const active = query.query_id === currentQueryId;
            return (
              <button
                key={query.query_id}
                onClick={() => onSelectQuery(query.query_id)}
                className={`w-full text-left rounded px-2 py-1.5 text-[11px] ${active ? 'bg-blue-100 text-blue-900 font-semibold' : 'text-slate-700 hover:bg-slate-100'}`}
                disabled={disableActions}
              >
                {query.query_text}
              </button>
            );
          })}
          {queries.length === 0 && <p className="text-[11px] px-2 py-1 text-slate-500">No query history yet.</p>}
        </div>
      </div>
    </div>
  );
});

interface PipelineErrorCardProps {
  error: string;
  onDismiss: () => void;
}

export const PipelineErrorCard = memo(function PipelineErrorCard({ error, onDismiss }: PipelineErrorCardProps) {
  return (
    <div className="animate-fade-in flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 mb-4">
      <AlertCircle size={16} className="text-red-600 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm font-semibold text-red-700">Pipeline Error</p>
        <p className="text-sm text-red-600">{error}</p>
      </div>
      <button onClick={onDismiss} className="text-red-600 text-sm">✕</button>
    </div>
  );
});

interface EmptyTabStateProps {
  title: string;
  subtitle: string;
}

export const EmptyTabState = memo(function EmptyTabState({ title, subtitle }: EmptyTabStateProps) {
  return (
    <div className="glass-card min-h-[420px] flex items-center justify-center p-8 text-center">
      <div>
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <p className="text-xs mt-1 text-slate-500">{subtitle}</p>
      </div>
    </div>
  );
});
