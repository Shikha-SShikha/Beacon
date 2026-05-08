# Phase 4 — HyDE Query Expansion

**Addresses:** A1 (terminology mismatch), A2 (synonym gap), C5a (implicit knowledge gap — partial)

**Status:** Complete

---

## Problem

Users ask questions in natural language, but scientific articles use technical vocabulary:
- "parasite immune evasion" → article says "T. annulata subversion of bovine leukocyte signalling"
- "what inhibits gene X" → article says "TM5614 attenuates PAI-1 mediated fibrinolytic suppression"

Dense embeddings encode the *meaning* of both, but the vocabulary gap means the embedding vectors aren't as close as they should be. The query vector and the document vector live in slightly different neighborhoods of the embedding space.

---

## Solution: HyDE (Hypothetical Document Embeddings)

**Paper:** Gao et al. 2022 — "Precise Zero-Shot Dense Retrieval without Relevance Labels"

Instead of embedding the raw query, ask an LLM to generate a hypothetical paragraph that *could* appear in a relevant article. Then embed that paragraph. The hypothetical text uses corpus-like vocabulary, bridging the terminology gap.

```
Query: "parasite immune evasion"
    ↓ LLM generates
HyDE: "Parasites have evolved sophisticated strategies to evade host immune
       responses... antigenic variation... surface antigens... host environment..."
    ↓ embed this instead
Vector is now closer to actual corpus chunks about T. annulata infection
```

---

## Implementation

### Module: `api/services/hyde.py`

Two functions:

**`generate_hypothetical_document(query)`**
- Calls gpt-4o-mini with a system prompt tuned for scientific article style
- Generates 100-150 words, temperature=0.7
- Prompt explicitly says: "write text that would appear in a relevant article" (not "answer the question")

**`expand_query_hyde(query)`**
- Returns: `{hypothetical_paragraph}\n\n{original_query}`
- Appends original query to preserve exact terms (critical for BM25 in hybrid mode, and for biomedical abbreviations)

### System prompt

```
You are a scientific article retrieval assistant. Given a user's search query,
write a single paragraph (100-150 words) that could plausibly appear in a
scientific article answering that query. Use technical vocabulary, specific
terminology, and the style of a peer-reviewed journal article.
Do NOT answer the question — write text that would appear in a relevant article.
Do NOT include citations, figure references, or hedging language.
```

### Integration in search pipeline

```
1. If hyde=true:
     a. LLM generates hypothetical paragraph (~1s)
     b. Embed (hypothetical + original query)
   Else:
     a. Embed raw query
2. BM25 always uses original query (exact terms, no HyDE)
3. RRF fusion (if hybrid=true)
4. Phase 2 reranking
5. License filtering
```

Key design decision: **BM25 always uses the raw query.** HyDE only affects the dense embedding path. This is deliberate — BM25's strength is exact term matching, and HyDE's expanded vocabulary would dilute that signal.

---

## Files Changed

| File | Change |
|---|---|
| `api/services/hyde.py` | **New.** `generate_hypothetical_document()`, `expand_query_hyde()`. |
| `api/routers/search.py` | Calls `expand_query_hyde()` before embedding when `req.hyde=True`. |
| `api/models.py` | Added `hyde: bool = False` to `SearchRequest`. |

---

## API Contract Changes

### SearchRequest (new field)

```json
{
  "query": "parasite immune evasion",
  "institution_id": "elsevier_internal",
  "top_k": 6,
  "hybrid": true,
  "hyde": true
}
```

- `hyde` (default `false`): disabled by default because it adds ~1s latency from the LLM call. Enable for terminology-gap-heavy queries.

---

## Latency Impact

| Component | Latency |
|---|---|
| HyDE generation (gpt-4o-mini) | ~0.8-1.2s |
| Embedding | ~0.1s |
| BM25 search | <1ms |
| ChromaDB vector search | ~10ms |

HyDE roughly doubles total search latency. Default off — enable when retrieval quality matters more than speed.

---

## Validation

| Query | HyDE-expanded vocabulary (sample) |
|---|---|
| "parasite immune evasion" | antigenic variation, surface antigens, host environment, immune modulation |
| "ALK translocation detection methods" | fluorescence in situ hybridization, FISH, NSCLC, gene rearrangement, immunohistochemistry |

The expanded vocabulary directly matches terminology used in the corpus articles, bridging the gap that raw queries cannot.

---

## When to Use HyDE

**Good candidates:**
- Broad conceptual queries ("parasite immune evasion", "drug resistance mechanisms")
- Queries using non-specialist language ("how does the cancer gene test work")
- Cross-domain queries where the user's field uses different terms than the article's field

**Poor candidates:**
- Exact entity queries ("METTL3 m6A") — BM25 already handles these; HyDE adds latency with no gain
- Figure/table queries — HyDE won't help find visual content
- Queries already using article terminology — no vocabulary gap to bridge
