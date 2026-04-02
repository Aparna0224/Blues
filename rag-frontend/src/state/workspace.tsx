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
  queryHistory: StoredQuery[];
  projects: WorkspaceProject[];
}

interface WorkspaceContextValue extends WorkspaceState {
  currentProject: WorkspaceProject | null;
  currentQuery: StoredQuery | null;
  createProject: (name?: string) => void;
  switchProject: (projectId: string) => void;
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
