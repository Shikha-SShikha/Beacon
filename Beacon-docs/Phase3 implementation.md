# Phase 3 — Hybrid BM25 + Dense Vector Search

**Addresses:** A1 (terminology mismatch), A2 (synonym gap), A3 (OOV/rare token fragmentation)

**Status:** Complete

---

## Problem

Dense embeddings (text-embedding-3-small) struggle with exact biomedical terms:
- ALK, PAI-1, METTL3 get split into meaningless subword tokens
- AI prefix text dilutes the exact-term signal (ALK query was -12.7% worse with enrichment)
- Terminology mismatch: "parasite immune evasion" vs "T. annulata infection" — embeddings don't bridge arbitrary synonym gaps

BM25 excels at exact term matching regardless of tokenisation. Combining both gives the best of both worlds.

---

## Architecture

```
Query
  ├── Dense path: embed query → ChromaDB vector search → ranked by cosine distance
  ├── Sparse path: tokenize query → BM25 index search → ranked by BM25 score
  └── Fusion: Reciprocal Rank Fusion (RRF) combines both rankings
        ↓
  Phase 2 reranking (section boost + recency)
        ↓
  License filtering → Response
```

---

## Reciprocal Rank Fusion (RRF)

**Formula:**
```
rrf_score = 1/(k + rank_vector) + 1/(k + rank_bm25)
```

- `k = 60` (standard constant from Cormack et al., 2009)
- Higher k = less influence from top ranks, more uniform blending
- Documents found by only one source get `default_rank = fetch_n + 1` for the other

**Why RRF over score normalisation:**
- BM25 scores and cosine distances are on incompatible scales
- RRF only uses rank positions — no score calibration needed
- Robust, well-studied, used in production by Elasticsearch and others

**Candidate pool:**
- Fetch `top_k * 3` (max 30) from each source
- Union all candidates, compute RRF score, return top N

---

## BM25 Index

### Singleton pattern

The BM25 index is built once from ChromaDB on first search, then cached in memory. No separate storage needed.

**File:** `api/services/bm25_index.py`

### Tokenizer

Custom tokenizer tuned for biomedical text:
```python
re.findall(r'[a-zA-Z0-9][\w\-/]*[a-zA-Z0-9]|[a-zA-Z0-9]', text.lower())
```

- Lowercased
- Keeps hyphens within tokens: `PAI-1` → `["pai-1"]` (not `["pai", "1"]`)
- Keeps slashes within tokens: `m6A` stays intact
- Strips outer punctuation but preserves internal structure

### Index rebuild

Call `rebuild_bm25_index()` after any ChromaDB collection update (experiment rebuild, new articles ingested).

---

## Files Changed

| File | Change |
|---|---|
| `api/services/bm25_index.py` | **New.** BM25Index class, tokenizer, singleton builder from ChromaDB. |
| `api/services/search_service.py` | Added `bm25_search()`, `hybrid_search()` with RRF. |
| `api/routers/search.py` | Routes to `hybrid_search()` when `req.hybrid=True` (default). Passes `HybridDebug` to response. |
| `api/models.py` | Added `HybridDebug` model (rrf_score, vector_rank, bm25_rank). Added `hybrid: bool` to `SearchRequest`. Added `hybrid_debug` to `SearchResult`. |

---

## API Contract Changes

### SearchRequest (new field)

```json
{
  "query": "ALK translocation FISH",
  "institution_id": "elsevier_internal",
  "top_k": 6,
  "hybrid": true,
  "section_boost": true,
  "recency_weight": 0.10
}
```

- `hybrid` (default `true`): use BM25+vector fusion. Set `false` for vector-only (Phase 1 behaviour).

### SearchResult (new field)

```json
{
  "rank": 1,
  "distance": 0.442,
  "raw_distance": 0.50,
  "hybrid_debug": {
    "rrf_score": 0.032787,
    "vector_rank": 1,
    "bm25_rank": 3
  },
  "rerank_debug": {
    "intent": "factual",
    "section_multiplier": 0.85,
    "recency_multiplier": 1.02
  }
}
```

---

## Search Pipeline Order

```
1. Embed query (OpenAI)
2. If hybrid=true:
     a. Vector search (ChromaDB) → top 3*k results with distances
     b. BM25 search (in-memory) → top 3*k results with BM25 scores
     c. RRF fusion → combined ranking
   Else:
     a. Vector search only
3. Phase 2 reranking (section boost + recency multipliers)
4. License filtering (ALLOWED / SNIPPET_ONLY / NO_ACCESS)
5. Return top_k results with debug info
```

---

## Validation Results

BM25 correctly surfaces exact biomedical terms:

| Query | BM25 Rank-1 Source | Correct? |
|---|---|---|
| ALK translocation FISH | BJ_100840 (discussion) | Yes |
| PAI-1 inhibition | BJ_100950 (other) | Yes |
| METTL3 m6A | BJ_100828 | Yes |
| EV charging optimization | ESR-102126 (results) | Yes |

These are the queries where pure vector search regressed with enrichment (-12.7% for ALK, -4.8% for PAI-1). BM25 provides an exact-match safety net that prevents those regressions.

---

## Note on Current ChromaDB State

Current ChromaDB has 195 documents (from a pre-chunking-overhaul build). After rebuilding experiment collections with the 903 paragraph-level chunks, the BM25 index will automatically pick up all documents on next load. Call `rebuild_bm25_index()` after any `experiment.py` run.
