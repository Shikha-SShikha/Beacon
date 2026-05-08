# Pipeline Comparison: End-to-End vs. Staged Enrichment

## The Core Difference

The end-to-end pipeline treats enrichment as a **post-production batch job** — a single script run after an article is finalized. The staged pipeline embeds enrichment **inside the editorial workflow**, distributing work across the two touchpoints where a human is already handling the article: copyedit and mastercopy.

---

## Side-by-Side Overview

|                         | End-to-End (`pipeline.py`)   | Staged (`stage_copyedit` → review → `stage_mastercopy`)      |
| ----------------------- | ---------------------------- | ------------------------------------------------------------ |
| **When it runs**        | After production is complete | During production, across two editorial stages               |
| **Input**               | One XML (final or proof)     | Two XMLs — Copyedit.xml + Proof.xml                          |
| **Human involvement**   | None                         | Editorial review at copyedit stage                           |
| **Entity verification** | No human check               | Human scans and rejects wrong entities                       |
| **Enrichment passes**   | One pass, all steps together | Split: lightweight pass at copyedit, full pass at mastercopy |
| **Output format**       | `chunks/<stem>_chunks.json`  | Same format — drop-in compatible with ChromaDB               |

---

## How the Steps Are Distributed

### End-to-End Pipeline — all steps in one pass

| Step | What happens |
|---|---|
| 1 | Parse Elsevier DTD XML |
| 2 | Extract metadata + section chunks |
| 3 | AI contextual prefix per chunk |
| 4 | AI figure/table claim extraction |
| 5 | NER: GPT entity extraction + ontology ID resolution |
| 6 | Semantic relation extraction |
| 7 | Figure cross-linking |

All seven steps run once, sequentially, on a single XML file. No human sees the output before it enters the index.

---

### Staged Pipeline — steps split across editorial stages

**Copyedit stage** — runs on `Copyedit.xml` (draft with track changes)

| Step | What happens |
|---|---|
| 1 | Parse flat editorial XML, apply ins/del track changes |
| 2 | Extract metadata + section/paragraph structure |
| 3 | NER Stage 1: GPT extracts entity names + types only (no IDs yet) |

Output: `enrichment_copyedit.json` — draft manifest with unverified entities.

---

**Human review** — runs in `review_app.py`

The editorial team scans entity chips grouped by type. Wrong extractions (e.g. an imaging score tagged as GENE, or an author name tagged as PROTEIN) are rejected with one click. Types can be corrected. Everything else is approved by default. Takes under a minute for a typical article.

---

**Mastercopy stage** — runs on `Proof.xml` (final proofed XML)

| Step | What happens |
|---|---|
| 1 | Parse Elsevier DTD XML (proofed version) |
| 2 | Load reviewed copyedit manifest → read rejected entities |
| 3 | Diff copyedit vs. mastercopy text by section |
| 4 | AI contextual prefix per chunk |
| 5 | AI figure/table claim extraction |
| 6 | NER Stage 2: GPT extraction + ontology ID resolution; rejected entities filtered out |
| 7 | Semantic relation extraction |
| 8 | Figure cross-linking |

Output: `enrichment_mastercopy.json` + `chunks/Proof__chunks.json` (same format as end-to-end output).

---

## Why Split NER Across Two Stages

The end-to-end pipeline runs NER once — entity extraction and ID resolution together. The staged pipeline separates them deliberately:

- **Stage 1 (copyedit):** GPT identifies what the entities *are* — names and types. This is fast and can surface obvious errors while the article is still being edited.
- **Human review:** A human confirms the type classifications are correct. This is the only gate.
- **Stage 2 (mastercopy):** Ontology IDs are resolved against NCBI, MeSH, ChEBI, and Cellosaurus *only for approved entities*. No API calls are wasted on entities a human already flagged as wrong.

Relations and figure claims run only at mastercopy because they depend on the final stable text — running them on a draft copyedit would require re-running them anyway after proofreading corrections.

---

## What Changes in the Output

The chunks JSON format is identical in both pipelines. The difference is in what's inside each chunk's `entities` array:

| | End-to-End | Staged |
|---|---|---|
| Entity source | GPT extraction, unverified | GPT extraction, human-reviewed |
| Ontology IDs | Resolved (best-effort) | Resolved only for approved entities |
| Rejected entities | Not possible | Excluded from index |
| `verified_by` field | Not present | `"human"` for reviewed, `"stage_mastercopy"` for auto |
| `status` field | Not present | `"verified"` or `"rejected"` |

---

## The Tradeoff

The end-to-end pipeline is simpler — one command, one file, done. It's the right approach when you have a completed article corpus and want to enrich everything in batch.

The staged pipeline is more complex but produces a cleaner index: entities that a human confirmed are wrong never enter the vector database. For a production publishing workflow where the article is already passing through human hands at copyedit and mastercopy, the review step adds almost no overhead — the editor is already reading the article.

Both pipelines produce the same chunk JSON format and feed into the same ChromaDB ingestion and chat interface. Both also feed into `jsonld_serializer.py`, which serialises each article as a `schema:ScholarlyArticle` with canonical entity IRIs (NCBI Gene, MeSH, ChEBI, Cellosaurus) and `skos:broader` MeSH hierarchy terms — output goes to `jsonld/`. Note: `jsonld_serializer.py` is a separate manual step not auto-called by either pipeline.

---

## Failure Mode Coverage

Every failure mode addressed by the pipeline, mapped against both versions. ✅ = handled · ⚠️ = requires separate step · ➕ = staged handles better than end-to-end.

### XML Parsing & Structure Extraction

| Failure mode | End-to-End | Staged |
|---|---|---|
| DTD parsing failure — standard parsers reject Elsevier DTDs | ✅ DOCTYPE stripped, lxml `recover=True` | ✅ Same (two separate parsers for editorial vs. DTD XML formats) |
| Paragraph fragmentation — near-empty chunks lose context | ✅ Tiny paragraphs merged; one-sentence overlap prepended | ✅ Same |
| Cross-chunk evidence loss — finding spans a paragraph boundary | ✅ Sentence overlap carries trailing context forward | ✅ Same |

### Contextual Prefix Generation

| Failure mode | End-to-End | Staged |
|---|---|---|
| Decontextualisation — orphaned paragraphs carry no meaning in isolation | ✅ AI prefix encodes article, section, and topic per chunk | ✅ Same — runs at mastercopy on final proofed text |
| Section-blind retrieval — methods and results paragraphs on the same topic are indistinguishable | ✅ Section type injected into prefix | ✅ Same |
| Author/recency blindness — no signal for authorship or year in the vector | ✅ First author and year included in prefix | ✅ Same |

### Figure & Table Claim Extraction

| Failure mode | End-to-End | Staged |
|---|---|---|
| Figure invisibility — baseline stores `[IMAGE]` placeholders | ✅ AI generates a factual finding claim per figure/table | ✅ Same — runs at mastercopy |
| Caption-only matching — captions describe what a figure contains, not what it proves | ✅ Claim written as a finding ("X increases with severity"), not a description | ✅ Same |
| Quantitative evidence loss — percentages and statistics that live only in figures never enter the index | ✅ Specific values, fold-changes, and comparisons extracted explicitly | ✅ Same |

### Named Entity Recognition + Ontology ID Resolution

| Failure mode | End-to-End | Staged |
|---|---|---|
| Synonym drift — `m6A`, `N6-methyladenosine`, `m⁶A` are the same entity | ✅ All resolve to the same ChEBI ID | ✅ Same |
| Abbreviation opacity — `PAI-1`, `YY1` are opaque to a general embedder | ✅ Canonical ontology IDs make abbreviations searchable by ID | ✅ Same |
| Cross-paper entity fragmentation — same entity in two papers are just similar strings without IDs | ✅ Shared canonical IDs link the same entity across all articles | ✅ Same |
| Wrong entity type classification — imaging scores tagged as GENE, author names as PROTEIN | ❌ No gate; bad entities enter the index | ➕ Human review catches misclassifications before ID resolution; rejected entities never enter the index |

### Semantic Relation Extraction

| Failure mode | End-to-End | Staged |
|---|---|---|
| Entity co-occurrence without relationship — two entities in the same chunk doesn't mean they interact | ✅ Typed triples extracted; co-occurrence alone doesn't create a relation | ✅ Same — runs at mastercopy |
| Implicit finding retrieval — "knockdown of X reduced Y" is not explicit in the text | ✅ GPT extracts explicit `(X, reduces, Y)` triples with evidence snippets | ✅ Same |
| Query-predicate mismatch — "what inhibits X" should match a chunk asserting `(Y, inhibits, X)` | ✅ Predicate is stored as a typed field, enabling predicate-aware retrieval | ✅ Same |

### MeSH Hierarchy Traversal

| Failure mode | End-to-End | Staged |
|---|---|---|
| Specificity mismatch — query uses genus-level term, article uses species-level | ✅ MeSH SPARQL walks one level up via `meshv:broaderDescriptor` | ✅ Same |
| Vocabulary siloing — each paper uses its own precise terms | ✅ Broader parent terms stored on entity; normalises upward to shared concepts | ✅ Same |

### Figure-Claim Cross-Linking

| Failure mode | End-to-End | Staged |
|---|---|---|
| Evidence fragmentation — finding is in text, data is in the figure | ✅ Text chunks citing a figure get `figure_refs`; figure gets `cited_in` | ✅ Same — runs at mastercopy |
| Orphaned figures — a figure with rich quantitative content may not match the query string directly | ✅ Linked via its citing text chunk, which will match | ✅ Same |

### JSON-LD Serialisation

| Failure mode | End-to-End | Staged |
|---|---|---|
| Enrichment lock-in — without serialisation all semantic enrichment is internal pipeline state | ⚠️ `jsonld_serializer.py` must be run separately after `pipeline.py` | ⚠️ Same — run separately after `stage_mastercopy.py` |
| Entity deduplication — same entity in 12 chunks should produce one `schema:mentions` entry | ⚠️ Handled inside `jsonld_serializer.py` (dedup by text+type) | ⚠️ Same |
| Knowledge graph interoperability — entity IRIs should resolve to live ontology records | ⚠️ Handled inside `jsonld_serializer.py` (canonical IRIs for all resolved entities) | ⚠️ Same |

---

### Summary

Of the 22 failure modes across all eight steps:

- **21 are handled identically** in both pipelines — the same technical approach, just distributed differently across stages in the staged version.
- **1 is handled better in the staged pipeline** — wrong entity type classification. The end-to-end pipeline has no gate; the staged pipeline has a human review step that catches these before they enter the index.
- **3 require a separate manual step in both** — the JSON-LD failure modes, which depend on running `jsonld_serializer.py` after the main pipeline completes.
