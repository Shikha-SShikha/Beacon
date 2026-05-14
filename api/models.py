from pydantic import BaseModel, Field
from typing import Optional


class LicenseDecision(BaseModel):
    decision: str       # "ALLOWED" | "SNIPPET_ONLY" | "OPEN_ACCESS"
    rights: str         # "RAG_READ_RAG_SOURCE" | "RAG" | "OPEN_ACCESS"
    journal_code: str
    reason: str


class ChunkMetadata(BaseModel):
    title: str = ""
    section: str = ""
    source: str = ""
    doi: str = ""
    entities: str = "[]"
    chunk_type: str = ""   # "text" | "table" | "figure"


class RerankDebug(BaseModel):
    intent: str
    section_multiplier: float
    recency_multiplier: float


class HybridDebug(BaseModel):
    rrf_score: float = 0.0
    vector_rank: Optional[int] = None
    bm25_rank: Optional[int] = None


class LinkedFigure(BaseModel):
    id: str
    chunk_type: str     # "figure" | "table"
    text: str           # AI summary + caption


class SearchResult(BaseModel):
    rank: int
    distance: float
    raw_distance: float = 0.0
    license: LicenseDecision
    metadata: ChunkMetadata
    text: str
    linked_figures: list[LinkedFigure] = []
    rerank_debug: Optional[RerankDebug] = None
    hybrid_debug: Optional[HybridDebug] = None
    article_id: str = ""        # e.g., "BJ_100850"
    journal_code: str = ""      # e.g., "BJ"
    domain: str = ""            # e.g., "Biomedical"
    access_level: str = ""      # "FULL_TEXT" | "SNIPPET_ONLY" | "OPEN_ACCESS"


class SearchStats(BaseModel):
    full_text: int
    snippet_only: int
    open_access: int
    total: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    institution_id: str
    top_k: int = Field(default=6, ge=1, le=20)
    section_boost: bool = Field(default=True, description="Enable query-dependent section reranking")
    recency_weight: float = Field(default=0.10, ge=0.0, le=0.5, description="Linear recency decay weight (0 = disabled)")
    hybrid: bool = Field(default=True, description="Enable hybrid BM25+vector search via RRF")
    hyde: bool = Field(default=False, description="Enable HyDE query expansion (adds ~1s latency from LLM call)")


class UpgradeHint(BaseModel):
    locked_count: int          # number of results hidden due to missing licence
    journal_names: list[str]   # display names of journals that have locked content


class SearchResponse(BaseModel):
    query: str
    institution_id: str
    results: list[SearchResult]
    stats: SearchStats
    upgrade_hint: UpgradeHint | None = None


# ─── Ask (RAG answer) models ──────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    institution_id: str
    top_k: int = Field(default=10, ge=1, le=20)


class SourceSection(BaseModel):
    section: str           # "results", "methods", "discussion", "figure", "table", "other"
    chunk_type: str        # "text", "figure", "table"
    text: str              # relevant snippet
    section_title: str = ""      # actual heading from paper, e.g. "Mechanisms of resistance…"
    subsection_title: str = ""   # subsection heading, e.g. "SLC7A11 and GPX4 antioxidant system"


class CitedSource(BaseModel):
    citation_id: int      # 1, 2, 3...
    source: str           # "BJ_100828"
    title: str
    journal_code: str
    year: str
    doi: str
    sections: list[SourceSection]
    license_decision: str = "ALLOWED"   # "ALLOWED" | "SNIPPET_ONLY" | "OPEN_ACCESS"
    publisher: str = ""                 # e.g. "Portland Press"
    entity_count: int = 0               # Total enriched entities in source
    relation_count: int = 0             # Total semantic relations in source
    entities: list[dict] = []           # Deduplicated entities for answer highlighting


class AskResponse(BaseModel):
    query: str
    answer: str           # synthesized answer with [1], [2] markers
    sources: list[CitedSource]


class JournalInfo(BaseModel):
    name: str
    publisher: str
    color: str


class LicensedJournal(BaseModel):
    code: str
    name: str
    publisher: str
    color: str
    rights: str


class InstitutionSummary(BaseModel):
    id: str
    name: str
    avatar: str
    description: str
    licensed_journals: list[LicensedJournal]


class InstitutionsResponse(BaseModel):
    institutions: list[InstitutionSummary]


class JournalsResponse(BaseModel):
    journals: dict[str, JournalInfo]


# ─── Collections models ────────────────────────────────────────────

class ArticleInfo(BaseModel):
    article_id: str
    journal_code: str
    domain: str
    doi: str = ""
    chunks: int
    entities: int


class JournalInCollection(BaseModel):
    journal_code: str
    journal_name: str
    color: str
    article_count: int
    total_chunks: int
    total_entities: int
    articles: list[ArticleInfo]


class DomainInCollection(BaseModel):
    domain: str
    journal_count: int
    article_count: int
    total_chunks: int
    total_entities: int
    journals: list[JournalInCollection]


class CollectionsSummary(BaseModel):
    institution_id: str
    total_domains: int
    total_journals: int
    total_articles: int
    total_chunks: int
    total_entities: int
    collections: list[DomainInCollection]
