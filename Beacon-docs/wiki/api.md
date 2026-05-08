# API Reference

**File:** `api/main.py`
**Framework:** FastAPI
**Start:** `uvicorn api.main:app --reload`
**CORS:** localhost:5173, 5174, 3000 (React dev server)

---

## Routes

### `POST /search`
Hybrid BM25 + vector search against `entity_enriched`.

- Applies Phase 2 section reranking + recency boost
- Fetches linked figures for top results
- License-filtered by institution

**Request:** `{ query, institution_id, top_k }`
**Response:** ranked hits with `linked_figures` per hit

---

### `POST /ask`
Full RAG — hybrid retrieval + GPT-4o-mini synthesis.

- Same retrieval as `/search`
- HyDE expansion optionally applied
- Groups results by source paper, builds citation-aware context block
- Returns answer + cited sources with sections

**Request:** `{ query, institution_id, top_k }`
**Response:** `AskResponse { query, answer, sources: [CitedSource] }`

---

### `POST /baseline`
Plain vector search against `html_scrape` collection. No hybrid BM25, no reranking, no figure linking.

Returns raw ranked chunks for inspection. This is the "before" comparison endpoint.

---

### `POST /baseline/ask`
Same as `/baseline` retrieval + GPT-4o-mini synthesis. Identical LLM and prompt as `/ask` — only retrieval differs.

This is the controlled comparison: hold everything constant, change only the collection.

---

### `POST /citation`
Citation graph lookup. Uses `citation_graph.json`.

---

### `GET /institutions`
Returns list of institutions from `governance/license_config.json`.

---

### `GET /journals`
Returns journal metadata from `governance/license_config.json`.

---

### `GET /health`
`{ status: "ok" }` — liveness check.

---

## Services

| Service | File | Purpose |
|---|---|---|
| `search_service` | `api/services/search_service.py` | `hybrid_search()`, `embed_query()`, `fetch_linked_figures()` |
| `reranker` | `api/services/reranker.py` | Section boost + recency decay |
| `bm25_index` | `api/services/bm25_index.py` | In-memory BM25 index over entity_enriched |
| `hyde` | `api/services/hyde.py` | HyDE query expansion via GPT-4o-mini |
| `citation_service` | `api/services/citation_service.py` | Citation graph queries |
| `clients` | `api/services/clients.py` | Singletons: `get_chroma()`, `get_openai()` |

---

## Governance

`governance/license_service.py` — `check_license(institution_id, chunk_metadata)` → `{decision: FULL_ACCESS | ABSTRACT_ONLY | NO_ACCESS}`.

Config in `governance/license_config.json` (institutions, journals, access tiers).
