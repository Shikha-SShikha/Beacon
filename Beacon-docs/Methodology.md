# Methodology

A complete reference for every technique used across the enrichment pipeline and the retrieval system — what it is, how it works here, and why it was chosen.

---

## Part 1 — Content Enrichment (Indexing Time)

These steps run once per article when it enters the system. The output is stored in ChromaDB and `chunks/` JSON files.

---

### 1. XML Parsing

**What it is:** Structured document parsing using `lxml`, a Python library for XML/HTML processing.

**How it works here:**
Elsevier articles are delivered in DTD v5.7 XML. The DTD includes internal entity declarations (e.g. `&trade;`, `&reg;`) that cause standard parsers to fail if the DTD file isn't present. The pipeline strips the DOCTYPE block with a regex before parsing, then uses `lxml` in recovery mode with entity resolution disabled.

Article structure is navigated by local tag name (stripping namespace prefixes), extracting:
- **Metadata** from `<item-info>` and `<head>`: DOI, authors, publication date, abstract, keywords, journal ID
- **Body sections** from `<ce:sections>` — each top-level `<ce:section>` becomes a chunk group
- **Figures and tables** from `<ce:floats>` — extracted separately with label, caption, and table cell content

Tables are converted to Markdown using the CALS table model (`tgroup > thead/tbody > row > entry`).

---

### 2. Paragraph Chunking with Merge and Overlap

**What it is:** A deterministic chunking strategy that controls chunk size and prevents evidence loss at boundaries.

**How it works here:**

**Chunk extraction:** Each top-level section produces one or more paragraph-level chunks. Subsection titles are prepended to the first paragraph of each subsection for context.

**Small paragraph merging:** Consecutive paragraphs within the same subsection that are under 200 characters are merged forward until the combined text exceeds 300 characters. This prevents near-empty chunks that would produce meaningless embeddings.

**Sentence overlap:** The last sentence of each paragraph chunk is prepended to the beginning of the next chunk. This means every chunk except the first carries one sentence of its predecessor — ensuring that findings which span a paragraph boundary (e.g. a sentence setting up a result followed by the value itself) are present in at least one complete chunk.

---

### 3. Contextual Prefix Generation

**What it is:** Prompt engineering with GPT-4o-mini to generate a retrieval-optimised context sentence per chunk.

**How it works here:**
Each text chunk is sent to GPT-4o-mini with the article title, first author, year, journal, section type, subsection title, and the first 400 characters of the chunk text. The model is instructed to write a single sentence (max 40 words) starting with *"This [section_type] section from..."* that summarises what the chunk covers.

The prefix is prepended to the chunk text before embedding:
```
This results section from "m6A Modification in Theileria-Infected Macrophages" (Smith, 2023)
covers the effect of METTL3 knockdown on m6A levels in TBL20 cells.

[original paragraph text follows]
```

**Why:** Dense embeddings encode the semantic meaning of whatever text they receive. Without a prefix, an orphaned paragraph like *"As shown above, this was consistent with..."* produces a weak, context-free embedding. The prefix injects article identity, section role, and topic summary directly into the vector.

---

### 4. Figure and Table Claim Extraction

**What it is:** Prompt engineering with GPT-4o-mini to rewrite figure/table captions as factual scientific claims.

**How it works here:**
Each figure and table is sent to GPT-4o-mini with its label, caption, and (for tables) the Markdown-rendered cell content. The model is instructed to:
1. State the key finding as a factual claim (e.g. *"X inhibits Y by N%"*)
2. Include specific values, comparisons, or trends visible in the data
3. End with what the figure demonstrates in the context of the article's argument

The model is explicitly told to avoid *"this figure shows"* framing and to use active, definitive language. The output becomes the chunk text for that figure or table.

**Why:** Captions describe visual content; they do not assert findings. A caption that reads *"Western blot analysis of m6A levels in TBL20 cells after METTL3 knockdown"* will not match a query for *"METTL3 reduces m6A"*. The extracted claim will.

---

### 5. Named Entity Recognition (NER)

**What it is:** A two-stage pipeline combining GPT-4o-mini for extraction and external ontology APIs for ID resolution.

#### Stage 1 — GPT Extraction

Each chunk (up to 800 characters) is sent to GPT-4o-mini with a domain-aware prompt. The domain hint adapts by journal:
- BJ / REDOX → *"biomedical. Extract: GENE, PROTEIN, DISEASE, CHEMICAL, DRUG, CELL_LINE, ORGANISM"*
- PLAS → *"project management / social science. Extract: THEORY, METHOD, CONCEPT, FRAMEWORK, TOOL"*
- ESR → *"energy systems / engineering. Extract: TECHNOLOGY, METHOD, LOCATION, CONCEPT, METRIC"*

The model returns up to 8 entities as a JSON array: `[{"text": "METTL3", "type": "GENE"}, ...]`

#### Stage 2 — Ontology ID Resolution

For each entity type that has a suitable registry, the entity name is sent to an external API with a fallback chain:

| Entity type | Primary | Fallback |
|---|---|---|
| GENE / PROTEIN | NCBI Gene E-utilities (`esearch.fcgi`) — searches `[gene name]` field, tries Homo sapiens first then any organism | — |
| DISEASE | NLM MeSH lookup API — tries exact match then contains match | OLS Disease Ontology search (EBI OLS4) |
| CHEMICAL / DRUG | NLM MeSH lookup API | OLS ChEBI search — handles abbreviations like `m6A` registered as synonyms |
| CELL_LINE | Cellosaurus REST API — returns primary CVCL accession | — |
| SPECIES / ORGANISM | NCBI Taxonomy E-utilities (`esearch.fcgi`) — searches `[scientific name]` | — |
| METHOD / TECHNOLOGY / CONCEPT | Tagged only, no ontology | — |

Results are cached in-memory by `(entity_text_lower, type)` to avoid duplicate API calls within a run. NCBI rate limit is respected with a 0.35s delay between calls (3 req/sec free tier).

**Final output format:**
```
[GENE: METTL3 | NCBI Gene:56339] [CHEMICAL: m6A | ChEBI:CHEBI:21891] [CELL_LINE: TBL20 | Cellosaurus:CVCL_2G83]
```
This tag string is prepended to the enriched chunk text before it is stored in ChromaDB.

---

### 6. MeSH Hierarchy Traversal (SPARQL)

**What SPARQL is:** SPARQL is a query language for RDF graph databases, analogous to SQL for relational databases. NLM publishes the MeSH ontology as a linked data graph queryable via a public SPARQL endpoint.

**How it works here:**
After a disease or chemical entity is resolved to a MeSH D-number, the pipeline queries the NLM MeSH SPARQL endpoint for its direct parent descriptors using the `meshv:broaderDescriptor` property:

```sparql
SELECT ?label WHERE {
  mesh:D007938 meshv:broaderDescriptor ?parent .
  ?parent rdfs:label ?label .
  FILTER(lang(?label) = 'en')
}
```

Example hierarchy traversed one level up:
```
tropical theileriosis (D013789)
  → Theileria Infections
    → Protozoan Infections
      → Parasitic Diseases
```

Broader terms are stored on the entity dict and serialised as `skos:broader` nodes in the JSON-LD output. Results are cached by MeSH ID.

**Why:** A researcher querying for *"parasitic infections"* would not match an article that only uses the species-specific term *"tropical theileriosis"* without this hierarchy. Broader terms act as vocabulary bridges.

---

### 7. Semantic Relation Extraction

**What it is:** Prompt engineering with GPT-4o-mini to extract typed subject-predicate-object triples from each text chunk.

**How it works here:**
Each text chunk (up to 900 characters) is sent to GPT-4o-mini along with the list of already-extracted entities as anchor hints and a domain-specific predicate vocabulary. The model returns up to 5 triples per chunk with a verbatim evidence snippet from the text.

Domain predicate vocabularies:
- **BJ / REDOX:** regulates, inhibits, activates, binds, methylates, demethylates, phosphorylates, promotes, suppresses, recruits, stabilizes, degrades
- **PLAS:** enables, constrains, influences, validates, challenges, depends_on, integrates_with
- **ESR:** uses, produces, optimizes, improves, reduces, models, compares, scales_with

Output:
```json
{"subject": "METTL3", "predicate": "methylates", "object": "m6A", "evidence": "METTL3 methylates m6A on mRNA transcripts..."}
```

**Why:** Entity co-occurrence alone doesn't capture relationships. Two entities appearing in the same paragraph could be correlated, causal, inhibitory, or unrelated. Typed triples encode directionality and predicate — enabling structured queries like *"what does METTL3 do?"* to surface `(METTL3, methylates, m6A)` even if that exact phrasing doesn't appear in any chunk.

---

### 8. Figure-Claim Cross-Linking

**What it is:** Bidirectional linking between text chunks and their referenced figures/tables using regex pattern matching.

**How it works here:**
A compiled regex scans every text chunk for patterns like `Figure 3`, `Fig. 3A`, `Table 2`. Matched figure numbers are resolved to float chunk IDs (e.g. `fig3`, `tbl2`) via a lookup built from the extracted float metadata.

Two fields are written in-place:
- Text chunks get `figure_refs: ["fig3", "tbl1"]` — IDs of figures they cite
- Float chunks get `cited_in: ["chunk-id-A", "chunk-id-B"]` — IDs of text chunks that reference them

At retrieval time, when a text chunk is returned by search, `fetch_linked_figures()` does a batch `.get()` on ChromaDB to fetch all linked float chunks, which are then appended to the context block passed to the LLM.

**Why:** A paper's methods section might state a conclusion, but the quantitative evidence is in Figure 3. Without cross-linking, a query matching the text chunk retrieves the claim without the data that supports it.

---

### 9. JSON-LD Serialization (schema.org)

**What JSON-LD is:** JSON-LD (JSON for Linked Data) is a W3C standard for expressing structured data in JSON using a `@context` that maps keys to globally unique IRIs. schema.org is a vocabulary of types and properties maintained by Google, Microsoft, and others — designed so that web content can be machine-readable without a proprietary API.

**How it works here:**
Each enriched article is serialised as a `schema:ScholarlyArticle` node with a `@id` derived from its DOI:

```json
{
  "@context": {"schema": "https://schema.org/", "beacon": "...", "skos": "..."},
  "@type": "schema:ScholarlyArticle",
  "@id": "https://doi.org/10.1042/BCJ20230225",
  "schema:name": "Article title",
  "schema:mentions": [...entities with canonical @id IRIs...],
  "schema:hasPart": [...sections with relations and entity mentions...],
  "schema:image": [...figures as schema:ImageObject...],
  "schema:table": [...tables as schema:Table...]
}
```

**Entity IRIs** point to their authoritative ontology sources:
- NCBI Gene: `https://www.ncbi.nlm.nih.gov/gene/56339`
- MeSH: `https://id.nlm.nih.gov/mesh/D007938`
- ChEBI: `http://purl.obolibrary.org/obo/CHEBI_21891`
- Disease Ontology: `http://purl.obolibrary.org/obo/DOID_3733`
- Cellosaurus: `https://www.cellosaurus.org/CVCL_2G83`

Entities are deduplicated at article level — the same entity appearing in 12 different chunks produces one `schema:mentions` entry. Broader MeSH terms appear as `skos:broader` nodes. Relations are stored as `beacon:Relation` nodes under each section.

**Output:** One `.jsonld` file per article in `jsonld/`, portable and independent of ChromaDB.

---

## Part 2 — Retrieval (Query Time)

These steps run on every user query.

---

### 10. Dense Vector Search

**What it is:** Semantic similarity search using embedding vectors and cosine distance.

**How it works here:**
Both the document chunks (at indexing time) and the query (at query time) are converted to 1536-dimensional embedding vectors using OpenAI's `text-embedding-3-small` model. ChromaDB stores these vectors and uses cosine distance to find the nearest neighbours to the query vector.

**Cosine distance** measures the angle between two vectors — 0 means identical direction (semantically similar), 2 means opposite. Chunks are ranked by this distance, lowest first.

**Why it works and where it fails:** Dense vectors capture semantic meaning well — *"m6A methylation writer"* will match chunks about METTL3 even without exact term overlap. But they struggle with rare abbreviations like `PAI-1`, `YY1`, or `ALK` — the embedding model may have seen these terms rarely and encodes them poorly, or tokenises them in a way that loses their identity.

---

### 11. BM25 (Sparse Keyword Search)

**What BM25 is:** BM25 (Best Match 25) is a ranking function from information retrieval, developed in the 1990s and still the standard for keyword search. It is a refinement of TF-IDF (Term Frequency–Inverse Document Frequency) that adds two key improvements:
- **Term frequency saturation:** Repeated occurrences of a term in a document give diminishing returns (unlike raw TF which keeps increasing)
- **Document length normalisation:** Shorter documents aren't penalised for lower raw term counts

The BM25 score for a document given a query is:

```
score = Σ IDF(term) × (tf × (k1 + 1)) / (tf + k1 × (1 - b + b × dl/avgdl))
```

Where `tf` = term frequency in document, `dl` = document length, `avgdl` = average document length, and `k1`, `b` are tuning parameters (defaults: k1=1.5, b=0.75).

**How it works here:**
An in-memory `BM25Okapi` index is built from all documents in the `entity_enriched` ChromaDB collection on first query (singleton pattern, reused after). Documents are tokenised with a custom tokenizer that preserves internal hyphens and slashes — critical for biomedical terms like `PAI-1`, `HIF-1α`, `m6A` that would otherwise be split into meaningless fragments.

**Why it complements vector search:** BM25 excels precisely where dense vectors fail — exact term matching. A query for `PAI-1` scores any document containing that exact string very highly, regardless of semantic similarity. A query for `METTL3 knockdown` will surface chunks that contain both exact tokens even if the embedding model doesn't encode them well.

---

### 12. Hybrid Search with Reciprocal Rank Fusion (RRF)

**What RRF is:** Reciprocal Rank Fusion is a score-free method for combining ranked lists from multiple retrieval systems. Instead of trying to normalise and add incompatible scores (BM25 scores and cosine distances are on different scales), RRF converts each ranked list into a reciprocal rank score and sums them:

```
rrf_score(doc) = 1/(k + rank_vector) + 1/(k + rank_bm25)
```

`k=60` is the standard constant (from Cormack et al., 2009) that dampens the influence of top-ranked results and prevents any single system from dominating. A document ranked 1st in both systems scores `1/61 + 1/61 = 0.033`. A document ranked 1st in one and absent from the other scores `1/61 + 1/91 = 0.027`.

**How it works here:**
For each query, both vector search and BM25 search retrieve 3× the requested results (`fetch_n = min(top_k * 3, 30)`). The two ranked lists are merged into a union of candidate documents. For documents that only appear in one list, a default rank of `fetch_n + 1` is assigned for the missing source. All candidates are scored with the RRF formula and sorted descending.

**Why:** Neither vector search nor BM25 alone is optimal. Hybrid RRF lets each system contribute what it does best — semantic matching from vectors, exact term matching from BM25 — without requiring any score calibration between them.

---

### 13. Section-Aware Reranking

**What it is:** A post-retrieval score adjustment using query intent classification and section metadata — no LLM involved.

**How it works here:**

**Intent detection:** The query is classified into one of four intents by counting keyword matches:
- `factual` — "finding", "result", "show", "effect", "inhibit", "trial", "significant"
- `methodological` — "method", "how was", "protocol", "measure", "collect", "assay"
- `background` — "background", "overview", "prior", "what is"
- `conclusion` — "conclusion", "summary", "implication", "recommend"
- `general` — no clear intent or a tie

**Section multipliers:** Based on the detected intent, each retrieved chunk's distance is multiplied by a section-specific factor. Values below 1.0 boost the chunk (lower distance = higher rank); above 1.0 penalise it:

| Intent | results | methods | introduction | discussion |
|---|---|---|---|---|
| factual | 0.85 ✓ | 1.0 | 1.10 | 0.85 ✓ |
| methodological | 1.0 | 0.85 ✓ | 1.10 | 1.0 |
| background | 1.0 | 1.0 | 0.85 ✓ | 1.0 |
| conclusion | 1.0 | 1.10 | 1.10 | 0.85 ✓ |

**Recency decay:** A linear multiplier penalises older papers. A paper published today gets a multiplier of 1.0 (no penalty). A paper 5+ years old gets a multiplier of `1.0 + recency_weight` (default: 1.10, a 10% distance penalty). Age is calculated from `publication_date` metadata.

Final distance = `raw_distance × section_multiplier × recency_multiplier`

Results are re-sorted by final distance and re-ranked.

---

### 14. LLM Synthesis (RAG Answer Generation)

**What it is:** Retrieval-Augmented Generation — the retrieved chunks are assembled into a context block and passed to a language model to synthesise a coherent answer.

**How it works here:**
After retrieval, reranking, and license filtering, the top-k allowed hits are grouped by source article and formatted into a numbered context block:

```
[1] Article Title (BJ_100828, 2023)
  [results] This results section from... METTL3 knockdown reduces m6A levels...
  [figure] Figure 3: METTL3 knockdown reduces m6A modification levels by ~60%...

[2] Another Article Title (REDOX_200123, 2022)
  [methods] ...
```

This is sent to `gpt-4o-mini` with a system prompt instructing it to write a comprehensive answer using inline citations `[1]`, `[2]`, cite every factual claim, use precise scientific language, and not invent information not present in the sources. Temperature is set to 0.3 for reproducibility. Max tokens: 1500.

**The `/ask` vs `/baseline/ask` distinction:** Both endpoints use identical system prompts, temperature, and model. The only difference is what goes into the context block — `/ask` uses hybrid search + enriched chunks from `entity_enriched`, `/baseline/ask` uses plain vector search from `html_scrape` (no enrichment). This isolates the retrieval quality variable.

---

### 15. HyDE (Hypothetical Document Embeddings) — Not Implemented

**What HyDE is:** HyDE is a query expansion technique where, instead of embedding the raw query, the LLM first generates a *hypothetical answer* to the query, and that hypothetical document is then embedded. The idea is that a hypothetical answer lives in the same semantic space as real documents — it uses the same vocabulary and structure — so its embedding is a better search vector than the short, often ambiguous query string.

Example: The query *"PAI-1 role in leukemia"* becomes *"PAI-1 (plasminogen activator inhibitor-1) plays a significant role in leukemia by promoting cell survival and proliferation through inhibition of fibrinolysis..."* — and that full paragraph is embedded.

**Status here:** The `hyde` field exists in `SearchRequest` but is not wired up in `search_service.py`. It would add approximately 1 second of latency per query (one extra LLM call) and roughly $0.001 in cost. The main benefit would be for very short or ambiguous queries where the query string itself is a poor embedding target.

---

## Summary Table

| Step | Methodology | AI / Deterministic |
|---|---|---|
| XML parsing | lxml with DTD stripping | Deterministic |
| Paragraph chunking | Merge < 200 chars + 1-sentence overlap | Deterministic |
| Contextual prefix | GPT-4o-mini prompt engineering | AI |
| Figure/table claim extraction | GPT-4o-mini prompt engineering | AI |
| NER extraction | GPT-4o-mini + NCBI/MeSH/ChEBI/Cellosaurus APIs | AI + API |
| MeSH hierarchy traversal | SPARQL query on NLM endpoint | API (deterministic) |
| Relation extraction | GPT-4o-mini with domain predicate vocabularies | AI |
| Figure cross-linking | Regex pattern matching + bidirectional index | Deterministic |
| JSON-LD serialization | schema.org + skos + beacon vocab | Deterministic |
| Dense vector search | text-embedding-3-small + ChromaDB cosine distance | AI (embedding) |
| BM25 keyword search | BM25Okapi with biomedical-aware tokenizer | Deterministic |
| Hybrid fusion | Reciprocal Rank Fusion (RRF, k=60) | Deterministic |
| Reranking | Intent keyword matching + section multipliers + recency decay | Deterministic |
| Answer synthesis | GPT-4o-mini RAG with inline citations | AI |
| HyDE | Hypothetical document embedding (not implemented) | AI |
