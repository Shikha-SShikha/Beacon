# Open Items

> Last updated: 2026-04-27

These are the genuinely open tasks. Everything else is done.

---

## 1. Top-K Recall View in UI

**What:** Show top-N results from both `html_scrape` and `entity_enriched` side-by-side in the React UI. Add a slider for K (default 3 or 5).

**Why:** Rank-1 distance framing makes enrichment look weak. Top-K recall shows that enriched surfaces more relevant chunks overall — especially for figure and entity queries.

**Where:** `beacon-ui/src/` — SearchPage or a new ComparisonPage. Calls `/baseline` and `/search` in parallel.

---

## 2. Figure-Specific Example Queries in UI

**What:** Add example query tabs for: *"show me a diagram of the decision architecture"*, *"which figure compares network topologies"*.

**Why:** These are the queries that most clearly show the figure visibility gap. `html_scrape` returns `[IMAGE]`; `entity_enriched` returns the claim-extracting summary.

**Where:** `beacon-ui/src/pages/SearchPage.tsx` — example query tabs.

---

## 3. Entity-Level Query Demos

**What:** Once NER entities are wired into search filtering, add example queries like: *"articles mentioning EGFR inhibitors in the methods section"*.

**Why:** These queries are only answerable with entity-tagged content. They make the clearest possible case for the enrichment pipeline.

**Dependency:** Requires a search filter on `entities` metadata in ChromaDB. The entities are already stored in chunk metadata — the filter just needs to be exposed in `/search`.

---

## Completed (moved here to avoid confusion)

- ~~HTML-scraped baseline~~ ✅ `html_scrape` collection in experiment.py + `/baseline` API endpoint
- ~~Staged enrichment POC~~ ✅ stage_copyedit.py, stage_mastercopy.py, review_app.py
- ~~Figure cross-linking~~ ✅ Phase 5 (pipeline.py + search_service.py)
- ~~Claim-extracting figure summaries~~ ✅ Phase 6 (pipeline.py)
- ~~HyDE query expansion~~ ✅ Phase 4 (api/services/hyde.py)
- ~~Hybrid BM25 + vector search~~ ✅ Phase 3 (api/services/bm25_index.py)
- ~~Section reranking + recency boost~~ ✅ Phase 2 (api/services/reranker.py)
- ~~Paragraph chunking~~ ✅ Phase 1 (pipeline.py)
