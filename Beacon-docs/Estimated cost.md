# Estimated API Cost

Pricing based on gpt-4o-mini ($0.15/1M input, $0.60/1M output) and text-embedding-3-small ($0.02/1M tokens).

---

## Indexing (one-time per article)

Assumes a typical biomedical article: ~46 text chunks, ~8 figures/tables.

| Call | Model | Calls | Avg tokens (in / out) | Est. cost |
|---|---|---|---|---|
| Contextual prefix generation | gpt-4o-mini | 46 | 430 / 40 | ~$0.004 |
| Figure & table claim extraction | gpt-4o-mini | 8 | 450 / 120 | ~$0.001 |
| NER extraction | gpt-4o-mini | 54 | 500 / 150 | ~$0.009 |
| Relation triple extraction | gpt-4o-mini | 46 | 380 / 150 | ~$0.007 |
| Embed chunks into ChromaDB | text-embedding-3-small | 1 batch (54 chunks ~440 tokens each) | ~24,000 | ~$0.0005 |
| **Total per article** | | **~154 LLM + 1 embed** | | **~$0.021** |

Embedding is negligible at $0.02/1M tokens — the entire article costs ~$0.0005 to embed.

**15-article corpus:** ~$0.32 total to index.

---

## Query time (per user query)

| Call | Model | When | Avg tokens (in / out) | Est. cost |
|---|---|---|---|---|
| Embed query | text-embedding-3-small | Every query | ~15 | ~$0.000 |
| /ask synthesis | gpt-4o-mini | Every /ask request | ~5,200 / 1,500 | ~$0.002 |
| /baseline/ask synthesis | gpt-4o-mini | Only if user clicks "How would current AI answer this?" | ~5,200 / 1,500 | ~$0.002 |
| **Total per query** | | | | **~$0.002–$0.004** |

The synthesis call dominates because the context block passes up to 10 sources (~500 tokens each) to the LLM in a single call.

---

## No LLM calls

| Component | Why no LLM |
|---|---|
| BM25 search | Inverted index, pure math |
| Reranker | Keyword intent detection + distance multipliers |
| Figure cross-linking (query time) | ChromaDB `.get()` lookup only |
| HyDE | Field exists in `SearchRequest` model but not implemented |
