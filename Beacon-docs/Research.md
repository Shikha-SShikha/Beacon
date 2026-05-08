# Research Notes — Entity Extraction & Linking for Scientific Articles

## Wiley AI Knowledge Nexus — Webinar Insights

Source: Transcribed from `2026-02-18 20-33-25.mkv` (Wiley webinar, full transcript in `Wiley Knowledge.txt`)

### Problems Publishers Face with AI Tools

1. **Trust erosion** — AI usage among researchers jumped from 57% to 84% (2024→2025), but confidence in those tools has *decreased*. More usage, less trust.
2. **Bypassed infrastructure** — Researchers are using ChatGPT, Claude, etc. to access research content without ever visiting publisher websites. The human-centric pipeline (Google → publisher site → content) is being circumvented by agentic AI tools.
3. **Revenue model threat** — Publisher business strategies are built around a human-centric model. If researchers never visit your site, your subscription/access model breaks down.
4. **Loss of citability and impact tracking** — When AI tools synthesize from hundreds of papers, how does a single paper get cited? How do you measure impact? Traditional metrics (downloads, citations) stop working.
5. **Provenance and attribution** — AI tools can surface content without linking back to the source. No way to verify where information came from.
6. **Retraction/correction blindness** — AI tools don't know if a paper has been retracted or corrected. They serve stale or discredited content with no flag.
7. **Content not AI-ready** — Even high-quality published content isn't in a format AI tools can efficiently retrieve. It needs enrichment — chunking, vectorization, entity tagging, metadata embedding.
8. **Open access complicates licensing** — If content is freely available, does the licensing model collapse? (Wiley argues no — enrichment still has value.)
9. **Small publishers left behind** — Smaller publishers lack dedicated licensing infrastructure to negotiate directly with AI companies.
10. **Speed of change** — "Even if you're two or three months behind, you may have already missed your chance." LLM training deals were hot in 2023-2024, already cooling.

### Key Learnings from Wiley Webinar

1. **LLM training deals are a one-time play, RAG is the long-term game.** Training deal demand is waning. The recurring revenue is in domain-specific RAG content via subscriptions.
2. **Content enrichment is the real value-add.** Even for open-access content, the work of chunking, vectorizing, and enriching metadata is what makes content licenseable.
3. **Wiley does chunking + vectorization but didn't mention entity extraction.** They embed "signifiers within the metadata and the XML" but the transcript never specifically mentions NER or ontology linking — potential gap and TNQ's opportunity to differentiate.
4. **Aggregation creates leverage.** Wiley bundles content from multiple publishers into one offering for AI companies. Broader corpus = stronger negotiating position. TNQ already processes content for multiple publishers — same advantage.
5. **DOI link-back is non-negotiable.** Publishers insist that AI-surfaced content must link back to the original article.
6. **Corporate R&D is the primary buyer** for domain-specific RAG content right now.
7. **"AI tools should be a pathway to your content, not a replacement for it."** — Wiley's philosophical frame.
8. **First-mover advantage is real and fleeting.**

---

## Why Scientific Content Isn't AI-Ready — Evidence

### Entity Ambiguity Kills Retrieval Precision

Biomedical literature is riddled with abbreviations that have multiple meanings:
- **"CLD"** could mean "Cholesterol-lowering Drug," "Chronic Liver Disease," "Congenital Lung Disease," or "Chronic Lung Disease"
- **"EGFR"** could be the gene, the protein, or a drug class (EGFR inhibitor)
- **"ER"** — estrogen receptor? endoplasmic reticulum? emergency room?

Without entity tagging and ontology linking, retrieval systems return noisy results — low precision and low recall.

### CLEAR Study — Hard Numbers

Source: [Clinical Entity Augmented Retrieval (npj Digital Medicine, 2025)](https://www.nature.com/articles/s41746-024-01377-1)

| Approach | F1 Score |
|----------|----------|
| Full-note (no retrieval) | 0.79 |
| Embedding-based RAG | 0.86 |
| **Entity-augmented retrieval (CLEAR)** | **0.90** |

- Removing NER from the pipeline dropped F1 by **0.11**
- Entity-based retrieval achieved **>70% reduction in token usage and inference time**
- Adding ontology linking (UMLS) pushed sensitivity to **99-100%**

### JATS XML — Structured but Not Semantic

Source: [From Valid XML to Valuable XML (JATS-Con 2025)](https://www.ncbi.nlm.nih.gov/books/NBK611679/)

Valid XML doesn't mean functional quality. NISO-JATS was not designed to aid text mining — text appears at different levels and in various structures. JATS gives you structure (sections, references, metadata) but the text content within those tags is unstructured natural language.

### Knowledge Graphs Built from NER Improve Retrieval

- Knowledge graph + RAG showed **71% improvement in LLaMA-2 performance** when augmented with biomedical entity context (SPOKE knowledge engine)
- Dual-pathway KG-RAG reduced hallucinations by **18%** in biomedical QA

### PubTator — Real-World Precedent

NCBI's PubTator adds NER annotations to PubMed articles — tagging genes, diseases, chemicals, mutations, species, and cell lines. It exists precisely because raw PubMed articles aren't AI-ready.

---

## IBM Docling — PDF Conversion Tool

Source: [GitHub](https://github.com/docling-project/docling) | [IBM Research Blog](https://research.ibm.com/blog/docling-generative-AI)

IBM's open-source toolkit that converts PDFs into structured Markdown/JSON using AI models for layout analysis (DocLayNet) and table recognition (TableFormer). 10k+ GitHub stars.

### Docling vs. TNQ's Approach

Docling solves a different problem — it takes unstructured PDFs and tries to recover structure. TNQ already has JATS XML.

| Layer | PDF path | TNQ path |
|-------|----------|----------|
| **Raw content** | PDF (images, layout) | JATS XML (clean, tagged) |
| **Structural extraction** | Docling needed here | Already done |
| **Entity extraction + NER** | Still needed | Still needed |
| **Ontology linking** | Still needed | Still needed |

Docling could be complementary — for publishers with legacy PDF-only content, it could serve as an ingestion step before entity enrichment.

---

## How AI Tools Consume Academic Content

### Three Distinct Modes

#### 1. LLM Training — Scrape Everything, Strip to Plain Text
- AI companies scrape publisher websites, PubMed Central, arXiv
- Strip HTML/XML/PDF down to raw text, tokenize into subwords
- Don't care about structure at training time — just want massive text volume
- Triggered lawsuits — one case resulted in a $1.5 billion settlement
- **Format consumed: plain text (scraped)**

#### 2. RAG (Retrieval) — Structure Matters Enormously
- Content gets chunked, vectorized, stored in vector databases
- Clean structured content (JATS XML) produces far better chunks than scraped PDFs
- Plain text from PDF scraping loses table structure, section hierarchy, metadata
- **Format consumed: chunked text/markdown, quality depends on source format**

#### 3. Licensed Content Pipelines — The Emerging Model
- Publishers proactively prepare content: chunk, vectorize, enrich with entity tags
- Deliver via API or data feed to AI companies
- **Format consumed: enriched structured data (JSON, enriched XML, markdown with metadata)**

### Where TNQ Fits

| Consumption mode | Who controls it? | Publisher gets paid? | Quality? |
|-----------------|-------------------|---------------------|----------|
| **Scraping** | AI company | No | Low — lossy, no attribution |
| **Licensed training** | Publisher (somewhat) | Yes — one-time | Medium — still stripped to text |
| **Licensed RAG/domains** | Publisher | Yes — recurring | **High — if enriched** |

The future is mode 3. TNQ's value prop: take content already in JATS XML and make it RAG-ready with entity enrichment — so publishers can participate in licensed RAG instead of having their content scraped.

---

## Open Access — Why Enrichment Still Has Value (And Why It's Still a Concern)

**Why enrichment has value even for open-access content:**

Open access makes content *readable for free*. Enrichment makes it *discoverable by machines*. Those are two different things. Think of Google Maps — every street address is "open access," but Google Maps adds geocoding, routing, traffic, business info. The enrichment layer is where the value lives.

An AI tool can read the raw text of an open-access article, but it doesn't *know* that "gefitinib" is a ChEBI-linked EGFR inhibitor, or that "BRCA1" maps to a specific Gene Ontology ID. Entity tagging adds the semantic layer that makes content findable with precision.

**Why it's still a concern:**

The *leverage* in licensing negotiations drops when the underlying content is free. With paywalled content, publishers sell access + enrichment — two layers of value. With open access, the AI company can say "we can already scrape your content for free — why pay for enrichment when we could run our own NER?"

The counter-arguments:
1. **DIY enrichment is expensive and hard** — running biomedical NER + ontology linking across millions of articles, maintaining quality, keeping up with retractions/corrections
2. **Publisher enrichment is more trustworthy** — domain-aware enrichment at the source beats generic NER
3. **Scale and freshness matter** — a subscription model with continuously flowing enriched content is more practical than an AI company re-scraping and re-enriching on its own

Entity extraction + ontology linking is a *harder* enrichment to DIY than chunking/vectorization, which makes it more defensible.

---

## Why LLM Training Deals Dried Up

**In one line:** LLM training is a one-time purchase — once the model is built, the same data isn't needed again. RAG is a subscription — it needs fresh, enriched content continuously to stay current.

**Why training is a one-time event:**

Wiley said it explicitly: "Once you've trained an LLM on your corpus of content, you will walk away with a one-time payment. But what is that gonna do for you three years from now?"

- **Base model training happens infrequently.** GPT-4 wasn't retrained every month. Massive training runs happen maybe once a year or less.
- **Incremental content has diminishing returns.** If an LLM was trained on 10 million articles and you add 100,000 new ones, the marginal improvement is small. The model already "knows" the domain.
- **Fine-tuning is cheaper.** For updates, AI companies use fine-tuning or smaller targeted runs — they don't need to re-license the full catalog.
- **The power dynamic shifted.** In 2023, AI companies were desperate for data — publishers had leverage. Now base models exist. The AI company can say "we already trained on your content, we don't need another deal."

**New content still accumulates — but it's valuable for retrieval, not training.** A researcher asking "latest CRISPR findings in 2026" needs content from this month. RAG needs to retrieve it fresh, not have it baked into weights from a training run 18 months ago. That's why RAG is a subscription — freshness is the product.

---

## TNQ's Aggregation Advantage — Clarified

The aggregation advantage is **not** about negotiating leverage over publishers. TNQ is a service provider, not a content aggregator like Wiley.

**What aggregation actually gives TNQ:**

1. **Efficiency argument for publishers** — "We already process content for 50+ publishers. Adding entity enrichment to our existing pipeline is incremental cost for you, massive value for your AI discoverability."
2. **Proof across publishers** — Success with Publisher A's chemistry journal becomes a case study for Publisher B, C, D. Results compound across the client base.
3. **Standardization authority** — Because TNQ touches so many publishers' content, TNQ is uniquely positioned to set the de facto standard for how entity enrichment should be done consistently across the industry.

It's less "leverage" and more **scale advantage** — TNQ can roll this out across its existing client base with minimal friction because the content and relationships already exist.

**Where aggregation *does* create negotiating leverage — with AI companies (future state):**
- If TNQ ever moves into licensing enriched content to AI companies (like Wiley does), a corpus spanning multiple publishers and disciplines is far more attractive than any single publisher's content
- One enriched corpus = one deal for the AI company, instead of negotiating with 50 publishers separately
- More coverage = more value to the buyer = better terms

---

## Sources

- [CLEAR — Clinical Entity Augmented Retrieval (npj Digital Medicine)](https://www.nature.com/articles/s41746-024-01377-1)
- [From Valid XML to Valuable XML (JATS-Con 2025)](https://www.ncbi.nlm.nih.gov/books/NBK611679/)
- [Knowledge Graph + RAG (Scientific Reports)](https://www.nature.com/articles/s41598-025-21222-z)
- [RAG Comprehensive Survey (arXiv)](https://arxiv.org/html/2506.00054v1)
- [IBM Docling GitHub](https://github.com/docling-project/docling)
- [IBM Research Blog on Docling](https://research.ibm.com/blog/docling-generative-AI)
- [Docling Technical Report (arXiv)](https://arxiv.org/html/2408.09869v1)
- [AI Copyright Lawsuits 2024 Review](https://copyrightalliance.org/ai-lawsuit-developments-2024-review/)
- [LLM Training Data Sources (Oxylabs)](https://oxylabs.io/blog/llm-training-data)
- [RAG for Academic Literature (arXiv)](https://arxiv.org/html/2412.15404v1)
- [JATSdecoder Software Review (Scientometrics)](https://link.springer.com/article/10.1007/s11192-021-04162-z)
- [Biomedical NER Survey (arXiv)](https://arxiv.org/html/2404.07376v2)



It means: your dashboard becomes the single place publisher teams look at to decide “what to do” about AI, not just a nice report.

Concretely, who uses it and how
Product / Strategy team

Sees which journals, topics, and articles are getting the most AI queries.

Uses that to decide which areas to invest in, launch new titles, or create special issues.

Example: “AI usage for oncology is 3× cardiology → let’s prioritize more oncology content.”

Sales / Business team

Sees which AI partners (OpenAI, a specific research tool, etc.) are driving the most usage and revenue.

Uses that to negotiate better deals or decide whom to deepen relationships with.

Example: “Partner A is 70% of our AI volume but paying much less than Partner B → renegotiate pricing.”

Editorial team

Sees what kinds of questions AI users are asking about their content.

Uses that to shape editorial priorities, author guidelines, and special collections.

Example: “Many AI queries relate to methods sections in clinical trials → we should standardize methods reporting.”

Legal / Policy team

Sees how much content is being used under which policies (training vs RAG, OA vs paywalled).

Uses that to adjust risk posture and rules.

Example: “Training usage on recent content is high → tighten training permissions to a 12‑month embargo.”

Finance / Royalties team

Sees AI usage broken down by journal, article, and even author.

Uses that to compute royalty pools or society revenue shares.

Example: “Author X’s articles generated ₹Y in AI usage this quarter → update royalty statements.”

So “teams rely on our usage and revenue views” means:

They regularly open your dashboard to answer real business questions, and they take budget, product, pricing, and policy decisions based on what they see there. If you disappeared, they would lose the data they now depend on