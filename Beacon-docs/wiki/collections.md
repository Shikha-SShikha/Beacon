# ChromaDB Collections

**Path:** `chroma_db/` (persistent on disk, ~chroma.sqlite3)
**Embedding model:** `text-embedding-3-small` (OpenAI)
**Built by:** `experiment.py`

---

## Active Collections

### `html_scrape`
Simulates what a standard RAG pipeline gets from publisher HTML — the baseline.

| Chunk type | What's stored |
|---|---|
| Text | Plain section text only (AI prefix stripped) |
| Figure | `[IMAGE]` |
| Table | `[TABLE]: caption` (truncated to 300 chars) or `[TABLE]: visual content only, structure not available` |

This is the "before" in every comparison. It represents the best a competitor building on scraped content can do.

---

### `entity_enriched`
Full Beacon enrichment — used by `/search` and `/ask`.

| Chunk type | What's stored |
|---|---|
| Text | Entity tag string + AI contextual prefix + section text |
| Figure | Entity tags + claim-extracting AI summary |
| Table | Entity tags + caption + structured content + AI summary |

Entity tag format (prepended): `[GENE: METTL3] [DISEASE: leukemia] [CHEMICAL: m6A] ...`

---

## How Collections Are Built

`experiment.py` `build_collections()`:
1. Deletes any existing `html_scrape` and `entity_enriched` collections
2. Reads all `chunks/*_chunks.json` files
3. For each chunk, generates `html_scrape` text (strip prefix, replace figures) and `entity_enriched` text (tag string + full text)
4. Embeds in batches of 20, stores with metadata

Text truncated to 1,500 chars at store time (embed limit).

**Metadata stored per chunk:**
```
source, doi, type, section, title, publication_date, entities (JSON), figure_refs (JSON), cited_in (JSON)
```

---

## Collections That No Longer Exist

The old experiment (POC phase, 2 articles) had three collections: `raw`, `metadata`, `enriched`. These were the original comparison set. They are no longer rebuilt by `experiment.py` and should not be referenced in new code.

`experiment.py` currently deletes `enriched` during its cleanup loop but doesn't rebuild it — this is expected. The `raw` collection may still exist in `chroma_db/` from a previous run; it is not used anywhere.

---

## API Access

| Endpoint | Collection used |
|---|---|
| `POST /search` | `entity_enriched` |
| `POST /ask` | `entity_enriched` |
| `POST /baseline` | `html_scrape` |
| `POST /baseline/ask` | `html_scrape` |

The `/baseline` routes are the apples-to-apples comparison: same LLM, same prompt, same license filtering — only the retrieval collection differs.
