/* ── Request / Response types matching FastAPI Pydantic models ── */

export interface QueryRequest {
  query: string;
  num_documents: number;
  mode: 'dynamic' | 'cached';
  include_summary: boolean;
}

export interface PaperInfo {
  paper_id: string;
  title: string;
  authors: string;
  year: string;
  doi: string;
}

export interface AuditInfo {
  total_claims_received: number;
  claims_after_dedup: number;
  claims_after_relevance_filter: number;
  claims_above_similarity_threshold: number;
  claims_rejected: number;
  dedup_removed: number;
  relevance_removed: number;
  similarity_gated: number;
  calibration_applied: boolean;
  avg_similarity: number;
  calibration_multiplier: number;
}

export interface VerificationResult {
  confidence_score: number;
  confidence_label: string;
  similarity_score: number;
  diversity_score: number;
  evidence_density: number;
  conflict_detected: boolean;
  conflict_details: string[];
  unique_papers: number;
  total_claims: number;
  audit: AuditInfo;
}

export interface PlanningInfo {
  main_question: string;
  sub_questions: string[];
  search_queries: string[];
  latency_ms: number;
}

export interface QueryResponse {
  execution_id: string;
  query: string;
  mode: string;
  status: string;
  planning: PlanningInfo;
  grouped_answer: string;
  chunks_used: number;
  papers_found: PaperInfo[];
  verification: VerificationResult;
  summary: string | null;
  total_time_ms: number;
  warnings: string[];
}

export interface UploadResponse {
  status: string;
  paper_id: string;
  title: string;
  chunks_created: number;
  vectors_added: number;
}

export interface StatusResponse {
  mongodb: string;
  papers_count: number;
  chunks_count: number;
  faiss_vectors: number;
  llm_provider: string;
  llm_model: string;
}
