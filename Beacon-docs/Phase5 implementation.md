# Phase 5 — Figure-Claim Cross-Linking

**Addresses:** E2 (figure–claim decoupling)

**Status:** Complete

---

## Problem

Figure chunks have `section=None`. The corresponding claim in the Discussion or Results is a separate, unlinked chunk. When a text chunk is retrieved that says "As shown in Figure 3, METTL3 expression increases...", the actual Figure 3 summary is invisible to the query. The scientific meaning of the figure and the prose that interprets it are structurally disconnected.

---

## Solution: Bidirectional Cross-Links

At enrichment time, scan text chunks for figure/table references and create bidirectional links:
- **Text → Figure**: `figure_refs: ["fig1", "fig3"]` on text chunks
- **Figure → Text**: `cited_in: ["article-...-sec3-p2", "article-...-sec4-p1"]` on figure/table chunks

At query time, when a text chunk is retrieved, its linked figure/table chunks are fetched and attached to the search result.

---

## Enrichment-Time: Cross-Linking (pipeline.py)

### Function: `cross_link_figures()` at pipeline.py

**Regex pattern:**
```python
r'(?:Fig(?:ure|\.)?\.?\s*(\d+[A-Za-z]?))'
r'|(?:Table\.?\s*(\d+[A-Za-z]?))'
```

Handles variations found in the corpus:
- `Figure 3`, `Fig. 3`, `Fig 3`, `figure. 3` (XML extraction artifact), `Figure 3A`
- `Table 2`, `Table. 2`

**Mapping:** Extracts the number from the reference and maps to float chunk IDs:
- "Figure 3" → `fig3`
- "Table 2" → `tbl2`

**Integration:** Runs as Step 6/7 in the pipeline, after NER (Step 5) and before final output (Step 7). No AI calls — pure regex, zero cost.

### Corpus-Wide Results

| Metric | Count |
|---|---|
| Text chunks with figure refs | 199 / 704 text chunks (28%) |
| Figures/tables cited in text | 154 / 154 (100%) |

Every single figure and table in the corpus is referenced by at least one text chunk.

### Per-Article Breakdown

| Article | Text with refs | Floats cited |
|---|---|---|
| BJ_100828 | 11 | 6/6 |
| BJ_100833 | 6 | 5/5 |
| BJ_100840 | 6 | 6/6 |
| BJ_100850 | 3 | 2/2 |
| BJ_100854 | 2 | 1/1 |
| BJ_100876 | 16 | 7/7 |
| BJ_100877 | 5 | 8/8 |
| BJ_100885 | 6 | 5/5 |
| BJ_100950 | 1 | 1/1 |
| ESR-102001 | 24 | 19/19 |
| ESR-102126 | 78 | 62/62 |
| PLAS-100213 | 8 | 6/6 |
| PLAS-100214 | 19 | 15/15 |
| REDOX-104085 | 14 | 11/11 |

---

## Query-Time: Figure Expansion (search_service.py)

### Function: `fetch_linked_figures()`

When search results are returned:
1. For each hit, read `figure_refs` from ChromaDB metadata
2. Batch fetch all referenced figure/table chunks in one ChromaDB `.get()` call
3. Return a map: `hit_id → [linked_figure_dicts]`

### Response format

Each `SearchResult` now has a `linked_figures` list:

```json
{
  "rank": 1,
  "distance": 0.45,
  "text": "As shown in Figure 3, METTL3 expression increases 3-fold...",
  "linked_figures": [
    {
      "id": "10-1016-j-bj-2025-100828::fig3",
      "chunk_type": "figure",
      "text": "Figure 3: Figure 3 illustrates the relationship between m6A methylation..."
    }
  ]
}
```

Figure text is truncated to 500 chars in the response to keep payload size manageable.

---

## Files Changed

| File | Change |
|---|---|
| `pipeline.py` | Added `cross_link_figures()`, `_FIGURE_REF_RE`. Inserted as Step 6/7. Updated step numbering (now 7 steps). |
| `api/services/search_service.py` | Added `fetch_linked_figures()` — batch fetch from ChromaDB. |
| `api/routers/search.py` | Calls `fetch_linked_figures()`, attaches `LinkedFigure` objects to results. |
| `api/models.py` | Added `LinkedFigure` model, `linked_figures` field on `SearchResult`. |
| `experiment.py` | Added `figure_refs` and `cited_in` to `chroma_meta`. |

---

## Pipeline Step Numbering (Updated)

```
[1/7] Parse XML
[2/7] Extract metadata and sections
[3/7] Generate contextual prefixes
[4/7] Summarise figures and tables
[5/7] Entity tagging (NER + ontology)
[6/7] Cross-link figures and tables    ← NEW (Phase 5)
[7/7] Combine and aggregate
```

---

## Important: Requires Re-Processing

The cross-links are computed at enrichment time and stored in chunk JSON. Existing chunk files in `chunks/` do **not** have `figure_refs` or `cited_in` fields yet. To populate them, either:

1. **Re-run the pipeline** on all articles (will re-run AI calls — costs API credits)
2. **Run cross-linking retroactively** — load existing chunks, call `cross_link_figures()`, save back (no AI calls needed)

Option 2 is recommended for existing chunks. The cross-linker is pure regex — no API calls.

Similarly, ChromaDB collections need a rebuild (via `experiment.py`) to include the new metadata fields.
