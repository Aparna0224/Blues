import axios, { AxiosError } from 'axios';
import type {
  QueryRequest,
  QueryResponse,
  UploadResponse,
  StatusResponse,
} from '../types';

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

/** Download comprehensive report as PDF or Markdown */
export async function downloadReport(executionId: string, format: 'pdf' | 'md'): Promise<void> {
  const res = await client.get(`/download-report`, {
    params: { execution_id: executionId, format },
    responseType: 'blob',
    timeout: 120_000,
  });

  const blob = new Blob([res.data], {
    type: format === 'pdf' ? 'application/pdf' : 'text/markdown;charset=utf-8',
  });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `blues_report_${executionId}.${format === 'pdf' ? 'pdf' : 'md'}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
