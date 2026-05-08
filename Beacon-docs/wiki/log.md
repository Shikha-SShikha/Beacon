# Session Log

Append-only. One entry per session. Most recent at top.

---

## 2026-04-27

**Context sync + wiki creation**

Confirmed state of all components:
- HTML-scrape baseline is implemented: `experiment.py` builds `html_scrape` collection (figures=`[IMAGE]`, tables=caption only, text=plain). `/baseline` and `/baseline/ask` API endpoints query it.
- Staged enrichment POC is complete: `stage_copyedit.py`, `stage_mastercopy.py`, `review_app.py` all built and run. Manifests exist at `.tmp/enrichment_copyedit.json` (107KB) and `.tmp/enrichment_mastercopy.json` (179KB).
- `experiment.py` updated: fixed docstring in `build_collections()` which incorrectly claimed 4 collections but only built 2 (`html_scrape` + `entity_enriched`).
- Created `Beacon-docs/wiki/` — Karpathy-style persistent wiki. Wiki is now the authoritative current state; other Beacon-docs are archival.
- Archived `Next steps.md` and updated `Tracker.md` — both were stale.

**Open items carried forward:** Top-K recall UI view, figure-specific example queries, entity-level query demos.

---

## 2026-04-08 (approx)

**NER pipeline + corpus expansion**

Added NER Stage 1 + entity tagging (Step 5) to pipeline. Expanded corpus to 15 articles. Rebuilt `entity_enriched` collection. Added `entity_enriched` as primary search collection. Old `raw`/`metadata`/`enriched` collections from original 2-article POC are no longer used.

---

## 2026-04-05

**Staged enrichment POC**

Built `stage_copyedit.py` — NER Stage 1 on Copyedit.xml, output draft manifest.
Built `stage_mastercopy.py` — diff, ontology resolution on Proof .xml, output verified manifest.
Built `review_app.py` — Streamlit HITL review interface.

---

## 2026-04-03 (approx)

**Phase 5 + 6**

Phase 5: Figure cross-linking (`cross_link_figures()` in pipeline.py, `fetch_linked_figures()` in search_service.py). 100% of corpus figures cited by at least one text chunk.

Phase 6: Claim-extracting figure/table summaries. Changed `summarise_float()` prompt from descriptive to factual-claim style.

---

## 2026-03-30 (approx)

**Phase 3 + 4, API, demo tool**

Phase 3: Hybrid BM25 + dense search with RRF fusion.
Phase 4: HyDE query expansion.
Built FastAPI backend (`api/`).
Built `tools/demo_comparison.py` — 5 curated scenarios.
Built `tools/generate_onepager.py`.
Added governance layer (`governance/license_service.py`).

---

## 2026-03-24 (approx)

**React UI, Phase 1 + 2**

Phase 1: Paragraph chunking, small paragraph merging, cross-chunk overlap.
Phase 2: Section reranking + recency boost (query-time, no pipeline rebuild).
Built `beacon-ui/` — React + Vite + Tailwind.

---

## Earlier

Original 2-article POC: `pipeline.py` parsing Elsevier XML, contextual prefixes, figure summarisation, ChromaDB, Streamlit chat app. Proved enriched wins on conceptual queries; metadata wins on topic queries. Identified correct baseline is HTML scrape vs enriched XML.
