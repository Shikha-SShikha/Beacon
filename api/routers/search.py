from fastapi import APIRouter, HTTPException
from ..models import (
    SearchRequest, SearchResponse, SearchResult, RerankDebug, HybridDebug,
    LinkedFigure, SearchStats, LicenseDecision, ChunkMetadata, UpgradeHint,
)
from ..services.search_service import embed_query, raw_search, hybrid_search, fetch_linked_figures
from ..services.reranker import rerank
from ..services.hyde import expand_query_hyde
from ..services.attribution_service import (
    log_search_attribution,
    get_journal_code_from_source,
    get_domain_for_journal,
)
from governance.license_service import check_license, load_config

router = APIRouter(prefix="/search", tags=["search"]) 


@router.post("", response_model=SearchResponse)
def search(req: SearchRequest):
    config = load_config()
    if req.institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")

    try:
        # Phase 4: HyDE expands query into a hypothetical document for embedding
        embed_text = expand_query_hyde(req.query) if req.hyde else req.query
        q_embed = embed_query(embed_text)
        fetch_n = min(req.top_k * 3, 20)

        if req.hybrid:
            # Phase 3: hybrid BM25 + vector via RRF
            # BM25 always uses the original query (exact terms matter)
            raw_hits = hybrid_search(req.query, q_embed, n=fetch_n)
        else:
            raw_hits = raw_search(q_embed, n=fetch_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Search service unavailable")

    # Phase 2: rerank using section metadata + recency
    raw_hits = rerank(
        raw_hits,
        query=req.query,
        section_boost=req.section_boost,
        recency_weight=req.recency_weight,
    )

    # Phase 5: fetch linked figure/table chunks for retrieved text chunks
    linked_figures_map = fetch_linked_figures(raw_hits)

    results = []
    locked_journals: set[str] = set()

    for hit in raw_hits:
        meta = hit["metadata"]
        decision = check_license(req.institution_id, meta)

        if decision["decision"] == "NO_ACCESS":
            journal_code = decision["journal_code"]
            journal_name = config["journals"].get(journal_code, {}).get("name", journal_code)
            locked_journals.add(journal_name)
            continue

        if len(results) < req.top_k:
            rerank_dbg = hit.get("rerank_debug")
            hybrid_dbg = None
            if req.hybrid and hit.get("rrf_score") is not None:
                hybrid_dbg = HybridDebug(
                    rrf_score=hit["rrf_score"],
                    vector_rank=hit.get("vector_rank"),
                    bm25_rank=hit.get("bm25_rank"),
                )

            # Phase 5: attach linked figures/tables
            linked = [
                LinkedFigure(id=fig["id"], chunk_type=fig["type"], text=fig["text"][:500])
                for fig in linked_figures_map.get(hit["id"], [])
            ]

            # Extract attribution metadata
            source = meta.get("source", "")
            journal_code = get_journal_code_from_source(source)
            domain = get_domain_for_journal(journal_code)
            access_level = decision["decision"]

            # Log attribution for metered usage tracking
            log_search_attribution(
                institution_id=req.institution_id,
                article_id=source,
                query=req.query,
                access_level=access_level,
                rank=len(results) + 1,
            )

            results.append(SearchResult(
                rank=len(results) + 1,
                distance=hit["distance"],
                raw_distance=hit.get("raw_distance", hit["distance"]),
                license=LicenseDecision(**decision),
                metadata=ChunkMetadata(
                    title=meta.get("title", ""),
                    section=meta.get("section", ""),
                    source=meta.get("source", ""),
                    doi=meta.get("doi", ""),
                    entities=meta.get("entities", "[]"),
                    chunk_type=meta.get("type", ""),
                ),
                text=hit["text"],
                linked_figures=linked,
                rerank_debug=RerankDebug(**rerank_dbg) if rerank_dbg else None,
                hybrid_debug=hybrid_dbg,
                article_id=source,
                journal_code=journal_code,
                domain=domain,
                access_level=access_level,
            ))

    stats = SearchStats(
        full_text=sum(1 for r in results if r.license.decision == "ALLOWED"),
        snippet_only=sum(1 for r in results if r.license.decision == "SNIPPET_ONLY"),
        open_access=sum(1 for r in results if r.license.decision == "OPEN_ACCESS"),
        total=len(results),
    )

    upgrade_hint = (
        UpgradeHint(
            locked_count=sum(1 for h in raw_hits
                             if check_license(req.institution_id, h["metadata"])["decision"] == "NO_ACCESS"),
            journal_names=sorted(locked_journals),
        )
        if locked_journals else None
    )

    return SearchResponse(
        query=req.query,
        institution_id=req.institution_id,
        results=results,
        stats=stats,
        upgrade_hint=upgrade_hint,
    )
