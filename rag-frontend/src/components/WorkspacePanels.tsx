import { memo } from 'react';
import { AlertCircle, Calendar, CheckCircle2, ChevronRight, FolderOpen, History, Sparkles, TriangleAlert } from 'lucide-react';
import type { QueryResponse } from '../types';
import type { StoredQuery, WorkspaceProject } from '../state/workspace';
import ResultsPanel from './ResultsPanel';
import AnalysisHealthPanel from './AnalysisHealthPanel';

interface CurrentQueryViewProps {
  result: QueryResponse | null;
}

interface XaiAnalysisViewProps {
  queryHistory: StoredQuery[];
  currentQueryId: string | null;
  onSelectQuery: (queryId: string) => void;
}

interface ConflictMapViewProps {
  result: QueryResponse | null;
}

interface ProjectLibraryViewProps {
  projects: WorkspaceProject[];
  currentProjectId: string;
  onSwitchProject: (projectId: string) => void;
  onSelectQuery: (queryId: string) => void;
}

interface SavedSynthesisViewProps {
  currentProject: WorkspaceProject | null;
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
  return groupedAnswer
    .split('⚠️ Cross-Paper Conflict Analysis')
    .slice(1)
    .map(block => block.split('📊 Comparison Summary')[0]?.trim())
    .filter(Boolean);
}

export const CurrentQueryView = memo(function CurrentQueryView({ result }: CurrentQueryViewProps) {
  if (!result) {
    return (
      <div className="glass-card min-h-[420px] flex items-center justify-center p-8 text-center">
        <div>
          <p className="text-sm font-semibold text-slate-800">No active query yet</p>
          <p className="text-xs mt-1 text-slate-500">Run a question to start your research workspace.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[1fr_260px] gap-5 items-start">
      <ResultsPanel result={result} />
      <div className="sticky top-0">
        <AnalysisHealthPanel result={result} />
      </div>
    </div>
  );
});

export const XaiAnalysisView = memo(function XaiAnalysisView({ queryHistory, currentQueryId, onSelectQuery }: XaiAnalysisViewProps) {
  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <History size={14} className="text-slate-700" />
        <h3 className="text-sm font-semibold text-slate-900">Trace History</h3>
      </div>

      {queryHistory.length === 0 ? (
        <p className="text-xs text-slate-500">No traces recorded yet.</p>
      ) : (
        <div className="space-y-2">
          {queryHistory.slice().reverse().map(item => {
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
                <p className="text-[11px] text-slate-500 mt-1">
                  Trace: {item.trace ? 'available' : 'not loaded'}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
});

export const ConflictMapView = memo(function ConflictMapView({ result }: ConflictMapViewProps) {
  const blocks = result ? extractConflictBlocks(result.grouped_answer) : [];

  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <TriangleAlert size={14} className="text-amber-700" />
        <h3 className="text-sm font-semibold text-slate-900">Conflict Map</h3>
      </div>

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

export const ProjectLibraryView = memo(function ProjectLibraryView({ projects, currentProjectId, onSwitchProject, onSelectQuery }: ProjectLibraryViewProps) {
  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <FolderOpen size={14} className="text-slate-700" />
        <h3 className="text-sm font-semibold text-slate-900">Project Library</h3>
      </div>

      <div className="space-y-4">
        {projects.map(project => {
          const active = project.id === currentProjectId;
          return (
            <section key={project.id} className={`rounded-lg border p-3 ${active ? 'border-blue-900 bg-blue-50' : 'border-slate-200 bg-white'}`}>
              <div className="flex items-center justify-between gap-2">
                <button onClick={() => onSwitchProject(project.id)} className="text-sm font-semibold text-slate-900 hover:underline">
                  {project.name}
                </button>
                <span className="text-[11px] text-slate-500">{project.queries.length} queries</span>
              </div>

              <div className="mt-2 space-y-1">
                {project.queries.slice().reverse().slice(0, 5).map(query => (
                  <button
                    key={query.query_id}
                    onClick={() => onSelectQuery(query.query_id)}
                    className="w-full text-left text-xs text-slate-700 hover:text-slate-900 rounded px-2 py-1 hover:bg-slate-100"
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
    </div>
  );
});

export const SavedSynthesisView = memo(function SavedSynthesisView({ currentProject, onSelectQuery }: SavedSynthesisViewProps) {
  const syntheses = (currentProject?.queries ?? []).filter(q => Boolean(q.result.summary));

  return (
    <div className="glass-card min-h-[420px] p-5">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={14} className="text-violet-700" />
        <h3 className="text-sm font-semibold text-slate-900">Saved Synthesis</h3>
      </div>

      {syntheses.length === 0 ? (
        <p className="text-xs text-slate-500">No saved summaries in this project yet.</p>
      ) : (
        <div className="space-y-3">
          {syntheses.slice().reverse().map(item => (
            <article key={item.query_id} className="rounded-lg border border-violet-200 bg-violet-50 p-4">
              <button onClick={() => onSelectQuery(item.query_id)} className="text-left w-full">
                <p className="text-sm font-semibold text-slate-900">{item.query_text}</p>
                <p className="text-[11px] text-slate-500 mt-1">{formatDate(item.timestamp)}</p>
                <p className="text-sm text-slate-700 mt-2 line-clamp-4">{item.result.summary}</p>
              </button>
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
}

export const QueryHistoryPanel = memo(function QueryHistoryPanel({ project, currentQueryId, onSelectQuery }: QueryHistoryPanelProps) {
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
