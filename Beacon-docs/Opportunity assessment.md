# Objective

Build entity extraction and linking for scientific articles — identifying and tagging named entities (chemicals, genes, proteins, diseases, methods, datasets, software, institutions) and linking them to standard ontologies (ChEBI, Gene Ontology, MeSH, etc.).

This makes publisher content more discoverable by AI tools. When an AI system asks "papers about BRCA1 mutations in ovarian cancer," entity-tagged content gets retrieved by exact entity match — not just semantic similarity. Entity linking resolves ambiguity (e.g., "EGFR" the gene vs. the protein vs. the drug class) and enables cross-referencing across a corpus. Entities become nodes in a knowledge graph, enabling multi-hop reasoning: "Find papers that use CRISPR → on gene BRCA1 → in breast cancer models → published after 2023."

POC goal: Validate technical feasibility by enriching 2 open-access JATS XML articles from one journal with entity annotations and ontology links.

# Target customer

Scientific publishers. They want their content found, cited, and monetized by AI systems. Entity enrichment makes their articles more machine-navigable and retrievable.

Business model: Bundle into existing TNQ services — lowest friction since we already have publisher relationships and process their content into JATS XML.

Competitive landscape: Cashmere.io and others operate in this space.

# Success

- Measure precision and recall against manually annotated ground truth for the 2 articles
- Track: total entities present, entities correctly identified, entities correctly linked to ontologies
- Entity types covered: chemicals, genes, proteins, diseases, methods, datasets, software, institutions
- Output: enriched JATS XML with entity annotations and ontology links
- Demonstrable to stakeholders after technical validation

# What I believe

- **TNQ has a structural advantage.** We already have high-quality structured content in JATS XML from publishers. We're not starting from raw PDFs or plain text. The data is clean and parseable.
- **We already have the relationships.** Publishers send us their content. We're adding value to content we already touch — no new data pipeline needed.
- **AI discoverability is the new SEO for scientific content.** Publishers who don't make their content machine-readable will get left behind as AI tools become the primary way research is discovered.
- **Entity-level retrieval beats keyword and semantic search** for precise scientific queries, especially for drug-gene-disease relationships (supported by CLEAR research).

# What I need to research

- Best technical approach for entity extraction: LLM-based (Claude), specialized biomedical NER models (scispaCy, BioBERT, PubTator), or a hybrid
- Best approach for ontology linking: direct API calls to ontology databases vs. pre-built entity linkers
- Accuracy achievable across different entity types — some (genes, chemicals) may be easier than others (methods, datasets)
- Cost profile at scale — API costs per article for different approaches
- How to represent entity annotations in JATS XML (inline markup? separate annotation layer?)
- What Cashmere.io and other competitors actually offer and how they approach this

# Solution directions

**Option A: LLM-based (e.g., Claude)**
- Send article sections to an LLM with prompts for entity extraction and classification
- Use LLM to suggest ontology mappings
- Pro: Flexible, handles context well, can extract novel/ambiguous entities
- Con: Cost at scale, potential hallucination of ontology IDs, latency

**Option B: Specialized biomedical NER pipeline**
- Use models like scispaCy, BioBERT, or PubTator for entity recognition
- Use dedicated entity linkers for ontology mapping (e.g., SciSpacy's UMLS linker)
- Pro: Purpose-built, potentially more accurate for known entity types, cheaper at scale
- Con: Less flexible for novel entities, may need multiple models for different entity types

**Option C: Hybrid**
- Use specialized NER for well-defined entity types (genes, chemicals, diseases)
- Use LLM for harder categories (methods, datasets, software) and for validation/disambiguation
- Pro: Best of both worlds — accuracy where models are strong, flexibility where they're not
- Con: More complex pipeline

For the POC: start by testing all three approaches on the 2 articles and compare accuracy, cost, and complexity. Let the data decide.

# Risks to validate + how to validate them cheaply/quickly

| Risk | Validation approach |
|------|-------------------|
| **Accuracy of entity extraction** — especially for harder types like methods, datasets, software | Manually annotate 2 articles as ground truth. Run extraction. Measure precision/recall per entity type. |
| **Ontology linking quality** — entities may not map cleanly to standard ontologies | Check what % of extracted entities get confident ontology matches. Identify gaps. |
| **Cost at scale** — LLM API costs could be prohibitive for large corpus processing | Track API costs for the 2 POC articles. Extrapolate to per-article cost at corpus scale. |
| **JATS XML integration** — unclear how to embed entity annotations without breaking schema | Test enriched XML against JATS validators. Explore annotation approaches (inline vs. separate). |
| **Data privacy at scale** — publisher content may not be sendable to external APIs | Not a POC blocker (using open-access articles), but flag for production architecture. On-prem or private deployment options needed. See section below. |

# Data Privacy & IP — Pre-Sales Requirement

## The question every publisher will ask

*"When you enrich our content using AI, where does our content go?"*

This needs a clear answer before any commercial conversation. Publishers have licensed their XML to TNQ for structuring and processing — that license almost certainly does not cover sending their content to a third-party AI provider like OpenAI or Anthropic.

## The two steps with different risk profiles

**Step 1 — Enrichment (the concern):**
The pipeline sends raw article text to an external AI API (currently OpenAI) to generate contextual prefixes, figure summaries, and entity tags. During this step, proprietary publisher content leaves the publisher's infrastructure and touches a US-based AI company's servers.

- OpenAI's API policy: does not train on API inputs by default (since March 2023), but retains data for up to 30 days for abuse monitoring
- This is a GDPR and data residency issue for EU publishers
- The publisher's license with TNQ almost certainly doesn't cover this use

**Step 2 — Retrieval (the intended goal):**
AI tools search the enriched content via a controlled API and retrieve chunks. This is the product — AI finds it, cites it, and the publisher gets paid. This is fine and expected.

The distinction matters: retrieval is monetisation; sending raw content to a training pipeline is the thing publishers are currently suing AI companies for.

## Deployment options

| Approach | Publisher content leaves publisher? | Notes |
|---|---|---|
| External API (OpenAI, Anthropic) — current POC | ✅ Yes, touches third-party servers | Acceptable for open-access POC only |
| Azure OpenAI with enterprise data agreement | Stays within Azure tenant | Microsoft contractually guarantees no training use |
| Self-hosted open-source model (Llama 3, Mistral) | ❌ Never leaves TNQ infrastructure | Strongest story; requires GPU infra investment |
| On-premise deployment at publisher site | ❌ Never leaves publisher | Most secure; complex to deploy and maintain |

## Recommended go-to-market position

The cleanest and most sellable story is a self-hosted model:

*"We enrich your content using models running entirely within our infrastructure. Your XML never touches OpenAI, Google, or any other AI provider. The enriched output — which you own — is what gets made discoverable."*

This removes the IP concern entirely and is a genuine differentiator over competitors who route everything through external APIs.

## What this means for the POC

The current setup (OpenAI API, open-access articles) is fine for internal demonstration. Before showing this to a publisher — even in a sales conversation — have an answer ready for this question. The architecture decision (self-hosted vs. Azure vs. on-prem) should be part of the proposal, not an afterthought.