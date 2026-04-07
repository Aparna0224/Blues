/* ── Request / Response types matching FastAPI Pydantic models ── */

export interface QueryRequest {
  query: string;
  num_documents: number;
  mode: 'dynamic' | 'cached';
  paper_source?: 'openalex' | 'semantic_scholar' | 'arxiv' | 'both' | 'all';
  include_summary: boolean;
  user_level?: 'auto' | 'beginner' | 'intermediate' | 'advanced';
  user_id?: string;
  project_id?: string;
  filters?: QueryFilters | null;
}

export interface QueryFilters {
  section?: string;
  category?: string;
  tags?: string[];
  year?: { min?: number; max?: number };
  title_contains?: string;
  source?: string;
}

export interface ProjectRecord {
  project_id: string;
  user_id: string;
  name: string;
  description: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateRequest {
  name: string;
  description?: string;
  user_id?: string;
}

export interface ProjectUpdateRequest {
  name?: string;
  description?: string;
}

export interface HardDeleteProjectResponse {
  status: string;
  project_id: string;
  project_deleted: number;
  queries_deleted: number;
  query_results_deleted: number;
  traces_deleted: number;
}

export interface QueryHistoryItem {
  query_id: string;
  project_id: string;
  user_id: string;
  query_text: string;
  mode: string;
  paper_source: string;
  user_level: string;
  status: string;
  execution_id: string;
  chunks_used: number;
  papers_found: number;
  created_at: string;
}

export interface PaperInfo {
  paper_id: string;
  title: string;
  authors: string;
  year: string;
  doi: string;
}

/** Matches the nested structure from verification.py verify() */
export interface VerificationMetrics {
  avg_similarity: number;
  source_diversity: number;
  normalized_source_diversity: number;
  evidence_density: number;
  conflicts_detected: string[];
}

export interface VerificationAudit {
  total_claims_received: number;
  claims_after_dedup: number;
  claims_after_relevance_filter: number;
  claims_above_similarity_threshold: number;
  claims_used_for_scoring: number;
  claims_rejected: number;
}

export interface VerificationResult {
  confidence_score: number;
  metrics: VerificationMetrics;
  warnings: string[];
  audit: VerificationAudit;
}

export interface PlanningInfo {
  main_question: string;
  sub_questions: string[];
  search_queries: string[];
  latency_ms: number;
}

export interface QueryResponse {
  query_id?: string;
  project_id?: string;
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
