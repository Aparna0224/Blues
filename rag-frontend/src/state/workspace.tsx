/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { QueryResponse } from '../types';

export interface StoredQuery {
  query_id: string;
  query_text: string;
  result: QueryResponse;
  trace: unknown | null;
  timestamp: string;
}

export interface WorkspaceProject {
  id: string;
  name: string;
  queries: StoredQuery[];
}

interface WorkspaceState {
  currentProjectId: string;
  currentQueryId: string | null;
  currentResult: QueryResponse | null;
  isLoading: boolean;
  queryHistory: StoredQuery[];
  projects: WorkspaceProject[];
}

interface WorkspaceContextValue extends WorkspaceState {
  currentProject: WorkspaceProject | null;
  currentQuery: StoredQuery | null;
  createProject: (name?: string) => void;
  switchProject: (projectId: string) => void;
  renameProject: (projectId: string, name: string) => void;
  deleteProject: (projectId: string) => void;
  clearCurrentQuery: () => void;
  updateQueryTrace: (queryId: string, trace: unknown | null) => void;
  setIsLoading: (loading: boolean) => void;
  addQueryRecord: (record: StoredQuery) => void;
  loadQuery: (queryId: string) => void;
}

const STORAGE_KEY = 'blues.workspace.v1';

function uid(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function createDefaultProject(name = 'Project 1'): WorkspaceProject {
  return { id: uid('project'), name, queries: [] };
}

function createInitialState(): WorkspaceState {
  const project = createDefaultProject();
  return {
    currentProjectId: project.id,
    currentQueryId: null,
    currentResult: null,
    isLoading: false,
    queryHistory: [],
    projects: [project],
  };
}

function findQuery(projects: WorkspaceProject[], queryId: string | null): StoredQuery | null {
  if (!queryId) return null;
  for (const project of projects) {
    const query = project.queries.find(q => q.query_id === queryId);
    if (query) return query;
  }
  return null;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkspaceState>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return createInitialState();
      const parsed = JSON.parse(raw) as WorkspaceState;
      if (!parsed.projects?.length) return createInitialState();

      const existingProject = parsed.projects.find(p => p.id === parsed.currentProjectId) ?? parsed.projects[0];
      const currentQuery = findQuery(parsed.projects, parsed.currentQueryId);

      return {
        ...parsed,
        currentProjectId: existingProject.id,
        currentQueryId: currentQuery?.query_id ?? null,
        currentResult: currentQuery?.result ?? null,
        isLoading: false,
      };
    } catch {
      return createInitialState();
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const createProject = (name?: string) => {
    setState(prev => {
      const nextIndex = prev.projects.length + 1;
      const project = createDefaultProject(name?.trim() || `Project ${nextIndex}`);
      return {
        ...prev,
        currentProjectId: project.id,
        currentQueryId: null,
        currentResult: null,
        projects: [...prev.projects, project],
      };
    });
  };

  const switchProject = (projectId: string) => {
    setState(prev => {
      const project = prev.projects.find(p => p.id === projectId);
      if (!project) return prev;
      const latest = project.queries[project.queries.length - 1] ?? null;
      return {
        ...prev,
        currentProjectId: project.id,
        currentQueryId: latest?.query_id ?? null,
        currentResult: latest?.result ?? null,
      };
    });
  };

  const renameProject = (projectId: string, name: string) => {
    const nextName = name.trim();
    if (!nextName) return;
    setState(prev => ({
      ...prev,
      projects: prev.projects.map(project =>
        project.id === projectId ? { ...project, name: nextName } : project,
      ),
    }));
  };

  const deleteProject = (projectId: string) => {
    setState(prev => {
      if (prev.projects.length <= 1) {
        return prev;
      }

      const remainingProjects = prev.projects.filter(project => project.id !== projectId);
      const removedQueryIds = new Set(
        prev.projects.find(p => p.id === projectId)?.queries.map(q => q.query_id) ?? [],
      );

      const activeProjectDeleted = prev.currentProjectId === projectId;
      const fallbackProject = activeProjectDeleted
        ? remainingProjects[0]
        : (remainingProjects.find(p => p.id === prev.currentProjectId) ?? remainingProjects[0]);

      const fallbackQuery = fallbackProject?.queries[fallbackProject.queries.length - 1] ?? null;

      return {
        ...prev,
        projects: remainingProjects,
        queryHistory: prev.queryHistory.filter(q => !removedQueryIds.has(q.query_id)),
        currentProjectId: fallbackProject?.id ?? prev.currentProjectId,
        currentQueryId: fallbackQuery?.query_id ?? null,
        currentResult: fallbackQuery?.result ?? null,
      };
    });
  };

  const clearCurrentQuery = () => {
    setState(prev => ({
      ...prev,
      currentQueryId: null,
      currentResult: null,
    }));
  };

  const updateQueryTrace = (queryId: string, trace: unknown | null) => {
    setState(prev => ({
      ...prev,
      projects: prev.projects.map(project => ({
        ...project,
        queries: project.queries.map(query =>
          query.query_id === queryId ? { ...query, trace } : query,
        ),
      })),
      queryHistory: prev.queryHistory.map(query =>
        query.query_id === queryId ? { ...query, trace } : query,
      ),
    }));
  };

  const setIsLoading = (loading: boolean) => {
    setState(prev => ({ ...prev, isLoading: loading }));
  };

  const addQueryRecord = (record: StoredQuery) => {
    setState(prev => {
      const updatedProjects = prev.projects.map(project =>
        project.id === prev.currentProjectId
          ? { ...project, queries: [...project.queries, record] }
          : project,
      );

      return {
        ...prev,
        projects: updatedProjects,
        queryHistory: [...prev.queryHistory, record],
        currentQueryId: record.query_id,
        currentResult: record.result,
      };
    });
  };

  const loadQuery = (queryId: string) => {
    setState(prev => {
      const loaded = findQuery(prev.projects, queryId);
      if (!loaded) return prev;

      const project = prev.projects.find(p => p.queries.some(q => q.query_id === queryId));
      return {
        ...prev,
        currentProjectId: project?.id ?? prev.currentProjectId,
        currentQueryId: loaded.query_id,
        currentResult: loaded.result,
      };
    });
  };

  const value = useMemo<WorkspaceContextValue>(() => {
    const currentProject = state.projects.find(p => p.id === state.currentProjectId) ?? null;
    const currentQuery = findQuery(state.projects, state.currentQueryId);

    return {
      ...state,
      currentProject,
      currentQuery,
      createProject,
      switchProject,
      renameProject,
  deleteProject,
  clearCurrentQuery,
  updateQueryTrace,
      setIsLoading,
      addQueryRecord,
      loadQuery,
    };
  }, [state]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error('useWorkspace must be used inside WorkspaceProvider');
  }
  return ctx;
}
