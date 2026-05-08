# Phase 2 — Activate Section Metadata as Filter + Reranking

**Addresses:** B2 (abstract over-weighting), C3 (discourse blindness), G4 (structural metadata loss), F1 (temporal drift)

**Principle:** All metadata already exists in ChromaDB — this phase activates it at query time. No pipeline rebuild needed.

---

## 1. Section-Type Reranking (Query-Dependent)

### How it works

After vector search returns top candidates, we apply a **section boost multiplier** to each result's distance score. The multiplier depends on the **query intent**, detected via lightweight keyword matching.

### Intent → Section Boost Map

| Query Intent | Boosted Sections | Penalised Sections | Detection Keywords |
|---|---|---|---|
| **factual** (findings, results) | `results`, `discussion` | `introduction`, `other` | "finding", "result", "show", "demonstrate", "effect", "impact", "outcome" |
| **methodological** | `methods` | `introduction`, `other` | "method", "methodology", "how was", "technique", "protocol", "procedure", "measure" |
| **background** | `introduction` | — | "background", "context", "overview", "what is known", "prior work" |
| **conclusion** | `conclusion`, `discussion` | `introduction` | "conclusion", "summary", "main finding", "implication" |
| **general** (default) | no boost | no boost | (fallback when no keywords match) |

### Scoring formula

```
reranked_distance = raw_distance * section_multiplier
```

- **Boosted section**: multiplier = `0.85` (15% distance reduction → ranked higher)
- **Neutral section**: multiplier = `1.0`
- **Penalised section**: multiplier = `1.10` (10% distance increase → ranked lower)

Asymmetric on purpose — we want to surface relevant sections more than we want to bury irrelevant ones. A results chunk that genuinely matches a methodology query should still appear; it just shouldn't outrank a methods chunk at equal distance.

---

## 2. Recency Boost (Linear Decay, Always-On)

### How it works

Newer papers get a small distance reduction. The boost decays linearly over a configurable window.

### Formula

```
age_years = (today - publication_date).days / 365.25
decay = min(age_years / max_age_years, 1.0)   # clamp at 1.0 for very old papers
recency_multiplier = 1.0 + (recency_weight * decay)
```

- `recency_weight = 0.10` (max 10% penalty for oldest papers)
- `max_age_years = 5` (papers older than 5 years get the full penalty)
- A paper from today: multiplier = `1.0` (no change)
- A paper from 2.5 years ago: multiplier = `1.05` (5% distance increase)
- A paper from 5+ years ago: multiplier = `1.10` (10% distance increase)

### Why linear

Exponential decay over-penalises foundational papers. In scientific literature, a 3-year-old paper is not dramatically less relevant than a 1-year-old paper. Linear keeps the penalty mild and predictable.

---

## 3. Combined Reranking

```
final_distance = raw_distance * section_multiplier * recency_multiplier
```

Then re-sort results by `final_distance`.

**Example:** A 2-year-old results chunk matching a factual query:
- raw_distance = `0.50`
- section_multiplier = `0.85` (results boosted)
- recency_multiplier = `1.04` (2yr linear decay at 10% over 5yr)
- final_distance = `0.50 * 0.85 * 1.04 = 0.442`

---

## 4. Files Changed

| File | Change |
|---|---|
| `api/services/search_service.py` | Add `rerank()` function with intent detection, section boost, recency boost. Thread `publication_date` from ChromaDB metadata. |
| `api/services/reranker.py` | **New file.** Contains `detect_intent()`, `section_multiplier()`, `recency_multiplier()`, `rerank()`. Separated from search_service for testability. |
| `api/routers/search.py` | Call reranker after `raw_search()`. Add optional `recency_weight` param to `SearchRequest`. |
| `api/models.py` | Add `recency_weight: float = 0.10` and `section_boost: bool = True` to `SearchRequest`. Add `rerank_debug` field to `SearchResult` for transparency. |
| `experiment.py` | Add `publication_date` to `chroma_meta` dict (line 136). Currently missing — needed for recency boost to work on experiment collections. |

### Not changed
- `pipeline.py` — no enrichment changes
- Chunk JSON files — no re-processing
- ChromaDB collections — only need rebuild if `publication_date` missing from metadata (experiment.py only)

---

## 5. API Contract Changes

### SearchRequest (new optional fields)

```json
{
  "query": "TM5614 clinical trial results",
  "institution_id": "elsevier_internal",
  "top_k": 6,
  "section_boost": true,
  "recency_weight": 0.10
}
```

- `section_boost` (default `true`): enable query-dependent section reranking
- `recency_weight` (default `0.10`): 0.0 disables recency boost, max 0.5

### SearchResult (new debug field)

```json
{
  "rank": 1,
  "distance": 0.442,
  "raw_distance": 0.50,
  "rerank_debug": {
    "intent": "factual",
    "section_multiplier": 0.85,
    "recency_multiplier": 1.04
  }
}
```

`rerank_debug` is included by default for now (demo/debugging). Can be toggled off later.

---

## 6. Intent Detection Logic

Simple keyword matching against the query string. No LLM call — this needs to be zero-latency.

```python
INTENT_KEYWORDS = {
    "factual": ["finding", "result", "show", "demonstrate", "effect",
                "impact", "outcome", "cause", "inhibit", "express"],
    "methodological": ["method", "methodology", "how was", "technique",
                       "protocol", "procedure", "measure", "collect", "analyse"],
    "background": ["background", "context", "overview", "known", "prior",
                   "previous", "literature"],
    "conclusion": ["conclusion", "summary", "main finding", "implication",
                   "recommend"],
}
```

Match priority: most keyword hits wins. Ties → `"general"` (no boost).

---

## 7. Experiment Validation Plan

After implementation, re-run `experiment.py` with reranking applied to the enriched collection. Compare:
- Rank-1 distances before/after reranking
- Check that methodology queries surface methods chunks
- Check that factual queries surface results/discussion chunks
- Verify recency doesn't kill foundational papers that are the best match
