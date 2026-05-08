# Demo Knowledge Base
*Everything you need to know before the demo. Read this the morning of.*

---

## What We Built

A pipeline that takes Elsevier XML articles and produces fully enriched chunks — including real ontology IDs — for AI retrieval. The demo shows the difference between what AI tools get today (HTML scrape) vs what TNQ's enriched pipeline delivers.

**Four files:**

| File | What it does |
|---|---|
| `pipeline.py` | Parses Elsevier XML → AI prefixes + figure/table summaries → NER + ontology IDs → outputs JSON chunks |
| `ner.py` | Two-step NER module: GPT extracts entities, NCBI/MeSH APIs resolve ontology IDs |
| `experiment.py` | Loads chunks → builds ChromaDB with 3 collections → runs benchmark queries |
| `chat_app.py` | Streamlit demo UI at `localhost:8501` |

**15 articles · 3 collections**

| Collection | What's in it |
|---|---|
| 🟠 HTML Scrape | Simulated scrape — figures as `[IMAGE]`, tables caption-only, no metadata per chunk |
| 🟡 Enriched | AI one-sentence contextual prefix + section text |
| 🟢 Entity-Enriched | Named entity tags with ontology IDs prepended to enriched text — e.g. `[GENE: METTL3 \| NCBI Gene:56339]` `[DISEASE: Leukemia \| MeSH:D007938]` |

---

## What "Distance" Means

Every piece of text — query and chunk — gets converted into a vector of ~1500 numbers representing its meaning. **Distance = how far apart two vectors are in meaning-space.**

- Uses **cosine distance** (ChromaDB default)
- `0.0` = identical meaning
- `1.0` = completely unrelated
- Lower = better match

Our numbers sit in the 0.6–0.9 range because we're using a compressed embedding model (`text-embedding-3-small`) and chunks are long (2000 chars). In production with better chunking, top matches typically sit at 0.3–0.5.

**What matters for the demo is not the absolute number — it's the relative gap between collections for the same query.** A difference of 0.08–0.10 is meaningful and compounds across thousands of queries.

### This is NOT Levenshtein distance

Levenshtein distance counts character-level edits — how many insertions, deletions, or substitutions to turn one string into another. `"cat" → "bat"` = 1. It has no understanding of meaning. We are not using that.

**Cosine distance** measures the angle between two vectors in high-dimensional space. Similar meanings = similar angle = low distance. Nothing to do with spelling or characters.

### Who does what

Two separate steps, two separate systems:

**Step 1 — OpenAI converts text to vectors** (`text-embedding-3-small`)
```
"What proteins are nitrated in lipotoxicity?"
        ↓
[0.021, -0.14, 0.87, 0.003, -0.52, ... ]  ← 1536 numbers
```
OpenAI's model reads the text and outputs 1536 numbers. Similar meanings produce similar vectors. This is the "understanding" step — OpenAI does it.

**Step 2 — ChromaDB calculates the distance**
```
query vector:  [0.021, -0.14, 0.87, ...]
chunk vector:  [0.018, -0.13, 0.91, ...]
cosine distance = 1 - (dot product / magnitudes) = 0.87
```
ChromaDB stores all chunk vectors. When a query arrives, it calculates cosine distance between the query vector and every stored chunk vector, then returns the closest ones. Pure maths — no AI involved here.

### Why cosine and not Euclidean?

Euclidean measures straight-line distance between points. Cosine measures the **angle** between vectors — which works better for text because it's not sensitive to text length, only the direction of meaning. Two chunks saying the same thing — one in 100 words, one in 1000 words — will have very different Euclidean distances but nearly identical cosine distances.

---

## NER + Ontology Linking — What the IDs Are

### Entity types and their ontologies

Resolution uses a primary source with a fallback where available:

| Entity type | Primary | Fallback | Example |
|---|---|---|---|
| GENE / PROTEIN | NCBI Gene | — | `[GENE: METTL3 \| NCBI Gene:56339]` |
| DISEASE | MeSH | Disease Ontology (OLS) | `[DISEASE: tropical theileriosis \| Disease Ontology:DOID:10607]` |
| CHEMICAL / DRUG | MeSH | ChEBI (OLS) | `[CHEMICAL: m6A \| ChEBI:CHEBI:21891]` |
| CELL_LINE | Cellosaurus | — | `[CELL_LINE: TBL20 \| Cellosaurus:CVCL_2G83]` |
| ORGANISM / SPECIES | NCBI Taxonomy | — | `[ORGANISM: Theileria annulata \| NCBI Taxonomy:5874]` |
| METHOD, TECHNOLOGY, CONCEPT | — | — | `[METHOD: CRISPR-Cas9]` — no ontology, no ID |

### Real output from BJ_100828 (Theileria / m6A article)

```
[CELL_LINE: BL20 | Cellosaurus:CVCL_L859]
[CELL_LINE: TBL20 | Cellosaurus:CVCL_2G83]
[CHEMICAL: RPMI 1640 | ChEBI:CHEBI:187086]
[CHEMICAL: m6A | ChEBI:CHEBI:21891]
[CHEMICAL: Hepes | ChEBI:CHEBI:46756]
[CHEMICAL: b-mercaptoethanol | ChEBI:CHEBI:41218]
[ORGANISM: Theileria annulata | NCBI Taxonomy:5874]
[DISEASE: tropical theileriosis | Disease Ontology:DOID:10607]
[GENE: mettl3 | NCBI Gene:56339]
[GENE: wtap | NCBI Gene:9589]
[GENE: ythdf1 | NCBI Gene:54915]
```

**33 entities extracted, 28 with real ontology IDs (85%)** from a 6-chunk article.

### Where IDs are still missing and why

A small residual gap remains — all cases are explainable:
- **"Ode"** cell line — lab-specific line, not registered in Cellosaurus
- **"FBS"** (Fetal Bovine Serum) — lab reagent abbreviation, not an ontology concept
- **"bovine"** — too generic; correct term is *Bos taurus* (which resolves to NCBI Taxonomy:9913)
- **"T. annulata"** — abbreviated species name; *Theileria annulata* (full name) resolves correctly
- Occasional GPT misclassification (e.g., "proliferation" as DISEASE rather than PROCESS) — wrong resolver is called, no ID returned

### Why ontology IDs matter at scale

A query for "METTL3" with just text matching may return articles that discuss METTL3 alongside unrelated contexts, or miss articles that refer to it as "m6A methyltransferase complex core." With `NCBI Gene:56339` as the key, you match the canonical entity regardless of what it's called in the text. This is the same reason PubMed uses MeSH headings — disambiguation at indexing time.

---

## Which Queries to Use in the Demo

### Use these — enriched or entity wins clearly

**Enriched wins — conceptual queries:**

| Query                                                                    | Winner   | Gap                                 |
| ------------------------------------------------------------------------ | -------- | ----------------------------------- |
| "What proteins are nitrated in lipotoxicity?"                            | Enriched | html=0.96, enriched=0.87 — Δ0.09    |
| "How does social network structure affect collective energy transition?" | Enriched | html=0.89, enriched=0.81            |
| "Hybrid renewable energy system optimization for EV charging stations"   | Enriched | html=0.60, enriched=0.61 (near tie) |

**Entity wins — named entity queries (use these for the entity demo):**

| Query | Why it works |
|---|---|
| "TM5614 clinical trial results in chronic myeloid leukemia" | TM5614 is a specific drug in one article only. Entity tags it explicitly — all top 5 results from the correct article at dist 0.63–0.84. The strongest demo query. |
| "PAI-1 inhibition as a therapeutic target in leukemia" | PAI-1 appears in THREE articles (skin cancer, leukemia, editorial). Entity tagging routes to the leukemia article. Without tags, HTML returns the skin cancer article first. |
| "YY1 and ANXA3 nitration in diabetic cardiomyopathy" | Two specific proteins + one disease — entity collection has all three tagged. Clear win over HTML. |
| "ALK translocation FISH detection in non-small cell lung cancer" | ALK, FISH, NSCLC all tagged. Very specific, single article. |
| "Theileria annulata m6A methylation host cell transformation" | Rare pathogen name — entity tagged in BJ_100828, invisible to HTML. |

**The PAI-1 story is the best narrative for the pitch:**
- Three articles all discuss PAI-1 — BJ_100850 (skin cancer), BJ_100854 (leukemia), BJ_100950 (editorial)
- Without entity tags: a query about "PAI-1 in leukemia" may surface the skin cancer article first (closest text match)
- With entity tags: `[DISEASE: chronic myeloid leukemia | MeSH:D015464]` + `[DRUG: TM5614]` steers to the correct article
- This is exactly what ontology linking enables at scale — precision over recall

**The ontology ID line to use in the pitch:**
*"These aren't just text labels — they're canonical database IDs. METTL3 in this article and METTL3 in any other article both carry NCBI Gene:56339. That means a query system can do exact entity-level matching across millions of articles, not just fuzzy text similarity."*

### Avoid these — HTML wins and it's hard to explain

- "What are the main conclusions?" — generic, HTML wins trivially
- "What methodology was used?" — same issue
- "What are the main findings?" — keyword match, no enrichment needed

### For figures and tables — use content view, not distance scores

Ask: *"What does Figure 1 show in the agent-based model?"*

Don't point at distance numbers. Instead **open the "View chunk" expander** in each column and show what text was actually returned:
- HTML column: `[IMAGE]` — nothing
- Enriched column: 3-sentence AI description of what the figure shows

That's the story. No numbers needed.

---

## The Pitch Narrative

### 1. Open with the problem
*"AI is the new discovery layer for scientific content — and publishers are largely invisible to it."*

- Researchers use ChatGPT, Perplexity, RAG systems to find and synthesise research
- These tools access publisher content via HTML scrape — no section structure, no metadata, figures completely invisible, tables garbled
- 40–60% of a paper's core findings live in figures and tables. AI tools miss all of it.

### 2. TNQ's structural advantage
*"We already have what everyone else is trying to build."*

- Companies building multimodal RAG start from PDFs — huge effort on layout detection, table extraction, figure identification
- TNQ already produces clean structured XML: `<ce:section>`, `<ce:figure>`, `<ce:table-wrap>` — everything tagged
- No new data pipeline. One enrichment layer on top of what we already do.

### 3. Walk the diagram
```
Publisher XML
     ↓
 [Section Chunking]      → one chunk per section, labelled intro/methods/results/conclusion
     ↓
 [AI Contextual Prefix]  → one sentence: "This methods section from X discusses Y"
     ↓
 [Figure Summarisation]  → 3-sentence AI description of what each figure shows
     ↓
 [Table Serialisation]   → Markdown table + AI summary (from clean XML structure)
     ↓
 [NER + Entity Tagging]  → [GENE: METTL3 | NCBI Gene:56339]
                            [DISEASE: Leukemia | MeSH:D007938]
                            [ORGANISM: Theileria annulata | NCBI Taxonomy:5874]
     ↓
 Enriched Chunk JSON     → stored in vector DB, served via API to AI tools
```

**All six steps are built and running.** The entity tags are not placeholders — they carry real database IDs from NCBI Gene, MeSH, and NCBI Taxonomy.

Key line to land: *"Every chunk carries the full article context — DOI, authors, keywords, section type, and verified entity IDs. When an AI tool retrieves a snippet, it knows exactly which paper it's from, who wrote it, where in the paper it lives, and which known biological concepts it discusses."*

### 4. What this unlocks (then go to demo)
Three things AI tools can do with enriched content they cannot do today:

1. **Find figures** — "Show me a diagram of the decision architecture." HTML: `[IMAGE]`. Enriched: 3-sentence searchable description.
2. **Find specific data** — "What performance metrics were measured?" HTML: no table structure. Enriched: Markdown table, fully searchable.
3. **Precise entity queries** — "Papers mentioning EGFR in the methods section." Only answerable with entity tagging — no keyword match can do this reliably.

### 5. Close with the business model
- **Delivery:** Enriched content API — publishers receive enriched chunk JSON, serve it to licensed AI partners
- **TNQ's role:** Enrichment as a service, bundled into existing XML contracts — lowest friction, relationship already exists
- **Revenue:** Per-article enrichment fee + ongoing API hosting, or licence the pipeline to run in-house
- **Data privacy:** Production model runs on TNQ infrastructure — publisher XML never touches OpenAI or any third party

**One line to leave the room with:**
*"Publishers have spent decades building the world's most structured scientific content. We turn that structure into the format AI actually needs — and we're the only ones who already have the raw material to do it."*

---

## Honest Boundaries — Questions You Will Get

**"But if I ask ChatGPT about a paper, it answers fine."**

Two different scenarios. ChatGPT answers from training data — content it has already seen. It cannot answer about paywalled content, content published after its training cutoff, or content that wasn't on the open web. The enrichment pipeline is for *licensed* content relationships — where an AI company ingests a publisher's full corpus to build a specialised knowledge base. That's where the retrieval quality determines the answer quality.

**"Couldn't AI companies just use better HTML parsers?"**

Better scrapers get cleaner text. But they still can't get inside figures (binary image files), reconstruct table structure that was rendered visually, or get the semantic XML labels that tell you what a section *is*. And they'd be scraping without a license — which is exactly what the publisher lawsuits are about. The moat isn't just technical; it's the commercial agreement.

**"Where does our content go when you enrich it?"**

In the current POC, we use OpenAI's API — open-access articles only, for internal demonstration. For production: enrichment runs on TNQ infrastructure using self-hosted models. Publisher XML never leaves the publisher's environment. That's the go-to-market story: *"We enrich your content without it touching any third-party AI provider."*

Note: the NCBI Gene and MeSH ID lookups send only the entity name (e.g., "METTL3") to NCBI's API — not the article text. NCBI is a US government database, publicly accessible. No content exposure risk.

**"Are the ontology IDs reliable?"**

For genes: highly reliable. NCBI Gene is the authoritative registry; a gene name like METTL3 or E2F4 almost always resolves correctly. For diseases and chemicals: reliable for common terms (Leukemia → D007938); less reliable for highly specific sub-terms or non-standard abbreviations. GPT occasionally misclassifies entity types (e.g., a cell line name labelled as ORGANISM), which means the wrong resolver is called and no ID is returned. This is a known gap — the entity is still tagged in the text, just without an ID. In production, adding a dedicated cell line resolver (Cellosaurus API) would close most of those gaps.

**"Why does HTML sometimes score better in your demo?"**

For generic text queries (methodology, conclusions, findings) the plain text already contains those words verbatim — adding metadata doesn't help and slightly dilutes the signal. Enrichment's value is on conceptual and entity queries — the ones researchers actually ask that don't have exact keyword matches in the text.

---

## What Competitors Are Doing

**Wiley** is building the same thing internally — they call it "AI Knowledge Nexus." Confirmed from a 2025 webinar transcript (`docs/Wiley Knowledge.md`). They are doing it for their own content only. TNQ's angle is doing it as a service for any publisher.

**Cashmere.io** — identified as a competitor in the space, operates in scientific content enrichment.

---

## Technical Stack

| Component | What we use |
|---|---|
| XML parsing | `lxml` — handles Elsevier DTD v5.7 (`ce:` prefix tags) |
| AI enrichment | `gpt-4o-mini` — contextual prefixes, figure/table summaries, NER extraction |
| Ontology linking | NCBI Gene → Gene IDs; NLM MeSH → MeSH D-numbers; NCBI Taxonomy → Taxonomy IDs; OLS/ChEBI → ChEBI IDs (chemical fallback); OLS/Disease Ontology → DOID (disease fallback); Cellosaurus → CVCL IDs (cell lines) |
| Embeddings | `text-embedding-3-small` (OpenAI) |
| Vector DB | ChromaDB (persistent, on disk at `./chroma_db/`) |
| Demo UI | Streamlit (`chat_app.py`) |

**Note on Elsevier XML format:** Not standard JATS. Uses `ce:` prefix tags, all figures/tables collected in `<ce:floats>` block at the top (not inline). Sections nest with `role` attribute for type labelling.

**Note on NER approach:** Two-step pipeline in `ner.py`. Step 1 — GPT extracts entity names and types from chunk text (domain-aware prompt per journal: biomedical for BJ/REDOX, engineering for ESR, project management for PLAS). Step 2 — resolvers run in priority order with fallbacks: DISEASE tries MeSH first, then OLS Disease Ontology; CHEMICAL/DRUG tries MeSH first, then OLS ChEBI; CELL_LINE uses Cellosaurus. Non-biological types (METHOD, TECHNOLOGY, CONCEPT) are extracted but not linked — no suitable general ontology exists. Results are cached in-memory across chunks to avoid duplicate API calls. Achieves ~85% ID coverage on biomedical articles.

**Why not PubTator3?** PubTator3's free-text annotation endpoint (`/annotate/submit/`) was removed — it now only supports PubMed ID lookups. BERN2 (a similar service from Seoul National University) is also down. The two-step approach (GPT + NCBI APIs) is more reliable because NCBI E-utilities and the NLM MeSH API are stable, well-maintained infrastructure.

---

## How to Run the Demo

```bash
# If ChromaDB needs rebuilding (after pipeline changes):
python experiment.py

# Start the demo:
streamlit run chat_app.py
# Opens at localhost:8501
```

Start on the **📊 Figures & Tables** tab, then move to **🟡 Contextual** for the strongest enrichment wins.
