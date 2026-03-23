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
  
  // Parse 5-section answer if present
  if (data.grouped_answer && data.answer_structure === '5-section') {
    data.five_section_answer = parse5SectionAnswer(data.grouped_answer);
  }
  
  return data;
}

/** Parse 5-section answer from text */
export function parse5SectionAnswer(text: string): {
  executive_summary: string;
  detailed_analysis: string;
  methodology: string;
  implications: string;
  research_gaps: string;
} {
  const sections = {
    executive_summary: '',
    detailed_analysis: '',
    methodology: '',
    implications: '',
    research_gaps: '',
  };

  // Split by section headers
  const sectionPatterns = [
    { key: 'executive_summary', regex: /(?:^|\n)##\s*1\.\s*Executive\s+Summary\n([\s\S]*?)(?=\n##\s*2\.|$)/i },
    { key: 'detailed_analysis', regex: /(?:^|\n)##\s*2\.\s*Detailed\s+Analysis\n([\s\S]*?)(?=\n##\s*3\.|$)/i },
    { key: 'methodology', regex: /(?:^|\n)##\s*3\.\s*Methodology\n([\s\S]*?)(?=\n##\s*4\.|$)/i },
    { key: 'implications', regex: /(?:^|\n)##\s*4\.\s*Implications\n([\s\S]*?)(?=\n##\s*5\.|$)/i },
    { key: 'research_gaps', regex: /(?:^|\n)##\s*5\.\s*Research\s+Gaps\n([\s\S]*?)(?=$)/i },
  ];

  for (const pattern of sectionPatterns) {
    const match = text.match(pattern.regex);
    if (match && match[1]) {
      sections[pattern.key as keyof typeof sections] = match[1].trim();
    }
  }

  return sections;
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
