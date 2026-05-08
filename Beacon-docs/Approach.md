# Beacon — Approach Document

**Licensed AI Content Gateway for Scientific Publishers**

---

## 1. The Problem

Scientific publishers own vast, high-quality content — peer-reviewed journals, articles, structured datasets. That content is increasingly being consumed by AI tools (RAG systems, research assistants, enterprise LLMs) but with no mechanism for:

- **License enforcement** — AI tools can retrieve content without checking whether the user or institution has rights to it
- **Access differentiation** — there is no meaningful difference between what a subscribed institution sees vs. a guest
- **Revenue capture** — publishers can't monetise AI-driven discovery even as AI replaces traditional search

Beacon solves this by sitting between the publisher content layer and AI consumption, enforcing institutional licensing at the point of retrieval.

---

## 2. The Concept

Beacon is a **Licensed AI Content Gateway**. It exposes publisher content for semantic (vector) search, but every retrieval decision is gated by a licence check.

The key insight is that **access control doesn't happen at login — it happens at the chunk level, at query time.** When a result is retrieved from the vector database, Beacon checks whether the requesting institution holds a licence for that chunk's journal, and returns accordingly:

| Decision | Rights | What the user sees |
|----------|--------|--------------------|
| `ALLOWED` | `RAG_READ_RAG_SOURCE` | Full text + entities + DOI link |
| `SNIPPET_ONLY` | `RAG` | Truncated preview (~320 chars) |
| `OPEN_ACCESS` | `OPEN_ACCESS` | Full text + entities + DOI link |
| `NO_ACCESS` | `NONE` | Hidden from results; counted in upgrade hint |

This mirrors real-world publisher licence agreements where institutions negotiate different access tiers per journal.

---

## 3. System Architecture

```
Elsevier XML Articles
        ↓
[Enrichment Pipeline]  ←─ pipeline.py + ner.py
        ↓
  ChromaDB (local)       ←─ entity_enriched collection
        ↓
[FastAPI / api/]
  ├── /search            ←─ embed query → raw_search → license gate → response
  ├── /institutions      ←─ list institutions + licensed journals
  └── /citation          ←─ citation context per card + foundational per query
        ↓
[Governance Layer]       ←─ governance/license_service.py
  └── license_config.json  ←─ hardcoded institution–journal–rights mappings
        ↓
[React UI / beacon-ui/]
  ├── SelectionPage      ←─ institution login (Beacon mode + Publisher mode)
  └── SearchPage         ←─ search bar + result cards + citation panels
```

---

## 4. Enrichment Pipeline

**Input:** Elsevier JATS XML articles (15 articles across 4 journals)

**Output:** Enriched JSON chunks stored in ChromaDB

### Pipeline steps (`pipeline.py`):

1. **Parse XML** — lxml, strips DOCTYPE, extracts article metadata (title, authors, DOI, year)
2. **Section chunking** — one chunk per article section (intro, methods, results, discussion). Section-level chunking preserves semantic coherence better than fixed-size splits.
3. **AI contextual prefix** — GPT-4o-mini prepends each chunk with a one-sentence context sentence: *"This methods section from a 2022 Biochemical Journal study on Theileria m6A methylation describes the CRISPR protocol used to knock out METTL3..."*. This dramatically improves retrieval quality because the embedding captures article-level context, not just the section's raw words.
4. **Figure/table summaries** — GPT-4o-mini generates 2–3 sentence summaries of each figure and table caption. These become separate searchable chunks.
5. **NER + ontology IDs** — `ner.py` runs two-step entity recognition:
   - GPT-4o-mini extracts entity names and types (GENE, DISEASE, CHEMICAL, CELL_LINE, SPECIES, METHOD)
   - Resolvers call NCBI Gene, NLM MeSH, OLS, and Cellosaurus APIs to link entities to canonical ontology IDs
   - Achieves ~85% ID coverage on biomedical articles
6. **Output JSON** — saved to `chunks/` (one file per article)

### Three ChromaDB collections (`experiment.py`):

| Collection | What's stored | Purpose |
|------------|---------------|---------|
| `html_scrape` | Plain text, figures as `[IMAGE]` | Baseline |
| `enriched` | AI prefix + section text | Better retrieval |
| `entity_enriched` | Entity tags + AI prefix + section text | Best retrieval — used in Beacon demo |

### Entity tag format in chunks:
```
[GENE: METTL3 | NCBI Gene:56339]
[DISEASE: tropical theileriosis | Disease Ontology:DOID:10607]
[CHEMICAL: m6A | ChEBI:CHEBI:21891]
[CELL_LINE: TBL20 | Cellosaurus:CVCL_2G83]
[METHOD: CRISPR-Cas9]
```

---

## 5. Governance Model

### Licence configuration (`governance/license_config.json`)

Institutions are configured with collections (journal codes) and rights levels:

```json
{
  "institutions": {
    "uni_edinburgh": {
      "name": "University of Edinburgh",
      "collections": { "BJ": "RAG_READ_RAG_SOURCE", "REDOX": "RAG_READ_RAG_SOURCE" }
    },
    "tu_berlin": {
      "name": "TU Berlin",
      "collections": { "ESR": "RAG" }
    },
    "global_policy": {
      "name": "Global Policy Institute",
      "collections": { "PLAS": "RAG_READ_RAG_SOURCE", "ESR": "RAG" }
    },
    "guest": {
      "name": "Guest",
      "collections": { "OA": "OPEN_ACCESS" }
    }
  },
  "open_access_sources": ["BJ_100885.xml", "BJ_100950.xml"]
}
```

### Licence check logic (`governance/license_service.py`)

Every result from ChromaDB is passed through `check_license(institution_id, chunk_metadata)` before being returned. The decision hierarchy:

1. If the source file is in `open_access_sources` → `OPEN_ACCESS` (regardless of institution)
2. If institution holds `RAG_READ_RAG_SOURCE` for that journal → `ALLOWED`
3. If institution holds `RAG` for that journal → `SNIPPET_ONLY`
4. Otherwise → `NO_ACCESS` (excluded from results, counted for upgrade hint)

### Search filtering (`api/routers/search.py`)

The API fetches `min(top_k × 3, 20)` raw results from ChromaDB (oversampling to compensate for filtered-out `NO_ACCESS` results), then:

- Applies the licence gate to each hit
- Collects journal names of `NO_ACCESS` hits for the upgrade hint
- Returns up to `top_k` permitted results
- Returns `upgrade_hint: { locked_count, journal_names }` when locked content was found

### What is hardcoded

The entire governance layer is a simulated lookup. In production, this would be driven by a real entitlement database queried against authenticated user/institution credentials. The POC demonstrates the *architecture and UX* of per-chunk access control, not a live licence API integration. The "Bring Your Own Licence" concept (institutions connecting their own subscription data) was intentionally deferred to keep the POC scope clear.

---

## 6. API Layer

**Stack:** FastAPI, Python 3.11, running on port 8001

### Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/institutions` | List all institutions with licensed journals |
| `GET` | `/institutions/{id}` | Single institution summary |
| `GET` | `/journals` | Journal metadata (name, publisher, colour) |
| `POST` | `/search` | Main search endpoint — embed, retrieve, gate, return |
| `GET` | `/citation/context?source=BJ_100828.xml` | Per-card citation context |
| `POST` | `/citation/foundational` | Foundational papers across a result set |

### Search request/response:

```python
# Request
{ "query": "m6A methylation METTL3", "institution_id": "uni_edinburgh", "top_k": 6 }

# Response
{
  "query": "...",
  "institution_id": "...",
  "results": [
    {
      "rank": 1,
      "distance": 0.312,
      "license": { "decision": "ALLOWED", "rights": "RAG_READ_RAG_SOURCE", ... },
      "metadata": { "title": "...", "section": "...", "source": "BJ_100828.xml", "doi": "...", "entities": "[...]", "chunk_type": "text" },
      "text": "..."
    }
  ],
  "stats": { "full_text": 4, "snippet_only": 0, "open_access": 2, "total": 6 },
  "upgrade_hint": { "locked_count": 11, "journal_names": ["Redox Biology"] }
}
```

---

## 7. Citation Graph

**Source:** `citation_graph.json` — built by `citation_graph.py`

**Structure:**
- `nodes`: dict of DOI → node data (type: `corpus` or `external`, title, authors, year, journal, source filename)
- `edges`: list of `{ from: doi, to: doi }` citation relationships
- `index`: inverted index — DOI → list of corpus articles that cite it

**Three surfaces exposed in the UI:**

| Surface | What it shows | Where it appears |
|---------|---------------|-----------------|
| Related in collection | Corpus articles sharing the most references with this card's article | Per result card |
| By same author | Other corpus articles with overlapping author surnames | Per result card |
| Key references | External papers cited by this article that are also widely cited across the corpus | Per result card |
| Foundational panel | External papers most cited across the *entire result set* for a query | Below all result cards |

**Practical note:** Because the corpus spans unrelated disciplines (biomedical journals BJ/REDOX vs. engineering ESR vs. social science PLAS), cross-article author overlap and shared references are rare within the POC. The foundational panel (query-level) is the most useful surface for this corpus.

---

## 8. UI Layer

**Stack:** React + TypeScript, Vite, Tailwind CSS. Running on port 5173.

### SelectionPage (Login)

Two auth modes selectable via tab:

**Beacon mode (default):**
- Institution dropdown → selects `institution_id`
- Shows preview of what journals will be accessible after sign-in

**Publisher subscription mode:**
- Publisher dropdown (Elsevier, Portland Press, Pleiades, Wiley)
- Institution name input with autocomplete datalist
- Subscriber ID field
- Maps to institution ID via `resolveInstitution()` helper (or falls back to "guest")

### SearchPage

- **Sidebar:** Institution avatar, name, description; list of licensed journals with access badges (green pill = Full Access, amber pill = Snippet Only); "Switch institution" link
- **Search bar:** Prominent full-width input with example queries; Enter or button submits
- **Results:** Stacked exchange history (newest first). Each exchange shows:
  - Query label
  - Stats bar: total, full text count (green dot), snippet count (amber dot), open access count (blue dot)
  - Result cards (see below)
  - Upgrade prompt (when applicable)
  - Foundational panel
- **Result cards** — left-border colour indicates access level:
  - Green border = `ALLOWED` (full text + entities table + DOI)
  - Amber border = `SNIPPET_ONLY` (truncated preview + lock icon + upgrade note)
  - Blue border = `OPEN_ACCESS` (full text + entities table + DOI — same as ALLOWED)
  - Each card: journal pill, section label, source filename, expandable content, citation context toggle

### Content display (`ContentRenderer`)
- Strips entity prefix lines from chunk text before rendering
- Detects chunk type: table → HTML table with dark header row; figure → summary + caption; text → paragraph
- Markdown tables parsed from `| cell |` format

### Entity display (`EntityTags`)
- Summary pills per entity type (coloured dot + type + count)
- Three-column grid: type badge | entity text | ontology ID in monospace
- Up to 14 entities shown; "+N more" overflow

---

## 9. Corpus

**15 articles across 4 journals:**

| Journal | Code | Publisher | Domain | Articles | Rights demo |
|---------|------|-----------|--------|----------|-------------|
| Biochemical Journal | BJ | Portland Press | Biomedical | ~8 | Full text for Edinburgh; locked for TU Berlin |
| Redox Biology | REDOX | Elsevier | Biomedical | ~4 | Full text for Edinburgh |
| Energy Systems Research | ESR | Pleiades | Engineering | ~2 | Snippet only for TU Berlin; locked for Edinburgh |
| Project Leadership & Society | PLAS | Elsevier | Social science | ~1 | Full text for Global Policy |

**Open access articles:** `BJ_100885.xml`, `BJ_100950.xml` — always accessible regardless of institution

---

## 10. Demo Flow

### Recommended sequence to show governance features:

**Step 1 — Guest (no licence)**
- Log in as Guest
- Search: *"m6A methylation Theileria"*
- Show: Only 1 OA result visible; upgrade prompt explains N results are behind a subscription in Biochemical Journal and Redox Biology
- Key message: The AI gateway respects access rights — it does not leak content the user isn't entitled to

**Step 2 — University of Edinburgh (full biomedical access)**
- Switch to Edinburgh
- Repeat the same query
- Show: 6 full-text results, all from BJ/REDOX, full content + entity tags + DOI links
- Switch to an ESR/energy query (*"renewable energy EV charging"*) → locked content (no ESR licence)
- Key message: Licence is per-journal, per-institution. Same person, different journal = different access.

**Step 3 — TU Berlin (snippet-only for ESR)**
- Switch to TU Berlin
- Search: *"renewable energy EV charging"*
- Show: Results returned but truncated — snippet access only; lock icon and upgrade note visible
- Key message: SNIPPET_ONLY is a real, contractual access tier. The system can surface content exists without exposing it.

**Step 4 — Citation context**
- Expand a result card → open "Explore context"
- Show: Related articles, same-author works, foundational references
- Open the foundational panel below the result set
- Key message: Beyond just retrieval, Beacon surfaces the intellectual landscape around the result set

**Step 5 — Upgrade prompt**
- Return to Guest
- Run any biomedical query
- Show upgrade prompt: "N results found behind a subscription"
- Click "Sign in for access →" → returns to login
- Key message: The discovery layer works for everyone; the access layer is gated

---

## 11. What Is Real vs. Simulated

| Component | POC status |
|-----------|-----------|
| Enrichment pipeline | Real — GPT-4o-mini, NCBI/OLS APIs, ChromaDB |
| Vector search (embeddings) | Real — ChromaDB with real embeddings |
| Licence check logic | Real architecture, simulated data |
| Institution–journal mappings | Hardcoded in `license_config.json` |
| Authentication | Not implemented — institution selected from dropdown |
| "Bring Your Own Licence" | Not implemented — deferred |
| Citation graph | Real graph built from reference lists in the corpus |
| Publisher subscription mode | UI only — maps to hardcoded institution IDs |

---

## 12. Technical Stack

| Layer | Technology |
|-------|-----------|
| Enrichment | Python, lxml, OpenAI GPT-4o-mini, NCBI/OLS/Cellosaurus APIs |
| Vector DB | ChromaDB (local) |
| Backend API | FastAPI (Python), Pydantic, Uvicorn |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Fonts | Playfair Display (Google Fonts) — wordmark; system sans-serif — UI |
| Icons | Inline SVG (no icon library dependency) |

---

## 13. Open Questions / Next Steps

1. **Authentication** — replace dropdown with a real auth flow (SSO, OAuth, institutional login)
2. **Bring Your Own Licence** — allow institutions to connect their actual subscription entitlement data rather than hardcoded config
3. **Publisher API integration** — check licence in real time against publisher entitlement APIs (e.g., Elsevier TDM API)
4. **Corpus scale** — the POC uses 15 articles; production would need ingestion at journal scale
5. **Snippet policy** — define contractually what "snippet" means (word count, section reveal, etc.)
6. **Metered access** — usage tracking per institution per journal for audit and billing
7. **Multi-modal content** — figures are currently summarised as text; native image embedding is a future path
8. **Cross-journal author graph** — the citation graph currently shows sparse cross-journal links because the corpus disciplines don't overlap; a real corpus of same-field journals would surface richer relationships
