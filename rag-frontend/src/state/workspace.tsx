/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  createProject as createProjectApi,
  hardDeleteProject as hardDeleteProjectApi,
  getQueryResult,
  listProjectQueries,
  listProjects,
  restoreProject as restoreProjectApi,
  updateProject as updateProjectApi,
} from '../services/api';
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
  isArchived?: boolean;
}

interface WorkspaceState {
  currentProjectId: string;
  currentQueryId: string | null;
  currentResult: QueryResponse | null;
  isLoading: boolean;
  queryHistory: StoredQuery[];
  projects: WorkspaceProject[];
  archivedProjects: WorkspaceProject[];
}

interface WorkspaceContextValue extends WorkspaceState {
  currentProject: WorkspaceProject | null;
  currentQuery: StoredQuery | null;
  createProject: (name?: string) => void;
  switchProject: (projectId: string) => void;
  renameProject: (projectId: string, name: string) => void;
  deleteProject: (projectId: string) => void;
  restoreProject: (projectId: string) => void;
  clearCurrentQuery: () => void;
  updateQueryTrace: (queryId: string, trace: unknown | null) => void;
  setIsLoading: (loading: boolean) => void;
  addQueryRecord: (record: StoredQuery) => void;
  loadQuery: (queryId: string) => Promise<StoredQuery | null>;
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
    archivedProjects: [],
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
        archivedProjects: parsed.archivedProjects ?? [],
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

  useEffect(() => {
    let cancelled = false;

    const hydrateFromBackend = async () => {
      try {
    const projectRecords = await listProjects('local_user', true);
        if (!projectRecords.length || cancelled) return;

    const hydratedProjects: WorkspaceProject[] = [];
    const hydratedArchivedProjects: WorkspaceProject[] = [];

        for (const p of projectRecords) {
          const queryMeta = await listProjectQueries(p.project_id);
          const queriesRaw = await Promise.all(
            queryMeta.slice(0, 30).map(async q => {
              try {
                const result = await getQueryResult(q.query_id);
                return {
                  query_id: q.query_id,
                  query_text: q.query_text,
                  result,
                  trace: null,
                  timestamp: q.created_at,
                } as StoredQuery;
              } catch {
                return null;
              }
            }),
          );

          const hydratedProject = {
            id: p.project_id,
            name: p.name,
            queries: queriesRaw.filter((x): x is StoredQuery => Boolean(x)),
            isArchived: p.is_archived,
          };

          if (p.is_archived) {
            hydratedArchivedProjects.push(hydratedProject);
          } else {
            hydratedProjects.push(hydratedProject);
          }
        }

        if (cancelled) return;

        if (!hydratedProjects.length) {
          setState(prev => ({
            ...prev,
            archivedProjects: hydratedArchivedProjects,
          }));
          return;
        }

        const preferredProject =
          hydratedProjects.find(p => p.id === state.currentProjectId) ?? hydratedProjects[0];
        const preferredQuery =
          preferredProject.queries.find(q => q.query_id === state.currentQueryId) ??
          preferredProject.queries[preferredProject.queries.length - 1] ??
          null;

        const allQueries = hydratedProjects.flatMap(p => p.queries);

        setState(prev => ({
          ...prev,
          projects: hydratedProjects,
          archivedProjects: hydratedArchivedProjects,
          queryHistory: allQueries,
          currentProjectId: preferredProject.id,
          currentQueryId: preferredQuery?.query_id ?? null,
          currentResult: preferredQuery?.result ?? null,
        }));
      } catch {
        // keep local fallback silently
      }
    };

    void hydrateFromBackend();
    return () => {
      cancelled = true;
    };
  }, []);

  const createProject = (name?: string) => {
    const nextName = (name?.trim() || '').trim();
    const fallbackName = nextName || `Project ${state.projects.length + 1}`;

    void createProjectApi({
      name: fallbackName,
      user_id: 'local_user',
      description: '',
    })
      .then(created => {
        setState(prev => {
          const project: WorkspaceProject = { id: created.project_id, name: created.name, queries: [] };
          return {
            ...prev,
            currentProjectId: project.id,
            currentQueryId: null,
            currentResult: null,
            archivedProjects: prev.archivedProjects.filter(p => p.id !== project.id),
            projects: [...prev.projects, project],
          };
        });
      })
      .catch(() => {
        // local fallback if backend create fails
        setState(prev => {
          const project = createDefaultProject(fallbackName);
          return {
            ...prev,
            currentProjectId: project.id,
            currentQueryId: null,
            currentResult: null,
            projects: [...prev.projects, project],
          };
        });
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

    void updateProjectApi(projectId, { name: nextName }, 'local_user')
      .then(updated => {
        setState(prev => ({
          ...prev,
          projects: prev.projects.map(project =>
            project.id === projectId ? { ...project, name: updated.name } : project,
          ),
        }));
      })
      .catch(() => {
        // keep optimistic local name if backend unavailable
      });
  };

  const deleteProject = (projectId: string) => {
    const removeProjectState = (prev: WorkspaceState): WorkspaceState => {
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
        archivedProjects: prev.archivedProjects.filter(project => project.id !== projectId),
      };
    };

    void hardDeleteProjectApi(projectId, 'local_user')
      .then(() => {
        setState(prev => removeProjectState(prev));
      })
      .catch(() => {
        // hard-delete must succeed on backend; keep local state unchanged on failure
      });
  };

  const restoreProject = (projectId: string) => {
    const archived = state.archivedProjects.find(project => project.id === projectId);
    if (!archived) return;

    const hydrateRestoredQueries = async () => {
      const queryMeta = await listProjectQueries(projectId);
      const queriesRaw = await Promise.all(
        queryMeta.slice(0, 30).map(async q => {
          try {
            const result = await getQueryResult(q.query_id);
            return {
              query_id: q.query_id,
              query_text: q.query_text,
              result,
              trace: null,
              timestamp: q.created_at,
            } as StoredQuery;
          } catch {
            return null;
          }
        }),
      );
      return queriesRaw.filter((x): x is StoredQuery => Boolean(x));
    };

    void restoreProjectApi(projectId, 'local_user')
      .then(async restored => {
        const restoredQueries = await hydrateRestoredQueries();
        setState(prev => {
          const restoredProject: WorkspaceProject = {
            id: restored.project_id,
            name: restored.name,
            queries: restoredQueries,
            isArchived: false,
          };
          return {
            ...prev,
            projects: [...prev.projects, restoredProject],
            archivedProjects: prev.archivedProjects.filter(project => project.id !== projectId),
            currentProjectId: restoredProject.id,
            currentQueryId: restoredQueries[restoredQueries.length - 1]?.query_id ?? null,
            currentResult: restoredQueries[restoredQueries.length - 1]?.result ?? null,
            queryHistory: [...prev.queryHistory, ...restoredQueries],
          };
        });
      })
      .catch(() => {
        // keep state unchanged when restore fails
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

  const loadQuery = async (queryId: string): Promise<StoredQuery | null> => {
    const baseQuery = findQuery(state.projects, queryId);
    if (!baseQuery) {
      return null;
    }

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

    try {
      const hydratedResult = await getQueryResult(queryId);

      setState(prev => ({
        ...prev,
        projects: prev.projects.map(project => ({
          ...project,
          queries: project.queries.map(query =>
            query.query_id === queryId ? { ...query, result: hydratedResult } : query,
          ),
        })),
        queryHistory: prev.queryHistory.map(query =>
          query.query_id === queryId ? { ...query, result: hydratedResult } : query,
        ),
        currentResult: prev.currentQueryId === queryId ? hydratedResult : prev.currentResult,
      }));

      return {
        query_id: baseQuery.query_id,
        query_text: baseQuery.query_text,
        result: hydratedResult,
        trace: baseQuery.trace,
        timestamp: baseQuery.timestamp,
      };
    } catch {
      return baseQuery;
    }
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
  restoreProject,
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
