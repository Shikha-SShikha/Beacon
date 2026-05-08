# Project Beacon — Wiki

> **This is the authoritative current state.** Other docs in `Beacon-docs/` are archival — useful for deep context but may be stale. Start here every session.

---

## What This Is

Beacon is a semantic enrichment pipeline that transforms raw publisher XML into AI-retrievable content. The core insight: AI tools get noisy HTML from web scraping (figures invisible, no section identity). Publishers have clean XML. Beacon bridges that gap via a licensed enrichment pipeline.

**Baseline vs Beacon — the comparison that tells the story:**

| Capability | HTML scrape (what AI gets today) | Beacon entity_enriched |
|---|---|---|
| Section identity | ❌ | ✅ |
| Metadata per chunk | ❌ | ✅ |
| Figures searchable | ❌ `[IMAGE]` | ✅ AI claim-extracting summary |
| Tables searchable | ❌ caption only | ✅ content + summary |
| Exact biomedical terms | partial | ✅ BM25 hybrid |
| Conceptual queries | poor | ✅ HyDE + AI prefix |
| Entity / ontology links | ❌ | ✅ NER + ID resolution |

---

## Component Map

```
pipeline.py          — 7-step enrichment: XML → enriched JSON chunks
experiment.py        — builds ChromaDB collections; runs baseline vs Beacon comparison
tools/demo_comparison.py — 5 curated scenarios comparing html_scrape vs entity_enriched
stage_copyedit.py    — HITL Stage 1: NER draft on copyedited XML → enrichment_copyedit.json
stage_mastercopy.py  — HITL Stage 2: ontology resolution on proofed XML → enrichment_mastercopy.json
review_app.py        — Streamlit UI for human review of draft entities (between stages)
api/                 — FastAPI backend (search, ask, baseline, citation, institutions)
beacon-ui/           — React frontend (institution select → search)
governance/          — License config + access control
chroma_db/           — Persistent vector store (2 active collections)
chunks/              — Enriched JSON chunks per article (15 articles, ~903 total chunks)
.tmp/                — Staged enrichment manifests (regeneratable)
```

---

## Wiki Pages

- [pipeline.md](pipeline.md) — 7-step enrichment pipeline, all phases
- [collections.md](collections.md) — ChromaDB collections: what exists, what each contains
- [api.md](api.md) — API routes and what each does
- [experiments.md](experiments.md) — what was tested and what it proved
- [staged-enrichment.md](staged-enrichment.md) — HITL staged enrichment workflow
- [open-items.md](open-items.md) — genuinely open work (read this to know what's next)
- [sources.md](sources.md) — catalog of all other Beacon-docs files with one-line summaries
- [log.md](log.md) — append-only session log

---

## Quick Status

| Component | Status |
|---|---|
| Pipeline (all 7 steps) | ✅ Complete |
| ChromaDB (html_scrape + entity_enriched) | ✅ Built, persistent |
| FastAPI (search, ask, baseline, citation) | ✅ Running |
| React UI | ✅ Functional |
| Staged enrichment POC | ✅ Complete (both stages + review app) |
| HTML-scrape baseline collection | ✅ Implemented in experiment.py + /baseline API |
| Demo comparison tool (5 scenarios) | ✅ tools/demo_comparison.py |
| Open: Top-K recall UI view | ⬜ Not started |
| Open: Figure-specific example queries in UI | ⬜ Not started |
| Open: Entity-level query demos | ⬜ Not started (needs NER wired into search) |
