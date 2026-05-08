# Phase 6 — Claim-Extracting Figure/Table Summaries

**Addresses:** E1 (visual content blindness — deeper)

**Status:** Complete

---

## Problem

The old figure summary prompt generates descriptive text:
> "Figure 4 demonstrates that the upregulation of METTL3 in Theileria-infected leukocytes leads to increased m6A levels, which correlate with a reduced growth rate..."

This starts with "Figure 4 demonstrates" — wasting embedding space on a reference instead of the finding. A researcher searching for "METTL3 m6A cell cycle" won't match as strongly because the first tokens are about the figure itself, not the science.

---

## Solution: Claim-Extracting Prompt

Changed the `summarise_float()` prompt in `pipeline.py` to extract the scientific finding as a factual claim:

> "METTL3 upregulation in Theileria-infected leukocytes increases m6A levels and accelerates the cell cycle, as evidenced by a higher fraction of cells in the G2 phase. The growth rate of virulent infected macrophages and TBL20 B cells declines post-METTL3 upregulation..."

### Key differences

| Aspect | Old prompt | New prompt |
|---|---|---|
| Opening | "Figure 4 demonstrates that..." | "METTL3 upregulation increases..." |
| Style | Descriptive (what the figure shows) | Factual claim (what the finding is) |
| Searchability | Figure reference wastes embedding tokens | Finding terms are front-loaded |
| Values | "reduced growth rate" | "growth rate declines", "boosts mRNA count of e2f4" |

---

## Prompt Design

### System prompt

```
You extract scientific findings from figures and tables in research articles.
State findings as factual claims with specific values, not descriptions of what
the figure contains. Your output will be used for search retrieval — a researcher
searching for 'X inhibits Y' should match your summary.
```

### User prompt

```
Extract the scientific finding or claim this {type} supports. Write 2-3 sentences:
1. State the key finding as a factual claim (e.g. "X inhibits Y", "Treatment A increases B by N%").
2. Include specific values, comparisons, or trends visible in the data.
3. End with what the {type} demonstrates in the context of the article's argument.

Use active, definitive language. Avoid "this figure shows" or "this table presents" —
state the finding directly. Return only the sentences.
```

### Why this works for retrieval

Dense embeddings weight early tokens more heavily. By front-loading the scientific claim ("METTL3 upregulation increases m6A levels") instead of a figure reference ("Figure 4 demonstrates"), the embedding vector is much closer to a researcher's query about the actual finding.

---

## Files Changed

| File | Change |
|---|---|
| `pipeline.py` | Rewrote `summarise_float()` prompt — system message and user prompt both changed. Docstring updated. |

No other files changed. No model or API contract changes — the summary text flows through the same `format_float()` output path.

---

## Important: Requires Re-Processing

Existing figure/table summaries in `chunks/` were generated with the old descriptive prompt. To get claim-extracting summaries, the pipeline must be re-run on the articles. This will:
- Re-call gpt-4o-mini for each figure/table (~154 across corpus)
- Cost: ~154 API calls × ~200 output tokens ≈ minimal cost
- Text chunks and NER results are unchanged — only figure/table summaries update

Alternatively, a targeted re-summarisation script could update only the figure/table chunks in each JSON file without re-running the full pipeline.
