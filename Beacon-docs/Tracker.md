# Tracker

> Active work is tracked in `Beacon-docs/wiki/open-items.md`.

## Open

- [ ] Top-K recall view in the React UI (side-by-side baseline vs Beacon, K slider)
- [ ] Figure-specific example queries in UI (expose the figure visibility gap)
- [ ] Entity-level query filtering in `/search` (expose `entities` metadata as a filter)

## Completed

- [x] Paragraph chunking (Phase 1)
- [x] Section reranking + recency boost (Phase 2)
- [x] Hybrid BM25 + vector search with RRF (Phase 3)
- [x] HyDE query expansion (Phase 4)
- [x] Figure cross-linking bidirectional (Phase 5)
- [x] Claim-extracting figure/table summaries (Phase 6)
- [x] HTML-scrape baseline collection + /baseline API
- [x] Demo comparison tool (5 scenarios, tools/demo_comparison.py)
- [x] Staged enrichment POC (stage_copyedit, review_app, stage_mastercopy)
- [x] FastAPI backend (search, ask, baseline, citation, institutions)
- [x] React UI (institution select → search)
- [x] Governance / license filtering
