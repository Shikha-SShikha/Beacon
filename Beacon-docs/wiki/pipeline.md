# Enrichment Pipeline

**File:** `pipeline.py`
**Input:** Elsevier DTD v5.7 XML (ce: prefix tags, floats block at top)
**Output:** `chunks/*_chunks.json` — one file per article, ~903 total chunks across 15 articles

---

## 7 Steps

```
[1/7] Parse XML
[2/7] Extract metadata and sections
[3/7] Generate contextual prefixes        ← GPT-4o-mini (AI cost)
[4/7] Summarise figures and tables        ← GPT-4o-mini (AI cost), claim-extracting prompt
[5/7] Entity tagging (NER + ontology)     ← GPT-4o-mini (AI cost)
[6/7] Cross-link figures and tables       ← pure regex, zero cost
[7/7] Combine and aggregate
```

---

## Phase History

### Phase 1 — Chunking Overhaul
**Addresses:** B1 (buried findings), B3, B4, truncation crisis

- **Paragraph-level chunking** — replaced section-level (7 chunks/article) with paragraph-level (~903 across 15 articles). Function: `extract_section_chunks()`.
- **Small paragraph merging** — paragraphs under 200 chars merged forward. Function: `_merge_small_paragraphs()`.
- **Cross-chunk overlap** — trailing sentences carried into next chunk to preserve context.

Before: ESR-102126 avg chunk = 31,065 chars → only 5% embedded. After: paragraphs fit within 1,500-char embed limit.

---

### Phase 2 — Section Reranking + Recency Boost
**Addresses:** B2, C3, G4, F1 — **query-time only, no pipeline rebuild needed**

Section boost multiplier applied after vector search:

| Intent | Boosted | Penalised |
|---|---|---|
| factual | results, discussion | introduction |
| methodological | methods | introduction |
| background | introduction | — |
| conclusion | conclusion, discussion | introduction |

Formula: `reranked_distance = raw_distance × section_multiplier` (boosted=0.85, penalised=1.10)

Also: linear recency decay, weight 0.10, always-on.

**File:** `api/services/reranker.py`

---

### Phase 3 — Hybrid BM25 + Dense Vector Search
**Addresses:** A1 (terminology mismatch), A2 (synonym gap), A3 (OOV fragmentation)

Dense embeddings fragment rare biomedical terms (ALK, PAI-1, METTL3) into meaningless subword tokens. BM25 matches them exactly. Reciprocal Rank Fusion (RRF) combines both:

```
rrf_score = 1/(k + rank_vector) + 1/(k + rank_bm25)
```

**Files:** `api/services/bm25_index.py`, `api/services/search_service.py`

---

### Phase 4 — HyDE Query Expansion
**Addresses:** A1, A2, C5a

User asks "parasite immune evasion" → article says "T. annulata subversion of bovine leukocyte signalling". HyDE generates a hypothetical paragraph using scientific vocabulary, embeds that instead of the raw query.

**File:** `api/services/hyde.py`
**Used in:** `/ask` endpoint and Scenario 5 of demo_comparison.py

---

### Phase 5 — Figure/Text Cross-Linking
**Addresses:** E2 (figure-claim decoupling)

Regex scan at enrichment time: finds all `Figure N` / `Table N` references in text chunks, creates bidirectional links:
- Text chunk: `figure_refs: ["fig1", "fig3"]`
- Figure chunk: `cited_in: ["chunk-id-1", "chunk-id-2"]`

At query time, linked figures fetched and attached to search results.

**Corpus results:** 199/704 text chunks have figure refs. 100% of figures cited in at least one text chunk.

**Files:** `pipeline.py` (`cross_link_figures()`), `api/services/search_service.py` (`fetch_linked_figures()`), `api/routers/search.py`

---

### Phase 6 — Claim-Extracting Figure/Table Summaries
**Addresses:** E1 (visual content blindness — deeper)

Changed `summarise_float()` prompt from descriptive ("Figure 4 demonstrates...") to claim-extracting ("METTL3 upregulation increases m6A levels..."). Dense embeddings weight early tokens heavily — front-loading the scientific claim instead of a figure reference improves retrieval match.

**File:** `pipeline.py` (`summarise_float()`)

---

## Chunk JSON Schema

```json
{
  "source_file": "BJ_100828.xml",
  "article_doi": "10.1016/j.bj.2025.100828",
  "total_chunks": 62,
  "processed_chunks": [
    {
      "id": "sec2-p3",
      "type": "text",            // or "figure" / "table"
      "section": "results",
      "text": "AI prefix...\n\nActual paragraph text...",
      "caption": "",             // figures/tables only
      "entities": [{"text": "METTL3", "type": "GENE", "id": "NCBI:56339"}],
      "figure_refs": ["fig3"],   // text chunks: outgoing refs
      "cited_in": [],            // figure chunks: incoming refs
      "metadata": {
        "title": "...",
        "authors": [...],
        "publication_date": "2025-01-01",
        "keywords": [...],
        "doi": "..."
      }
    }
  ]
}
```

---

## Corpus

15 articles processed (BJ, ESR, PLAS, REDOX journals). XML files in `articles/`. Chunk files in `chunks/`.

**Note on re-processing:** Existing chunk files were generated with all 7 phases. Re-running the pipeline costs API credits (GPT-4o-mini calls for prefixes, figure summaries, NER). The cross-linker (Step 6) is regex-only — can be run retroactively at zero cost.
