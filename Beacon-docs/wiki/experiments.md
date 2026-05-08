# Experiments

---

## Current Experiment: html_scrape vs entity_enriched

**File:** `experiment.py`
**Corpus:** 15 articles, ~903 total chunks
**Comparison:** 2 collections (html_scrape = baseline, entity_enriched = Beacon full pipeline)

### How to run
```bash
python experiment.py              # builds collections, runs all queries, saves experiment_results.json
python experiment.py --top-k 5   # show top-5 per query
```

### Query set (12 queries)
Covers: energy domain, biomedical entity-specific, project management, cross-domain, figure/table-specific.

Figure/table queries are the most revealing — html_scrape returns `[IMAGE]` or caption-only, entity_enriched returns AI claim-extracting summaries.

---

## Demo Comparison Tool

**File:** `tools/demo_comparison.py`
**5 curated scenarios** each demonstrating a specific failure mode:

| # | Title | Failure Mode | Enhancement |
|---|---|---|---|
| 1 | Buried Finding → Surfaced | B1, B4 | Paragraph chunking |
| 2 | Figure Was Invisible → Now Retrievable | E1, E2 | Claim-extracting summaries + cross-linking |
| 3 | Wrong Section Ranked First | C3, B2 | Section reranking |
| 4 | Exact Biomedical Term Boosted | A1, A3 | Hybrid BM25 |
| 5 | Terminology Gap Bridged | A2, C5a | HyDE |

```bash
python tools/demo_comparison.py           # full report → demo_comparison_report.txt
python tools/demo_comparison.py --query 2 # single scenario
python tools/demo_comparison.py --json    # JSON output
```

---

## Original POC Experiment (Archival)

**2 articles, 3 collections: raw / metadata / enriched**

Key finding: enriched wins on conceptual queries (bounded confidence, community brokers), metadata wins on topic queries (article title in query), raw wins on generic/keyword queries.

Honest caveat: at 2 articles the gap is small. Enrichment's disambiguation value compounds at scale (500+ articles, multiple identical "Introduction" sections).

**Why raw won most queries:**
1. AI prefix is ~40 words vs 2,000+ char sections — only 5% of embedding signal
2. 40 total chunks is too small to need disambiguation
3. Figure chunks were identical in raw and enriched (no prefix separator for floats)

**The right baseline** is HTML scrape vs enriched XML — not clean XML vs enriched XML. That's what the current experiment measures.

See: `Beacon-docs/POC results.md` for full original results.

---

## What the Results Show

**Figure queries expose the largest gap.** html_scrape returns `[IMAGE]` — vector search can't match anything. entity_enriched returns the claim-extracting summary — exact finding retrievable.

**Entity-specific biomedical queries** (YY1, ANXA3, PAI-1) benefit from BM25 hybrid. Dense embeddings fragment rare terms; BM25 anchors them exactly.

**Rank-1 distance is a weak metric.** A difference of 0.97 vs 0.98 looks like noise. The better metric is: did the right article surface in top-K? Did a previously invisible figure become retrievable? These are shown in the demo comparison tool.
