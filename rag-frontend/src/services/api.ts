import axios, { AxiosError } from 'axios';
import type {
  QueryRequest,
  QueryResponse,
  UploadResponse,
  StatusResponse,
  ProjectRecord,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  HardDeleteProjectResponse,
  QueryHistoryItem,
} from '../types';

interface DownloadReportOptions {
  queryText?: string;
  projectName?: string;
  timestamp?: string;
}

function toShortTimestamp(input?: string): string {
  const date = input ? new Date(input) : new Date();
  if (Number.isNaN(date.getTime())) {
    const now = new Date();
    return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
  }
  return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}_${String(date.getHours()).padStart(2, '0')}${String(date.getMinutes()).padStart(2, '0')}`;
}

function slugify(value: string, fallback = 'query'): string {
  const normalized = (value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  return (normalized || fallback).slice(0, 64);
}

const client = axios.create({
  baseURL: '/api',
  timeout: 600_000, // 10 min — dynamic pipeline can be very slow
  headers: { 'Content-Type': 'application/json' },
});

/** Extract a human-readable message from any axios error */
export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    // Server responded with an error (4xx / 5xx)
    if (err.response?.data?.detail) {
      return String(err.response.data.detail);
    }
    if (err.response?.status) {
      return `Server error ${err.response.status}: ${err.response.statusText}`;
    }
    // Network-level failure
    if (err.code === 'ECONNABORTED') {
      return 'Request timed out. The pipeline may still be running — try again with fewer documents.';
    }
    if (err.code === 'ERR_NETWORK') {
      return 'Network error — cannot reach the backend. Make sure the FastAPI server is running on port 8000.';
    }
    return err.message || 'An unexpected network error occurred.';
  }
  if (err instanceof Error) return err.message;
  return 'An unknown error occurred.';
}

/** Run the full agentic RAG pipeline */
export async function runQuery(params: QueryRequest): Promise<QueryResponse> {
  const { data } = await client.post<QueryResponse>('/query', params);
  return data;
}

/** Upload a PDF paper for ingestion */
export async function uploadPaper(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.post<UploadResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  });
  return data;
}

/** Get system status & stats */
export async function getStatus(): Promise<StatusResponse> {
  const { data } = await client.get<StatusResponse>('/status');
  return data;
}

/** Retrieve execution trace by ID */
export async function getTrace(executionId: string): Promise<unknown> {
  const { data } = await client.get(`/traces/${executionId}`);
  return data;
}

export async function createProject(payload: ProjectCreateRequest): Promise<ProjectRecord> {
  const { data } = await client.post<ProjectRecord>('/projects', payload);
  return data;
}

export async function listProjects(userId = 'local_user', includeArchived = false): Promise<ProjectRecord[]> {
  const { data } = await client.get<ProjectRecord[]>('/projects', {
    params: { user_id: userId, include_archived: includeArchived },
  });
  return data;
}

export async function updateProject(projectId: string, payload: ProjectUpdateRequest, userId = 'local_user'): Promise<ProjectRecord> {
  const { data } = await client.patch<ProjectRecord>(`/projects/${projectId}`, payload, {
    params: { user_id: userId },
  });
  return data;
}

export async function hardDeleteProject(projectId: string, userId = 'local_user'): Promise<HardDeleteProjectResponse> {
  const { data } = await client.delete<HardDeleteProjectResponse>(`/projects/${projectId}/hard`, {
    params: { user_id: userId, confirm: true },
  });
  return data;
}

export async function restoreProject(projectId: string, userId = 'local_user'): Promise<ProjectRecord> {
  const { data } = await client.post<ProjectRecord>(`/projects/${projectId}/restore`, undefined, {
    params: { user_id: userId },
  });
  return data;
}

export async function listProjectQueries(projectId: string): Promise<QueryHistoryItem[]> {
  const { data } = await client.get<QueryHistoryItem[]>(`/projects/${projectId}/queries`);
  return data;
}

export async function getQueryResult(queryId: string): Promise<QueryResponse> {
  const { data } = await client.get<QueryResponse>(`/queries/${queryId}/result`);
  return data;
}

export async function getExecutionResult(executionId: string): Promise<QueryResponse> {
  const { data } = await client.get<QueryResponse>(`/executions/${executionId}/result`);
  return data;
}

/** Download comprehensive report as PDF or Markdown */
export async function downloadReport(executionId: string, format: 'pdf' | 'md', options?: DownloadReportOptions): Promise<void> {
  const shortTs = toShortTimestamp(options?.timestamp);
  const safeQuery = slugify(options?.queryText || 'query');
  const res = await client.get(`/download-report`, {
    params: {
      execution_id: executionId,
      format,
      project_name: options?.projectName,
      query_text: options?.queryText,
      generated_at: options?.timestamp,
    },
    responseType: 'blob',
    timeout: 120_000,
  });

  const blob = new Blob([res.data], {
    type: format === 'pdf' ? 'application/pdf' : 'text/markdown;charset=utf-8',
  });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safeQuery}_${shortTs}.${format === 'pdf' ? 'pdf' : 'md'}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
