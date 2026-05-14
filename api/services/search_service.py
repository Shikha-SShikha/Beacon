"""
Search service - vector search, BM25 search, hybrid (RRF) fusion,
and figure-claim expansion (Phase 5).
"""

import json
from .clients import get_openai, get_chroma, EMBED_MODEL
from .bm25_index import get_bm25_index


def embed_query(query: str) -> list[float]:
    client = get_openai()
    return client.embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding


def raw_search(q_embed: list[float], n: int = 10) -> list[dict]:
    """Pure vector (dense) search against ChromaDB."""
    chroma = get_chroma()
    collection = chroma.get_collection("entity_enriched")
    res = collection.query(query_embeddings=[q_embed], n_results=n)
    return [
        {
            "id": res["ids"][0][i],
            "rank": i + 1,
            "distance": round(res["distances"][0][i], 4),
            "metadata": res["metadatas"][0][i],
            "text": res["documents"][0][i],
        }
        for i in range(len(res["ids"][0]))
    ]


def bm25_search(query: str, n: int = 10) -> list[dict]:
    """Pure BM25 (sparse) search."""
    index = get_bm25_index()
    return index.search(query, n=n)


def hybrid_search(query: str, q_embed: list[float], n: int = 10, k: int = 60) -> list[dict]:
    """Hybrid search using Reciprocal Rank Fusion (RRF) with Source Diversification."""
    # Fetch more candidates from each source for better fusion
    fetch_n = min(n * 4, 50) 
    vector_hits = raw_search(q_embed, n=fetch_n)
    bm25_hits = bm25_search(query, n=fetch_n)

    # Build rank maps
    vector_ranks = {h["id"]: h["rank"] for h in vector_hits}
    vector_docs = {h["id"]: h for h in vector_hits}
    bm25_ranks = {h["id"]: h["bm25_rank"] for h in bm25_hits}
    bm25_docs = {h["id"]: h for h in bm25_hits}

    all_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
    default_rank = fetch_n + 1

    fused = []
    for doc_id in all_ids:
        v_rank = vector_ranks.get(doc_id, default_rank)
        b_rank = bm25_ranks.get(doc_id, default_rank)
        rrf_score = 1.0 / (k + v_rank) + 1.0 / (k + b_rank)

        doc = vector_docs.get(doc_id) or bm25_docs[doc_id]
        v_distance = vector_docs[doc_id]["distance"] if doc_id in vector_docs else 2.0

        fused.append({
            "id": doc_id,
            "rank": 0,
            "distance": v_distance,
            "rrf_score": rrf_score,
            "vector_rank": v_rank if doc_id in vector_ranks else None,
            "bm25_rank": b_rank if doc_id in bm25_ranks else None,
            "metadata": doc["metadata"],
            "text": doc["text"],
        })

    fused.sort(key=lambda h: h["rrf_score"], reverse=True)

    # --- Source Diversification ---
    source_counts = {}
    for hit in fused:
        source = hit["metadata"].get("source", "unknown")
        count = source_counts.get(source, 0)
        # Apply a soft penalty to subsequent chunks from the same source
        hit["div_score"] = hit["rrf_score"] * (0.8 ** count)
        source_counts[source] = count + 1

    fused.sort(key=lambda h: h["div_score"], reverse=True)

    # Assign final ranks and trim
    for i, hit in enumerate(fused[:n]):
        hit["rank"] = i + 1
        hit["rrf_score"] = round(hit["rrf_score"], 6)

    return fused[:n]


# ─── Figure-Claim Expansion (Phase 5) ───────────────────────────────────────

def fetch_linked_figures(hits: list[dict]) -> dict[str, list[dict]]:
    """For each retrieved text chunk, fetch its linked figure/table chunks."""
    chroma = get_chroma()
    collection = chroma.get_collection("entity_enriched")

    all_ref_ids = []
    hit_to_refs = {}

    for hit in hits:
        meta = hit.get("metadata") or {}
        figure_refs_raw = meta.get("figure_refs", "[]")
        try:
            figure_refs = json.loads(figure_refs_raw) if isinstance(figure_refs_raw, str) else figure_refs_raw
        except (json.JSONDecodeError, TypeError):
            figure_refs = []

        if not figure_refs:
            continue

        doi_prefix = hit["id"].split("::")[0] if "::" in hit["id"] else ""
        full_ids = []
        for fref in figure_refs:
            full_id = f"{doi_prefix}::{fref}" if doi_prefix else fref
            full_ids.append(full_id)
            if full_id not in all_ref_ids:
                all_ref_ids.append(full_id)

        hit_to_refs[hit["id"]] = full_ids

    if not all_ref_ids:
        return {}

    try:
        fetched = collection.get(ids=all_ref_ids, include=["documents", "metadatas"])
    except Exception:
        return {}

    fig_lookup = {}
    for i, doc_id in enumerate(fetched["ids"]):
        fig_lookup[doc_id] = {
            "id": doc_id,
            "type": fetched["metadatas"][i].get("type", ""),
            "text": fetched["documents"][i],
        }

    result = {}
    for hit_id, ref_ids in hit_to_refs.items():
        linked = [fig_lookup[rid] for rid in ref_ids if rid in fig_lookup]
        if linked:
            result[hit_id] = linked

    return result


def fetch_figures_for_source(source: str, max_figures: int = 3) -> list[dict]:
    """Fetch figure and table chunks for a source article directly from ChromaDB.

    Used when figure_refs cross-links are absent — guarantees every cited
    article surfaces at least its top figures/tables in the sources panel.
    """
    chroma = get_chroma()
    collection = chroma.get_collection("entity_enriched")
    try:
        res = collection.get(
            where={"$and": [{"source": source}, {"type": {"$in": ["figure", "table"]}}]},
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    results = []
    for i, doc_id in enumerate(res["ids"]):
        results.append({
            "id": doc_id,
            "type": res["metadatas"][i].get("type", "figure"),
            "text": res["documents"][i],
        })
    return results[:max_figures]
