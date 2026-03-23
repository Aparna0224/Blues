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

/** Inference summary from InferenceEngine */
export interface InferenceSummary {
  methodology_insights_count: number;
  experimental_findings_count: number;
  inference_chains_count: number;
  overall_confidence: number;
}

/** 5-section answer structure */
export interface FiveSectionAnswer {
  executive_summary: string;
  detailed_analysis: string;
  methodology: string;
  implications: string;
  research_gaps: string;
}

export interface QueryResponse {
  execution_id: string;
  query: string;
  mode: string;
  status: string;
  planning: PlanningInfo;
  grouped_answer: string;
  
  // NEW: 5-section answer fields
  answer_structure?: string; // "5-section" or undefined for backward compat
  answer_confidence?: number; // 0-1 confidence score
  inference_summary?: InferenceSummary; // Inference metrics
  five_section_answer?: FiveSectionAnswer; // Parsed 5-section answer
  inferences_confidence?: number; // Inference confidence 0-1
  
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
