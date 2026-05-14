export interface LicenseDecision {
  decision: "ALLOWED" | "SNIPPET_ONLY" | "OPEN_ACCESS";
  rights: "RAG_READ_RAG_SOURCE" | "RAG" | "OPEN_ACCESS";
  journal_code: string;
  reason: string;
}

export interface ChunkMetadata {
  title: string;
  section: string;
  source: string;
  doi: string;
  entities: string; // raw JSON string
  chunk_type: string; // "text" | "table" | "figure"
}

export interface Entity {
  text: string;
  type: string;
  id: string | null;
  ontology: string | null;
}

export interface LinkedFigure {
  id: string;
  chunk_type: string;
  text: string;
}

export interface RerankDebug {
  intent: string;
  section_multiplier: number;
  recency_multiplier: number;
}

export interface HybridDebug {
  rrf_score: number;
  vector_rank: number | null;
  bm25_rank: number | null;
}

export interface SearchResult {
  rank: number;
  distance: number;
  raw_distance?: number;
  license: LicenseDecision;
  metadata: ChunkMetadata;
  text: string;
  linked_figures?: LinkedFigure[];
  rerank_debug?: RerankDebug | null;
  hybrid_debug?: HybridDebug | null;
}

export interface SearchStats {
  full_text: number;
  snippet_only: number;
  open_access: number;
  total: number;
}

export interface UpgradeHint {
  locked_count: number;
  journal_names: string[];
}

export interface SearchResponse {
  query: string;
  institution_id: string;
  results: SearchResult[];
  stats: SearchStats;
  upgrade_hint: UpgradeHint | null;
}

export interface LicensedJournal {
  code: string;
  name: string;
  publisher: string;
  color: string;
  rights: string;
}

export interface InstitutionSummary {
  id: string;
  name: string;
  avatar: string;
  description: string;
  licensed_journals: LicensedJournal[];
}

export interface JournalInfo {
  name: string;
  publisher: string;
  color: string;
}

export interface SearchExchange {
  query: string;
  response: SearchResponse;
}

export interface CorpusArticle {
  doi: string;
  title: string;
  authors: string[];
  year: string;
  journal_code: string;
  source: string;
  shared_refs?: number;
  shared_authors?: string[];
}

export interface FoundationalPaper {
  title: string;
  authors: string[];
  year: string;
  journal: string;
  cited_by_corpus?: number;
  cited_by_count?: number;
}

// ─── Ask (RAG answer) types ─────────────────────────────────────────────

export interface SourceSection {
  section: string;
  chunk_type: string;
  text: string;
  section_title?: string;
  subsection_title?: string;
}

export interface HighlightEntity {
  text: string;
  type: string;   // GENE | PROTEIN | DISEASE | CHEMICAL | DRUG | RNA | CELL_LINE | CONCEPT | ENTITY | METHOD | ORGANISM | ...
  id: string | null;
  ontology: string | null;
}

export interface CitedSource {
  citation_id: number;
  source: string;
  title: string;
  journal_code: string;
  year: string;
  doi: string;
  sections: SourceSection[];
  license_decision: string;  // "ALLOWED" | "SNIPPET_ONLY" | "OPEN_ACCESS"
  publisher: string;
  entity_count?: number;
  relation_count?: number;
  entities?: HighlightEntity[];
}

export interface AskResponse {
  query: string;
  answer: string;
  sources: CitedSource[];
}

export interface AskExchange {
  query: string;
  response: AskResponse;
}

// ─── Baseline types ─────────────────────────────────────────────────────

export interface BaselineHit {
  rank: number;
  distance: number;
  source: string;
  title: string;
  section: string;
  chunk_type: string;
  text: string;
}

export interface BaselineResponse {
  query: string;
  hits: BaselineHit[];
}

// ─── Attribution types ───────────────────────────────────────────────────

export interface AttributionSourceEvent {
  citation_id: number;
  title: string;
  journal_code: string;
  publisher_label: string;
  doi: string;
  sections_used: string[];
  license_decision: string;
  entity_count: number;
}

export interface BlockedAttempt {
  journal_code: string;
  publisher_label: string;
  article_count: number;
}

export interface FeedEvent {
  event_id: string;
  event_type: "served" | "blocked";
  timestamp: string;
  query: string;
  institution_id: string;
  agent_label: string;
  // served
  sources: AttributionSourceEvent[];
  // blocked
  attempted: BlockedAttempt[];
  articles_attempted: number;
  articles_served: number;
  block_reason: string;
}

export interface PublisherSummary {
  label: string;
  queries_served: number;
  article_citations: number;
  queries_blocked: number;
  institution_count: number;
  top_sections: { section: string; count: number }[];
}

export interface AttributionSummary {
  total_events: number;
  total_served: number;
  total_blocked: number;
  publishers: PublisherSummary[];
}

// Keep for backwards compat if referenced elsewhere
export type AttributionEvent = FeedEvent;

export interface CitationContextData {
  related_corpus: CorpusArticle[];
  by_same_author: CorpusArticle[];
  foundational: FoundationalPaper[];
}
