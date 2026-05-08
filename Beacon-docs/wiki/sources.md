# Source Documents

All files in `Beacon-docs/` (non-wiki). These are the originals — read them for deep context. The wiki pages synthesize the current implementation state; these hold the reasoning behind it.

---

## Business & Strategy

| File | What it contains |
|---|---|
| [Approach.md](../Approach.md) | Business case: Beacon as a licensed AI content gateway between publisher XML and AI consumption, enforcing institutional licensing at retrieval |
| [Opportunity assessment.md](../Opportunity%20assessment.md) | Early POC framing: target customer (scientific publishers), business model (bundle into TNQ services), competitive landscape (Cashmere.io) |
| [Phase1 discovery.md](../Phase1%20discovery.md) | Discovery research: 7 problems publishers face with AI — trust erosion, bypassed infrastructure, revenue model threat, citation loss, provenance, retraction blindness, content not AI-ready |
| [Research.md](../Research.md) | Research notes from Wiley AI webinar — same 7 publisher problems, sourced from webinar transcript (`Wiley Knowledge.md`) |
| [Wiley Knowledge.md](../Wiley%20Knowledge.md) | Transcript excerpt from a Wiley AI webinar on publisher trust issues with AI tools |
| [Brainstorming.md](../Brainstorming.md) | Design exploration of two modules: Discoverability (built) and Governance (license-aware gateway with RAG vs READ_RAG_SOURCE access tiers) |

---

## Technical Reference

| File | What it contains |
|---|---|
| [Methodology.md](../Methodology.md) | Deep reference for every technique used — XML parsing, chunking, prefixes, NER, BM25, HyDE, reranking — with "why we chose this" explanations |
| [Semantic enrichment.md](../Semantic%20enrichment.md) | Complete pipeline reference table: all 8 steps with failure modes handled per step. More detailed than wiki/pipeline.md |
| [Pipeline comparison.md](../Pipeline%20comparison.md) | Side-by-side comparison of end-to-end (`pipeline.py`) vs staged enrichment (`stage_copyedit` → review → `stage_mastercopy`) |
| [jsonld_explainer.md](../jsonld_explainer.md) | What JSON-LD is and why it matters: makes chunk data universally interpretable via @context/@id, enabling external knowledge graph traversal (NCBI, ChEBI, Wikidata) |
| [Estimated cost.md](../Estimated%20cost.md) | API cost model: ~$0.014/article for indexing (gpt-4o-mini + text-embedding-3-small), cost per query for search + synthesis |

---

## POC History

| File | What it contains |
|---|---|
| [POC.md](../POC.md) | Early workflow walkthrough — step-by-step explanation of XML parsing and enrichment, written during initial build |
| [POC results.md](../POC%20results.md) | Full original 2-article experiment results (raw/metadata/enriched collections); honest caveats about why raw won; the reframe toward HTML-scrape as correct baseline |

---

## Communication

| File | What it contains |
|---|---|
| [Semantic Enrichment One Pager.md](../Semantic%20Enrichment%20One%20Pager.md) | Plain-language pipeline summary for non-technical audiences — 7 steps without jargon |
| [Knowledge.md](../Knowledge.md) | Demo prep notes: what to say, what each file does, talking points ("read this the morning of") |

---

## Phase Implementation Logs

Detailed notes on each implementation phase — what was built, files changed, design decisions made.

| File | Phase |
|---|---|
| [Phase1 implementation.md](../Phase1%20implementation.md) | Paragraph chunking, small paragraph merging, cross-chunk overlap |
| [Phase2 implementation.md](../Phase2%20implementation.md) | Section reranking + recency boost |
| [Phase3 implementation.md](../Phase3%20implementation.md) | Hybrid BM25 + vector search with RRF |
| [Phase4 implementation.md](../Phase4%20implementation.md) | HyDE query expansion |
| [Phase5 implementation.md](../Phase5%20implementation.md) | Figure/text cross-linking (bidirectional) |
| [Phase6 implementation.md](../Phase6%20implementation.md) | Claim-extracting figure/table summaries |
