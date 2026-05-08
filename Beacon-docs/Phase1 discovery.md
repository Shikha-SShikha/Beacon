# Beacon — Phase 1 Discovery

## Problems We're Solving

1. **Trust erosion** — AI usage among researchers jumped from 57% to 84% (2024→2025), but confidence in those tools has decreased. More usage, less trust.

2. **Bypassed infrastructure** — Researchers are using ChatGPT, Claude, etc. to access research content without ever visiting publisher websites. The human-centric pipeline (Google → publisher site → content) is being circumvented by agentic AI tools.

3. **Revenue model threat** — Publisher business strategies are built around a human-centric model. If researchers never visit your site, your subscription/access model breaks down.

4. **Loss of citability and impact tracking** — When AI tools synthesize from hundreds of papers, how does a single paper get cited? How do you measure impact? Traditional metrics (downloads, citations) stop working.

5. **Provenance and attribution** — AI tools can surface content without linking back to the source. No way to verify where information came from.

6. **Retraction/correction blindness** — AI tools don't know if a paper has been retracted or corrected. They serve stale or discredited content with no flag.

7. **Content not AI-ready** — Even high-quality published content isn't in a format AI tools can efficiently retrieve. It needs enrichment — chunking, vectorization, entity tagging, metadata embedding.

8. **Open access complicates licensing** — If content is freely available, does the licensing model collapse? (No — enrichment still has value, but it's a real concern.)

9. **Small publishers left behind** — Smaller publishers lack dedicated licensing infrastructure to negotiate directly with AI companies. They can't access this market alone.

10. **Speed of change** — LLM training deals were hot in 2023–2024, already cooling. Publishers who waited missed the window.

---

## Gap Analysis — Current Implementation vs. Problems

### What we've built well

| Problem                      | What addresses it                                                                                  |
| ---------------------------- | -------------------------------------------------------------------------------------------------- |
| **#7 Content not AI-ready**  | Core strength. Chunking, NER+ontology IDs, AI prefixes, figure/table summaries.                    |
| **#3 Revenue model**         | License service with ALLOWED/SNIPPET_ONLY/NO_ACCESS tiers per institution.                         |
| **#8 Open access licensing** | OA flag handled in license config.                                                                 |
| **#9 Small publishers**      | Multi-journal architecture + flexible license config supports this.                                |
| **#5 Provenance**            | DOI stored in chunk metadata, returned in search results. Citation graph is a real differentiator. |

---

### Real gaps

**Gap 1: Retraction/correction blindness (Problem #6) — nothing implemented**
The pipeline has no check against Retraction Watch or CrossRef retraction metadata. We're potentially serving discredited content with full confidence. This is the most dangerous gap — it's also a trust erosion driver (Problem #1).

**Gap 2: No AI-native interface (Problem #2)**
We have a REST API, but AI tools (ChatGPT, Claude, etc.) don't call REST APIs unless they have an explicit integration. To actually intercept how AI tools access research content, we need to be in the agent tool ecosystem:
- An **MCP server** so Claude can call our search natively
- An **OpenAI function tool definition** for GPT

Without this, our API exists but agents will never use it — they'll still just scrape or use training data.

**Gap 3: No usage/attribution analytics (Problem #4)**
When a chunk is served via the API, we don't log: who used it, what query triggered it, whether it was cited downstream. We have no answer to "how does a paper measure its AI-era impact?" The citation graph is great for intra-corpus relationships, but there's no telemetry for actual AI consumption.

**Gap 4: Provenance format AI tools won't use (Problem #5)**
DOI is in metadata but as a bare string. AI tools won't automatically turn that into a citation. We need a `citation_hint` field in each result — a ready-to-use citation string (APA/BibTeX format) so the AI tool can drop it inline.

**Gap 5: Trust signals too implicit (Problem #1)**
NER+ontology IDs improve accuracy, but we're not surfacing trust signals explicitly: no journal impact factor, no peer review flag, no retraction status, no confidence score on the chunk itself. A researcher using an AI tool can't tell *why* our result is more trustworthy than a Wikipedia chunk.

---

## Better Ways to Improve Discoverability

**1. MCP server wrapping the search endpoint**
Highest-leverage move. If our search is an MCP tool, every Claude user can call it. The technical lift is small — FastAPI endpoint already exists, just needs an MCP wrapper. Directly addresses Problem #2 — instead of being bypassed, we become the tool.

**2. Structured citation hints per chunk**
Add to each search result:
```json
"citation_hint": "Smith et al. (2023). Title. Biochemical Journal. https://doi.org/10.1042/..."
```
AI tools that want to cite sources need this. Without it, even if they use our content, attribution breaks down.

**3. Retraction + correction status as a first-class field**
CrossRef has a free API for retraction metadata. Flag each article at enrichment time:
```json
"retraction_status": "active" | "retracted" | "corrected"
"retraction_date": "2024-03-15"
```
Then refuse to serve or visibly flag retracted content. No other AI content pipeline does this reliably today — strong trust differentiator.

---

## Priority Order

1. **Retraction check** — data integrity risk, easy to add at enrichment time
2. **MCP server** — unlocks actual AI agent adoption
3. **Citation hint field** — attribution without friction
4. **Usage telemetry** — needed to prove AI-era impact to publishers
5. **Trust signal fields** — longer-term differentiator

---

## Discoverability: Retrieval Experiment Results

### Failure modes (why articles are invisible — or worse, wrongly surfaced)

**Primary failure modes:**

1. **Terminology mismatch** — query uses different words than the article ("parasite immune evasion" vs "T. annulata infection"). Root cause: embedding space doesn't bridge synonym gaps; a specific failure variant is OOV/rare token fragmentation — new gene names or coined terminology (e.g. "CHCHD2") get split into meaningless subword tokens with weak embeddings. Different cause, different fix (character-level or hybrid encoding vs. synonym expansion).

2. **Visual content** — key findings live in figures/tables. The failure isn't just "text-only search is blind." Even when captions are indexed, the relationship between a figure and its claim is lost — the caption says "Figure 3" but the conclusion "drug X shows 3x potency" lives two pages away in the discussion. The figure and its scientific meaning are structurally disconnected in any text representation.

3. **Relationship queries** — answer requires connecting entities across a relationship ("what inhibits gene X in disease Y"). Single-document retrieval can't do this. Extends further to multi-document reasoning: many scientific questions require synthesising across 3–5 papers where paper A establishes a mechanism, paper B shows an inhibitor, and paper C demonstrates the in-vivo context. The answer literally doesn't exist in any one chunk.

4. **Buried findings** — specific finding is inside a 2000-word section. The problem isn't just that section embeddings average over many concepts — it's that the query vector has to compete with a section embedding that contains many other concepts. Even a perfect retrieval model can rank a chunk lower because the signal-to-noise ratio in the embedding is poor.

5. **Negation blindness** — embedding models are notoriously bad at encoding negation. "Compound X does not inhibit pathway Y" generates an embedding very similar to "compound X inhibits pathway Y." A query for "what inhibits pathway Y" will retrieve the first paper — and the AI will confabulate the wrong conclusion from it. This is arguably more dangerous than invisibility: it produces false positives with high confidence.

6. **Temporal drift** — a 2019 paper with the right terminology will rank highly even if a 2023 paper has completely overturned its findings. No mechanism in standard RAG flags "this finding has been superseded." For biomedical literature especially, this is a serious failure mode — you're not just missing the new paper, you're actively surfacing the old one.

7. **Confidence collapse** — "Drug X may have potential implications for..." ranks the same as "Drug X definitively inhibits...". Embeddings don't encode epistemic strength. A speculative sentence in a limitations section and a core finding in the results section are treated identically. In scientific literature where hedging is pervasive, this systematically overstates weak evidence.

**Secondary failure modes:**

8. **Index bias / abstract over-representation** — most systems over-index on abstracts and titles because they're clean and short. A paper's most important contribution is often a subordinate clause in the methods or a table footnote — which gets chunked, embedded, and buried under abstract-level matches.

9. **Discourse blindness** — an embedding can't distinguish whether a sentence is making a claim, providing background, or describing prior work being refuted. "Previous studies suggested X" and "we demonstrate X" generate similar embeddings. A paper that argues against a hypothesis can be retrieved as evidence for it.

### Experiment results (html_scrape vs enriched vs entity_enriched, 12 queries)

**Rank-1 wins: HTML=5/12, Enriched=6/12, Entity=1/12**

| Query type | HTML | Enriched | Delta | Verdict |
|---|---|---|---|---|
| Figure 1 in agent-based model | 0.8916 | 0.6655 | **+25.4%** | Clear enrichment win |
| EV charging results tables | 0.9437 | 0.8176 | **+13.4%** | Clear enrichment win |
| YY1 and ANXA3 nitration | 0.5663 | 0.4997 | +11.8% | Enrichment wins |
| Agile autonomy paradox | 0.5475 | 0.4835 | +11.7% | Enrichment wins |
| Methodology query | 1.1422 | 1.0274 | +10.1% | Enrichment wins (different article) |
| TM5614 leukemia trial | 0.5626 | 0.5368 | +4.6% | Marginal enrichment win |
| Dark personality traits | 0.4979 | 0.4849 | +2.6% | Marginal enrichment win |
| ALK translocation FISH | 0.6966 | 0.7851 | **-12.7%** | Enrichment hurts |
| PAI-1 inhibition | 0.6854 | 0.7183 | -4.8% | Enrichment hurts (wrong article) |
| EV optimization | 0.6032 | 0.6248 | -3.6% | Enrichment hurts |
| Social network energy | 0.8910 | 0.9165 | -2.9% | Enrichment hurts |
| Main conclusions | 1.2442 | 1.2743 | -2.4% | Marginal regression |

**Key findings:**
- Enrichment clearly wins only for figure/table content (failure mode 2) — this is its unique value
- Entity tags embedded in text hurt more than they help — entity enrichment wins only 1/12
- For exact biomedical terms (ALK, PAI-1), raw text is sometimes a stronger signal than enriched text
- The AI prefix uses ~150-200 chars of the 1500-char budget, diluting the content signal for precise queries

### Why enrichment sometimes hurts
The AI prefix adds context but its vocabulary may not align with the query's exact terminology. For highly specific biomedical queries, the raw term in the text is the strongest signal — the prefix dilutes it.

---

## Input Format: XML vs PDF

**Conclusion: XML is strictly better. PDF is a fallback for publisher coverage, not an upgrade.**

The "ready to print" PDF is the rendered output of the XML. Switching to PDF means throwing away structure and trying to reconstruct it.

| Content type | XML gives you | PDF gives you |
|---|---|---|
| Sections | Explicit `<ce:section>` tags | Inferred from font size/bold heuristics |
| Figure captions | Discrete tagged element | Text near image region (may be wrong page) |
| Tables | Structured rows/columns | Fragmented X/Y positioned text |
| Equations | MathML | Rendered glyphs, often garbage |
| Metadata (DOI, authors) | Explicit fields | First page header, needs regex |
| References | Structured per-citation | Text blob, needs re-parsing |

**Intake strategy by publisher type:**
```
Elsevier, Springer, Wiley  →  XML (TDM APIs exist)
Smaller publishers          →  PDF (only option, lower chunk quality)
Web-only content            →  HTML scrape (baseline)
```

Track input format as a metadata field (`input_format: "xml" | "pdf" | "html"`) — it affects how much to trust the enriched output.

---

## Three Approaches to Discoverability — Critical Analysis

### Core question: which failure modes does each approach fix?

| | 1. Terminology | 2. Visual content | 3. Relationship / multi-doc | 4. Buried findings | 5. Negation | 6. Temporal drift | 7. Confidence collapse | 8. Index bias | 9. Discourse blindness |
|---|---|---|---|---|---|---|---|---|---|
| **Current (chunks + NER)** | Partial | Partial | None | None | None | None | None | None | None |
| **Knowledge Graph** | Good | None | Strong (single-doc); weak (multi-doc) | Only if claim-level | Partial (if relations typed) | Partial (with timestamps) | None | None | Partial (if node type encodes claim vs background) |
| **Multimodal embeddings** | Partial | Strong | None | None | None | None | None | None | None |
| **Hybrid BM25 + vector** | Strong (exact terms) | None | None | None | None | None | None | Partial | None |
| **Claim-level chunking** | None | None | None | Strong | None | None | None | Strong | Partial |
| **Metadata filters (date, retraction)** | None | None | None | None | None | Strong | None | None | None |
| **Epistemic tagging** | None | None | None | None | None | None | Strong | None | Strong |

---

### Approach 1 — XML → Chunks + AI Summaries + NER (current)

**Fixes:** Failure modes 1 (partial) and 2 (partial via summaries)
**Doesn't fix:** Failure modes 3 and 4

**Pros:** Works now. Lowest query latency. Interpretable results.

**Cons:** Hits a ceiling at ~6/12 vs 5/12 baseline. Not a step-change. No cross-article reasoning.

**Discoverability delta: Moderate.** Makes figure-invisible articles visible. Limited on relationship and buried-finding queries.

---

### Approach 2 — Knowledge Graph (concepts, facts, entities, topics, sections)

**Can it be built? Yes — at three quality levels:**

| KG type | What it captures | Build difficulty | Retrieval power |
|---|---|---|---|
| Entity co-occurrence | METTL3 and m6A appear in same article | Low | Low |
| Entity-relationship | METTL3 **upregulates** m6A **in** T. annulata | High | High |
| Claim-level facts | "METTL3 expression is 3-fold higher at 48h in infected cells" | Very high | Very high |

**Fixes:** Failure mode 3 (relationship queries) directly. Cross-article entity clustering — an article becomes discoverable because related articles are discoverable.

**Doesn't fix:** Failure mode 2 (figures), failure mode 4 (buried findings unless claim-level).

**Pros:**
- Enables query types impossible with vector search ("what papers study gene X in disease Y")
- Cross-article clustering surfaces related articles together
- Relationships once extracted are queryable forever

**Cons:**
- Relationship extraction accuracy ~60-70% on scientific text — wrong edges hurt precision
- Current NER has entity type errors (cell lines as organisms, etc.) — noisy NER = noisy graph
- Query interface changes — needs NL-to-Cypher routing layer
- High build and maintenance cost

**Discoverability delta: High for relationship queries, zero for visual content.** Real improvement but narrow — serves structured biomedical queries well. Must run alongside vector search, not instead of it.

**Build prerequisite: clean entity extraction first.** Don't build the KG until NER quality is higher.

---

### Approach 3 — Multimodal Embedding Model

**Two architectures:**

**Option A — Figure-level (CLIP / Voyage Multimodal)**
Extract each figure as an image, embed in shared text-image space. Text query retrieves matching figures natively.

**Option B — Page-level (ColPali, 2024)**
Render each document page as an image, embed the whole page. No parsing required — handles multi-column layouts, equations, tables, figures natively because it sees the page as a human does. Works on PDF, XML, HTML equally (no parsing = format-agnostic).

**Fixes:** Failure mode 2 (visual content) fully and natively — much better than AI-generated text summaries because the model understands visual content directly.

**Doesn't fix:** Failure mode 3 (relationships), failure mode 4 (buried findings).

**Pros:**
- Largest single delta for currently-invisible figure content
- ColPali: no parsing required — solves publisher coverage problem simultaneously (any format works)
- No extraction errors — the model sees what a human sees

**Cons:**
- Higher query-time latency (image embeddings are larger)
- ColPali requires GPU for reasonable speed
- Cross-modal retrieval (text query → image result) still has a gap vs. same-modal
- Not yet mainstream in RAG tooling

**Discoverability delta: Potentially the largest single improvement for figure-heavy scientific content.**

**Implementation constraints (assessed 2026-03-29 after Phases 1–6 complete):**

1. **No image files available (hard blocker).** XML contains `<ce:link locator="fx1"/>` references but actual image binaries (PNG/TIFF) are not in the local corpus. Must be fetched from Elsevier's TDM API or article supplementary packages. Without images, there is nothing to embed.

2. **Embedding model is text-only.** Current pipeline uses `text-embedding-3-small` which cannot embed images. Multimodal alternatives:
   - **CLIP / OpenCLIP** — free, good for natural images, weaker on scientific charts/diagrams
   - **Voyage Multimodal** — API-based, better on document content
   - **ColPali** — page-level embeddings, strong on scientific content but requires GPU

3. **ChromaDB supports image embeddings** — no DB migration needed. Can use a separate collection or shared multimodal embedding space.

4. **Cross-modal retrieval gap** — text query → image result is weaker than text → text. A hybrid approach (text summary embedding + image embedding, fused) would be more robust than image-only.

5. **Embedding size/cost** — image embeddings are 4–10x larger than text embeddings. Storage and query latency increase proportionally.

6. **Current mitigation in place.** Phase 6 claim-extracting summaries + Phase 5 cross-linking partially address visual content blindness through text — figures are now retrievable via their scientific claims, and linked to the prose that interprets them. Multimodal would add native visual understanding on top of this, not replace it.

---

### Recommended architecture: three retrieval paths with a router

```
Query comes in
    ↓
Intent detection
    ├── Relationship query?   → KG traversal
    ├── Visual/figure query?  → Multimodal vector search
    └── Everything else?      → Text vector search (current)
```

**If forced to pick one next step: Multimodal embeddings (ColPali)**
- Figures are the biggest current gap
- Solves publisher coverage (format-agnostic)
- Technology is mature enough in 2025
- Higher effort-to-impact ratio than KG at this stage

**KG is second** — but only after NER quality improves, because noisy entities = noisy graph = retrieval regressions.

---

## Validation Against Full Failure Mode Taxonomy (27 modes, 3 buckets)

Source document: `AI_Article_Discoverability_Failure_Modes.docx`

**Legend: ✓ Addressed | ~ Partial | ✗ Not addressed**

---

### Bucket 1 — Corpus & Access (5 modes)

| Code | Failure Mode | Status | Notes |
|---|---|---|---|
| G1 | Paywall / access gap | **✓** | License service with ALLOWED/SNIPPET_ONLY/NO_ACCESS tiers per institution. Full-text ingested and access-controlled. |
| G2 | Grey literature exclusion | **✗** | Elsevier XML only. Conference abstracts, theses, regulatory filings not ingested. |
| G3 | Indexing lag | **✗** | Static pipeline. No incremental update mechanism. |
| F3 | Retraction blindness | **✗** | No CrossRef or Retraction Watch check. Retracted papers serve with full confidence. |
| F4 | Correction / erratum blindness | **✗** | No erratum propagation. Pipeline always serves the original version. |

**Score: 1/5**

---

### Bucket 2 — Matching & Architecture (15 modes)

| Code | Failure Mode | Status | Notes |
|---|---|---|---|
| A1 | Terminology mismatch | **~** | AI prefix adds context vocabulary. Helps but doesn't bridge arbitrary synonym gaps. |
| A2 | Synonym / trade name gap | **~** | Ontology IDs (NCBI Gene, MeSH, ChEBI) normalise some synonyms. Brand→INN gap not handled. No query-side expansion. |
| A3 | OOV / rare token fragmentation | **✗** | No character-level or hybrid encoding. New gene names silently destroyed by tokeniser. |
| A4 | Language / script barrier | **✗** | English-only corpus and pipeline. |
| B1 | Buried findings | **✗** | Section-level chunks. One chunk per section. A 2000-word results section is a single embedding. |
| B2 | Abstract over-weighting | **✗** | No weighting distinction between abstract and results chunks. |
| B3 | Cross-chunk dependency | **✗** | No chunk linking. A finding split across two adjacent sections is permanently split. |
| B4 | Granularity mismatch | **~** | Section-based chunking is better than fixed-size, but still coarse (~7 chunks per paper). |
| C4 | Relationship queries | **✗** | No KG, no graph traversal. |
| C5a | Implicit knowledge gap (as miss) | **✗** | No mechanism to surface or follow cited prior work. |
| E1 | Visual content blindness | **~** | AI-generated summaries from captions help with topicality. Doesn't natively read visual data inside figures (numbers in charts, curve shapes). |
| E2 | Figure–claim decoupling | **✗** | Figure chunks have `section=None`. The corresponding claim in Discussion is a separate unlinked chunk. |
| E3 | Supplementary data blindness | **✗** | Pipeline processes main XML only. Supplementary tables and extended methods not ingested. |
| D3 | Citation-chasing blindness | **✗** | Citation graph exists but is display-only. Not traversed during retrieval. |
| D1 | Multi-doc reasoning gap | **✗** | Single-document retrieval architecture. No cross-paper inference. |

**Score: 0 fully addressed, 4 partial / 15**

---

### Bucket 3 — Retrieval & Misread (10 modes)

| Code | Failure Mode | Status | Notes |
|---|---|---|---|
| C1 | Negation blindness | **✗** | No negation handling anywhere in pipeline or retrieval. |
| C2 | Confidence collapse | **✗** | No epistemic strength encoding. Hedged findings and confirmed results are identical in embedding space. |
| C3 | Discourse blindness | **~** | `section` field stored (introduction, methods, results, discussion, conclusion) and in ChromaDB — but **not used as a filter or reranking signal**. Infrastructure present, capability not activated. |
| C6 | Causal direction loss | **✗** | No directional relationship encoding. |
| D2 | Contradictory evidence | **✗** | No conflict detection between retrieved chunks. |
| F1 | Temporal drift | **~** | `publication_date` stored in chunk metadata. Not used in ranking or as a recency boost. Infrastructure present, not activated. |
| F2 | Preprint vs published divergence | **✗** | No version tracking or deduplication between preprint and final. |
| G4 | Structural metadata loss | **~** | Section type stored in ChromaDB. Same as C3 — present but not used at query time. |
| C5b | Implicit knowledge gap (as misread) | **✗** | No mechanism to flag that a finding depends on unindexed prior work. |
| B2b | Abstract over-weighting (as filter) | **✗** | No context window slot management by section type. |

**Score: 0 fully addressed, 3 partial (infrastructure only) / 10**

---

### Overall summary

| Bucket | Fully addressed | Partial | Not addressed |
|---|---|---|---|
| Bucket 1 — Corpus & access | 1 | 0 | 4 |
| Bucket 2 — Matching & architecture | 0 | 4 | 11 |
| Bucket 3 — Retrieval & misread | 0 | 3 (infrastructure only) | 7 |
| **Total** | **1 / 27** | **7 / 27** | **19 / 27** |

---

### Key observations

**The pipeline primarily solves Bucket 1 (access), not discoverability.**
The license service, institutional access tiers, and full-text ingestion are real. But they solve *availability*, not *findability*. An article can be in the corpus and still be invisible to a relevant query — which is what Buckets 2 and 3 are about.

**Bucket 3 is completely unaddressed — and it's the most dangerous bucket.**
Negation blindness, confidence collapse, discourse blindness don't produce empty results. They produce wrong answers that look correct. No Bucket 3 mode has any mitigation in the current pipeline.

**Two quick wins that require no new pipeline work — metadata already exists, just not activated:**
- C3 / G4: Section type is in ChromaDB — use it as a query filter or reranking signal immediately
- F1: `publication_date` is in chunk metadata — add a recency boost to counteract temporal drift

---

## Bucket 2 Improvement Plan — Vector DB Approach

### What vector DB can and cannot fix

| Mode                        | Fixable via vector DB?                            |
| --------------------------- | ------------------------------------------------- |
| A1 Terminology mismatch     | Yes — query expansion                             |
| A2 Synonym gap              | Yes — query expansion + ontology                  |
| A3 OOV fragmentation        | Yes — BM25 hybrid                                 |
| A4 Language barrier         | No — out of scope                                 |
| B1 Buried findings          | Yes — finer chunking                              |
| B2 Abstract over-weighting  | Yes — section metadata filter (already in DB)     |
| B3 Cross-chunk dependency   | Yes — overlapping chunks                          |
| B4 Granularity mismatch     | Yes — chunking overhaul                           |
| C4 Relationship queries     | No — needs KG                                     |
| C5a Implicit knowledge gap  | Partial — query expansion helps                   |
| E1 Visual content blindness | Partial — better summaries; full fix = multimodal |
| E2 Figure–claim decoupling  | Yes — enrichment-time cross-linking               |
| E3 Supplementary data       | No — corpus access problem                        |
| D3 Citation-chasing         | Partial — corpus expansion helps                  |
| D1 Multi-doc reasoning      | Partial — multi-query retrieval helps             |

**10 of 15 Bucket 2 modes addressable through vector DB changes alone.**

---

### Critical finding: the truncation problem

Current embed limit is **1,500 chars**. Chunk size analysis across the corpus:

- `ESR-102126`: avg text chunk = **31,065 chars** → only ~5% of each chunk is ever embedded
- `BJ_100828`: avg text chunk = **8,345 chars** → ~18% embedded
- Overall: min=212, max=59,673, avg=6,808 chars per chunk

For large articles, the content isn't "buried" — it literally doesn't exist in the index. This makes Phase 1 (chunking overhaul) the highest-priority intervention by far.

---

### Phase 1 — Chunking overhaul *(do first)*

**Addresses: B1, B3, B4 — and fixes the truncation crisis**

- Split sections into paragraphs at XML `<ce:para>` boundaries (~400–600 char target)
- Add 1-sentence overlap between consecutive paragraphs (fixes B3)
- Keep `parent_section` as metadata for context retrieval
- Result: `ESR-102126` goes from 5 truncated chunks to ~150 fully-embedded paragraph chunks

```
chunk_id: ESR-102126::results::para_3
text: "[AI prefix] ...paragraph about EV charging optimisation metrics..."
metadata: { section: "results", parent_section_id: "...", paragraph_index: 3, doi: ..., publication_date: ... }
```

---

### Phase 2 — Activate section metadata as a filter *(zero new pipeline work)*

**Addresses: B2, C3, G4, F1**

Already in ChromaDB, just not queried against:
- **Section-type reranking**: boost `results` and `methods` chunks over `introduction` and `other` for factual queries
- **Recency boost**: time-decay multiplier on distance score using `publication_date`

---

### Phase 3 — Hybrid BM25 + dense search

**Addresses: A1, A2, A3**

Experiment showed ALK (-12.7%) and PAI-1 (-4.8%) get worse with enrichment because the AI prefix dilutes exact term signal. BM25 handles exact biomedical terms regardless of embedding tokenisation.

- Add `rank_bm25` Python library as a second index over same documents
- Combine scores using Reciprocal Rank Fusion: `score = 1/(k + rank_bm25) + 1/(k + rank_vector)` where k=60
- Or migrate to Qdrant/Weaviate which have native hybrid search

---

### Phase 4 — Query-time expansion (HyDE)

**Addresses: A1, A2, C5a (partial)**

No pipeline or DB changes. Ask the LLM to generate a hypothetical answer paragraph, embed that instead of the raw query. The hypothetical answer uses corpus vocabulary — "parasite immune evasion" → generates text mentioning "T. annulata host defence subversion" → much closer to actual chunks.

Alternative: multi-query (3 terminology variants per query, retrieve and deduplicate). Simpler to implement, slightly weaker.

---

### Phase 5 — Figure-claim cross-linking

**Addresses: E2**

At enrichment time in `pipeline.py`:
- Scan text sections for "As shown in Figure X", "Figure X demonstrates" patterns
- Write `figure_refs: ["fig1", "fig3"]` onto the text chunk metadata
- Write `cited_in_sections: ["results", "discussion"]` onto the figure chunk metadata
- At query time: when a text chunk is retrieved, also surface its linked figure chunks

---

### Phase 6 — Claim-extracting figure/table summaries

**Addresses: E1 (deeper)**

Change summary prompt from describing the figure to extracting the finding:

- Current: "Figure 1 illustrates the proposed mechanisms through which PAI-1 inhibitors exert anti-tumor effects..."
- Target: "Key finding: PAI-1 inhibition via TM5614 suppresses tumour growth through angiogenesis inhibition, macrophage reprogramming, and PD-L1 downregulation. [Figure 1 shows the mechanistic diagram and trial rationale.]"

---

### Prioritised implementation order

| Phase | Modes addressed | Effort | Impact |
|---|---|---|---|
| 1. Chunking overhaul | B1, B3, B4 + truncation | Medium | **Critical** |
| 2. Activate section metadata | B2, C3, G4, F1 | Low (no rebuild) | High |
| 3. Hybrid BM25 | A1, A2, A3 | Medium | High |
| 4. Query expansion (HyDE) | A1, A2, C5a | Low | Medium |
| 5. Figure-claim linking | E2 | Medium | Medium |
| 6. Claim-extracting summaries | E1 | Low (prompt change) | Medium |

**After all 6 phases: 10 of 15 Bucket 2 modes addressed or significantly improved.**

Remaining 5 (C4, D1, A4, E3, D3) require KG, multimodal embeddings, corpus expansion, or are out of scope.

---

## KG on Top of the Vector DB Foundation

### Does completing the vector DB phases make KG better?

Yes — significantly. The KG's quality directly depends on what the vector DB phases produce.

**Phase 1 (paragraph chunking) feeds the KG better source material.**
Entity extraction (NER) currently runs on section-level chunks — a 31,000-char results section produces one entity list that mixes entities from across the whole section with no positional context. With paragraph-level chunks, each entity is extracted from a tighter 400-600 char window. Entities are more accurately typed, co-occurrences are more meaningful (two entities in the same paragraph are more likely to be in a direct relationship than two entities in the same 5,000-word section).

**Phase 5 (figure-claim linking) gives the KG explicit claim anchors.**
The "cited_in_sections" metadata created in Phase 5 tells you exactly which prose section draws a conclusion from which figure. That's a claim-evidence link — precisely the kind of relationship a KG needs to be populated with. Instead of extracting triples blindly from all text, you can prioritise triple extraction from the claim-bearing sentences identified by the figure-claim linker.

**Phase 3 (BM25 hybrid) validates entity resolution.**
After building the KG, entity queries need to be reliably retrievable. BM25 ensures that exact entity names (METTL3, TM5614, ALK) are always reachable — which means the KG node lookup never goes dark due to OOV tokenisation.

---

### What the KG adds that the vector phases cannot

After all 6 vector phases, 5 Bucket 2 modes remain unaddressed. The KG covers 3 of them directly:

| Mode                    | Why vector can't fix it                                      | How KG fixes it                                                             |
| ----------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------- |
| C4 Relationship queries | Semantic similarity can't encode "X inhibits Y in disease Z" | Graph traversal: (X)-[INHIBITS]->(Y)<-[ASSOCIATED_WITH]-(Z)                 |
| D1 Multi-doc reasoning  | No architecture for cross-paper synthesis                    | Entity nodes link papers that share entities; traversal assembles the chain |
| D3 Citation-chasing     | RAG doesn't follow references                                | Citation edges in graph are traversable — one hop to the referenced paper   |

**The KG also adds value to Bucket 3** — specifically the modes that are hardest to fix with embeddings alone:
- **C3 Discourse blindness**: KG nodes can be typed as Claim, Background, Refutation, Limitation. A node typed "Claim" in a Results section carries more epistemic weight than a node typed "Background" in Introduction. This is structural metadata the graph preserves that embeddings lose.
- **D2 Contradictory evidence**: If two corpus papers make opposing claims about the same entity pair, the KG can detect the conflict explicitly — same subject, same object, contradictory predicates. The vector DB has no way to surface this.
- **C2 Confidence collapse**: KG nodes can carry an epistemic strength tag (confirmed finding vs. preliminary vs. speculative) extracted at enrichment time.

---

### What the KG build looks like after the vector phases

By the time Phases 1–6 are complete, you have:

- Paragraph-level chunks with accurate entity lists (good NER input quality)
- Figure-claim links identifying which sentences are claim-bearing
- Section type metadata identifying Results vs Limitations vs Introduction

The KG build becomes:

**Step 1 — Entity nodes (already partially done via NER)**
Each unique ontology-resolved entity becomes a node: METTL3 (NCBI Gene:56339), TM5614 (Drug), T. annulata (Taxonomy:5874). Phase 1 improves resolution accuracy significantly.

**Step 2 — Relationship extraction (the new hard step)**
Run triple extraction only on claim-bearing sentences (identified by Phase 5 figure-claim linking + section=results filter). "METTL3 expression is upregulated in T. annulata-infected cells" → (METTL3)-[UPREGULATED_IN]->(T. annulata infection). Scoping to claim-bearing sentences reduces the surface area and improves precision.

**Step 3 — Article nodes + citation edges**
Already in `citation_graph.json`. Connect entity nodes to the article nodes that assert them.

**Step 4 — Cross-paper entity clustering**
Two papers that both have METTL3 as a node are now linked. Querying for METTL3 returns both papers, ranked by relationship type and recency.

---

### Honest assessment: does it all fit together?

Yes — and the architecture is cleaner than building KG first:

```
Query
  ↓
Intent classification (entity query? relationship? visual? general?)
  ├── Entity/relationship → KG traversal + vector rerank
  ├── Visual/figure      → Multimodal search (future)
  └── General            → Hybrid BM25 + vector (Phase 3)
        ↓
Section-type reranking (Phase 2)
        ↓
Figure-claim expansion (Phase 5)
        ↓
Results
```

The vector phases give you a working, measurably better system immediately. The KG adds on top without replacing anything — it's an additional retrieval path, not a rewrite. And because the vector phases clean up chunking and entity extraction quality, the KG is built on a more reliable foundation than if you built it now.
