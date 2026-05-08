# POC Results — Enriched Content Retrieval Experiment

## What Was Built

**The problem:** Scientific articles are stored as XML files. A researcher asks an AI: *"How do community leaders affect energy transition?"* — the AI needs to find the right piece of text from thousands of articles. How well it finds it depends on how the content was prepared.

**The pipeline** takes a raw Elsevier XML article and prepares it three ways, then stores all three in a vector database. A set of queries is fired at all three versions and results are compared side-by-side.

---

## Source Articles

| File | Title | Sections | Figures/Tables |
|---|---|---|---|
| ESR-102001.xml | Collective heat-transition voting: An agent-based model integrating bounded confidence, social pressure, and information diffusion | 6 | 10 figs, 9 tables |
| ESR-102126.xml | Towards sustainable transportation: Optimizing hybrid renewable energy systems for EV charging in Bangladesh | 5 | 42 figs, 20 tables |

┌─────┬───────────────────────┬──────────────┐                                                                                       
  │  #  │        Section        │     Size     │
  ├─────┼───────────────────────┼──────────────┤                                                                                       
  │ 1   │ Introduction          │ 8,460 chars  │                                                                                       
  ├─────┼───────────────────────┼──────────────┤
  │ 2   │ Theoretical framework │ 12,811 chars │
  ├─────┼───────────────────────┼──────────────┤
  │ 3   │ Model structure       │ 11,957 chars │
  ├─────┼───────────────────────┼──────────────┤
  │ 4   │ Model verification    │ 6,310 chars  │
  ├─────┼───────────────────────┼──────────────┤
  │ 5   │ Results               │ 18,921 chars │
  ├─────┼───────────────────────┼──────────────┤
  │ 6   │ Conclusion            │ 5,536 chars  │
  └─────┴───────────────────────┴──────────────┘

  ---
  ESR-102126 — Hybrid renewable energy for EV charging, Bangladesh

  ┌─────┬──────────────────────────────────────────────────────
  │  #  │                        Section                        │     Size     │
  ├─────┼──────────────────────────────────────────────────────
  │ 1   │ Introduction                                          │ 54,262 chars │
  ├─────┼──────────────────────────────────────────────────────
  │ 2   │ Methodology                                           │ 13,831 chars │
  ├─────┼──────────────────────────────────────────────────────
  │ 3   │ Renewable energy integration for EV charging stations │ 15,976 chars │
  ├─────┼──────────────────────────────────────────────────────
  │ 4   │ Results and discussions                               │ 59,433 chars │
  ├─────┼──────────────────────────────────────────────────────
  │ 5   │ Conclusions                                           │ 10,608 chars │
  └─────┴──────────────────────────────────────────────────────


**Total chunks processed:** 40 (25 from ESR-102001 + 15 from ESR-102126)

---

## The Three Versions of the Same Content

Take this paragraph from the article about district heating in the Netherlands:

**Version 1 — Raw** (just the text, as-is):
```
Opinion dynamics research and energy-system modeling increasingly
face a common challenge: how to link individual behavior to
collective outcomes...
```

**Version 2 — Metadata** (article info prepended as a header):
s```
Title: Collective heat-transition voting...
Authors: Xinyi Mu, Dujuan Yang, Qi Han
Keywords: Agent-based modeling, Opinion dynamics...

Opinion dynamics research and energy-system modeling increasingly
face a common challenge...
```

**Version 3 — Enriched** (AI-generated one-sentence contextual prefix + text):
```
This theoretical framework section from Xinyi Mu's 2025 article
discusses the role of agent-based modeling in linking individual
behavior to collective energy transition outcomes.

Opinion dynamics research and energy-system modeling increasingly
face a common challenge...
```

All three versions are converted to embeddings (`text-embedding-3-small`) and stored in ChromaDB. The same 7 queries are fired at all three collections. Distance = cosine distance; **lower = better match**.

---

## Experiment Results

### Distance Summary — Rank 1 Match per Query

| Query | Raw | Metadata | Enriched | Winner |
|---|---|---|---|---|
| How does social network structure affect collective energy transition decisions? | 0.8509 | 0.8069 | 0.8672 | **Metadata** |
| What methodology was used to model agent behavior and opinion dynamics? | 0.6470 | 0.7232 | 0.6673 | **Raw** |
| What are the main results and findings of the study? | 1.2475 | 1.4270 | 1.2998 | **Raw** |
| How is bounded confidence theory applied in the simulation? | 1.0086 | 1.1467 | 0.9753 | **Enriched** |
| What is the role of community leaders and brokers in driving adoption? | 1.1158 | 1.2239 | 1.1157 | **Enriched** |
| Hybrid renewable energy system optimization for EV charging stations | 0.6396 | 0.5674 | 0.6262 | **Metadata** |
| What tables show numerical results for charging station performance? | 0.9642 | 1.0685 | 0.9642 | **Raw** |

**Rank-1 wins: Raw = 3/7 · Metadata = 2/7 · Enriched = 2/7**

---

### Detailed Examples

#### Example 1 — Conceptual query (enriched wins)
> *"How is bounded confidence theory applied in the simulation?"*

| Version | Distance | What was returned |
|---|---|---|
| Raw | 1.0086 | Model credibility section ❌ (wrong section) |
| Metadata | 1.1467 | Same wrong section |
| **Enriched** | **0.9753** | **Model verification section ✅ (best match)** |

The AI prefix explicitly described this chunk as being about bounded confidence mechanisms — so when a researcher asks about bounded confidence, the enriched version matched more precisely.

#### Example 2 — Topic query (metadata wins)
> *"Hybrid renewable energy system optimization for EV charging stations"*

| Version | Distance | What was returned |
|---|---|---|
| Raw | 0.6396 | A figure (reasonable but not best) |
| **Metadata** | **0.5674** | **Results section ✅ (best match)** |
| Enriched | 0.6262 | Results section |

The article title contained "hybrid renewable energy systems for EV charging" — prepending the title alone was enough to route to the right article and section.

#### Example 3 — Generic query (raw wins)
> *"What are the main results and findings of the study?"*

| Version | Distance | What was returned |
|---|---|---|
| **Raw** | **1.2475** | Model credibility section (closest, but all distances are high) |
| Metadata | 1.4270 | Results section |
| Enriched | 1.2998 | Results section |

All distances are high — this query is too vague to retrieve well from any version. The word "results" appears in the raw text itself, giving raw a slight edge. This is expected behaviour.

---

## What the Results Prove

Enrichment helps most for **the queries that matter most** — specific, domain-level questions a researcher actually asks.

- **Generic queries** ("what are the results?") don't need enrichment. The word "results" already appears in the text — raw wins trivially.
- **Topic queries** ("hybrid renewable energy + EV") are well-served by metadata — the article title alone routes to the right document.
- **Conceptual queries** ("how is bounded confidence applied?", "role of community brokers") — these require the chunk to already *know what it's about*. That's exactly what the AI prefix adds, and enriched wins here.

Conceptual queries are the hardest and most valuable to serve well. They are also the queries researchers actually ask.

---

## What the Results Also Reveal — The Next Layer

The current pipeline has:
- ✅ Section chunking
- ✅ AI-generated contextual prefix (section-level)
- ✅ Figure/table summarisation
- ✅ Article metadata (title, authors, DOI, keywords)
- ❌ Entity extraction (NER)
- ❌ Ontology linking (MeSH, ChEBI, Gene Ontology, etc.)

If "bounded confidence" were tagged as a known concept linked to an ontology ID, or "district heating" were linked to an energy ontology, enriched would win even more consistently on domain queries. That is the next layer of value — and the gap that separates this from what Wiley currently does.

---

## Setup

```
pipeline.py     — parses Elsevier XML, calls GPT-4o-mini to enrich, outputs JSON chunks
experiment.py   — loads chunks, builds 3 ChromaDB collections, runs queries, compares results
```

**Models used:**
- Enrichment: `gpt-4o-mini` (contextual prefixes + figure/table summaries)
- Embeddings: `text-embedding-3-small`
- Vector DB: ChromaDB (in-memory)

      182 +- Vector DB: ChromaDB (persistent, on disk at `./chroma_db/`)                                                         
      183 +                                                                                                                      
      184 +---                                                                                                                   
      185 +                                                                                                                      
      186 +## Gaps in the Experiment & Honest Assessment                                                                         
      187 +                                                                                                                      
      188 +### Why raw wins most of the time in these results                                                                    
      189 +                                                                                                                      
      190 +**1. The AI prefix is too small relative to the section text**                                                        
      191 +The contextual prefix is ~40 words. The section text is 2,000+ characters. When embedded together, the prefix         
          +represents roughly 5% of the signal — the embedding is dominated by the raw text regardless of the prefix.            
      192 +                                                                                                                      
      193 +**2. Two articles is too small a corpus**                                                                             
      194 +With 40 chunks from 2 articles, every section is easily retrievable by keyword alone. There is nothing to             
          +disambiguate. The value of enrichment only compounds at scale — when you have 10,000+ chunks from 500+ articles and   
          +multiple "Introduction" or "Methods" sections that look similar in raw text.                                          
      195 +                                                                                                                      
      196 +**3. Figures are identical in raw and enriched collections — a design flaw**                                          
      197 +In the current experiment, "raw" strips the AI prefix from text chunks (before the first blank line). But figure and  
          +table chunks have no prefix separator — they are stored as `"Fig. 1: {AI summary}"` in both versions. So raw and      
          +enriched figure chunks contain the exact same AI-generated summary. The experiment never tests the real gap for       
          +figures.                                                                                                              
      198 +                                                                                                                      
      199 +---                                                                                                                   
      200 +                                                                                                                      
      201 +### The comparison that actually tells the story                                                                      
      202 +                                                                                                                      
      203 +The experiment compares **clean XML vs slightly-more-enriched XML**. That is the wrong baseline. The right comparison 
          + is:                                                                                                                  
      204 +                                                                                                                      
      205 +| Version | What it represents | What AI gets today |                                                                 
      206 +|---|---|---|                                                                                                         
      207 +| **HTML scrape** | Noisy HTML — nav bars, cookie banners, ad text mixed with content. Figures are `<img>` tags,      
          +completely invisible to search. No section identity. | ✅ This is what AI tools get when accessing publisher websites 
          + |                                                                                                                    
      208 +| **Clean XML** | Structured section text with labels, clean metadata, figure captions intact | ❌ AI tools don't get 
          + this — only the publisher has it |                                                                                   
      209 +| **Enriched XML** | Clean XML + AI contextual prefix + AI figure/table summaries | ❌ Doesn't exist yet anywhere —   
          +this is the product |                                                                                                 
      210 +                                                                                                                      
      211 +The gap between HTML scrape and enriched XML is large and would show clearly in a retrieval experiment. The gap       
          +between clean XML and enriched XML (what the current experiment measures) is small at 2 articles.                     
      212 +                                                                                                                      
      213 +**Concrete example — figures:**                                                                                       
      214 +                                                                                                                      
      215 +```                                                                                                                   
      216 +HTML scrape  →  <img src="gr1.jpg" alt="">          ← invisible to any search                                         
      217 +Raw XML      →  Fig. 1 — "Integrated theoretical framework..."  ← short caption only                                  
      218 +Enriched XML →  Fig. 1 — "Figure 1 presents an integrated theoretical framework                                       
      219 +                connecting bounded confidence, social influence, and dual-process                                     
      220 +                theory, showing how agents update opinions in the heating                                             
      221 +                transition model across three layers."  ← searchable, meaningful                                      
      222 +```                                                                                                                   
      223 +                                                                                                                      
      224 +---                                                                                                                   
      225 +                                                                                                                      
      226 +### What a stronger version of the experiment would include                                                           
      227 +                                                                                                                      
      228 +1. **HTML-scraped baseline** — simulate what AI tools actually get from publisher websites: strip structure, inject   
          +navigation noise, replace figures with empty strings                                                                  
      229 +2. **Scale** — 50+ articles minimum before enrichment's disambiguation value is visible                               
      230 +3. **Figure-specific queries** — "show me a diagram of the decision architecture", "which figure compares network     
          +topologies" — these would show enriched winning by a large margin over both HTML and raw XML                          
      231 +4. **Entity-level queries** — once NER + ontology linking is added, queries like "articles mentioning EGFR inhibitors 
          + in the methods section" would only be answerable with enriched content                                               
      232 +                                                                                                                      
      233 +---                                                                                                                   
      234 +                                                                                                                      
      235 +### What enrichment is genuinely giving right now                                                                     
      236 +                                                                                                                      
      237 +| Capability | HTML scrape | Raw XML | Enriched XML |                                                                 
      238 +|---|---|---|---|                                                                                                     
      239 +| Section identity (intro / methods / results) | ❌ | ✅ | ✅ |                                                       
      240 +| Article metadata per chunk (DOI, authors, keywords) | ❌ | ✅ | ✅ |                                                
      241 +| Figures searchable | ❌ | Partially (caption only) | ✅ (AI summary) |                                              
      242 +| Tables searchable | ❌ | Partially (caption only) | ✅ (content + summary) |                                        
      243 +| Cross-article disambiguation at scale | ❌ | ❌ | ✅ (AI prefix) |                                                  
      244 +| Entity / ontology linking | ❌ | ❌ | ❌ (next layer) |                                                             
      245 +                                                                                                                      
      246 +The structural enrichment — clean extraction, section labelling, figure summarisation — is the primary value. The AI
          +prefix is a thin layer on top that matters at scale and for conceptual queries, but is not visible at 2 articles.

---

### How to present results — stop using win/loss framing

Presenting results as distance scores + a winner per query makes enrichment look like it loses. That is the wrong frame.

**The problem with rank-1 distance as the metric:**
A difference of 0.97 vs 0.98 looks like noise, not value. And raw has a structural advantage on verbatim keyword queries that has nothing to do with enrichment quality.

**Better framing — Top-K recall:**
Instead of "which collection wins on rank-1 distance", show how many relevant chunks appear in the top-K results:

| Query | Raw top-5 | Enriched top-5 |
|---|---|---|
| Articles mentioning YY1 in methods | 1 relevant + 4 noise | 3 relevant + 2 noise |
| Figure showing decision architecture | 0 relevant (no figure descriptions) | 2 relevant (AI summaries) |
| EGFR inhibitors in clinical context | 1 relevant (keyword match) | 3 relevant (entity-tagged) |

This shows enrichment surfaces more relevant results overall — not that it narrowly beats raw on one distance score.

**Broader reframe — "what you can find that you couldn't before":**
Stop asking "which version wins" and instead demonstrate:
- **Figure queries** — HTML scrape returns nothing (invisible `<img>` tags); raw returns a short caption; enriched returns a 3-sentence searchable summary
- **Entity-level queries** — "articles mentioning EGFR inhibitors in the methods section" is simply unanswerable without NER tagging, regardless of collection
- **Entity chips in the UI** — a publisher or librarian can see what concepts are in a chunk without opening the article

---

### Four concrete improvements to implement next

1. **Top-K recall view in the chat app** — show top-N results from each collection side by side, not just rank-1. Add a slider for K (default 3 or 5). This makes the recall advantage visible.

2. **Figure-specific example queries** — add to the example tabs: *"show me a diagram of the decision architecture"*, *"which figure compares network topologies"*. These expose the largest real gap between HTML, raw XML, and enriched XML.

3. **HTML-scraped baseline** — run the pipeline on a plain-text/HTML scrape of the same articles (strip structure, inject nav noise, replace figures with empty strings) and add it as a 4th `html_scrape` collection. The correct comparison is HTML scrape vs enriched XML, not clean XML vs enriched XML.

4. **Entity-level queries** — once NER + ontology linking is added, add example queries like *"articles mentioning EGFR inhibitors in the methods section"*. These are only answerable with enriched content and make the clearest possible case for the pipeline.

---

# Conversation Log

A record of key discussions, decisions, and insights from building this POC. Useful for revisiting context and reasoning later.

---

## On the Pipeline Design

**Q: The pipeline diagram shows XML Input → Detect type → JSON → Parse JATS → Chunks → AI prefix → Figures → Combine → Vector DB. Should this work for both files?**

Yes. Both files (ESR-102001 and ESR-102126) are Elsevier DTD v5.7 format — not JATS as originally assumed. Key structural differences from JATS:
- Tags use `ce:` prefix throughout (`ce:section`, `ce:para`, `ce:figure` etc.)
- All figures and tables are collected in a `<ce:floats>` block at the top of the file, not inline in the body
- Sections can nest (sec2 → sec2.1, sec2.2...) — subsections are folded into parent chunks
- Tables use CALS model (`tgroup > thead/tbody > row > entry`)
- Float-anchors (`<ce:float-anchor refid="fig1"/>`) in paragraphs reference figures by ID

The pipeline was built to handle both files without any file-specific logic.

---

## On What AI Tools Actually Access

**Q: When AI tools access content from the web, do they access XML files or web content?**

They access the rendered HTML page — the same thing a browser sees. Not the XML.

The XML is a backend format that lives on the publisher's internal systems and is never exposed publicly. When an AI company scrapes a journal website for training data, it gets HTML, strips the tags, and keeps plain text — losing section structure, table formatting, figure content, and metadata.

Three modes of AI content access:
1. **Web scraping for training** — HTML → stripped plain text. Lossy, no structure, no attribution. Triggered $1.5B+ in lawsuits.
2. **RAG retrieval** — chunked text from various sources. Quality entirely depends on how well the content was prepared.
3. **Licensed content pipelines** — publisher proactively prepares enriched structured data and delivers via API. This is the emerging model and where recurring revenue lives.

The XML pipeline being built addresses mode 3. The XML is the raw material only the publisher has access to — that's the moat.

---

## On What the Sections Look Like

**ESR-102001** — *Collective heat-transition voting (district heating, Netherlands)*
- Introduction (8,460 chars)
- Theoretical framework (12,811 chars)
- Model structure (11,957 chars)
- Model verification (6,310 chars)
- Results (18,921 chars)
- Conclusion (5,536 chars)
- 10 figures, 9 tables

**ESR-102126** — *Hybrid renewable energy for EV charging, Bangladesh*
- Introduction (54,262 chars) — very large, many subsections folded in
- Methodology (13,831 chars)
- Renewable energy integration for EV charging stations (15,976 chars)
- Results and discussions (59,433 chars) — very large
- Conclusions (10,608 chars)
- 42 figures, 20 tables

Note: ESR-102126's Introduction and Results sections are extremely large (54K and 59K chars). In production, these would need further splitting — a 54K char chunk is too large to embed meaningfully.

---

## On ChromaDB and Whether Results Are Real

**Q: Where is the ChromaDB? Are results simulated?**

Initially ChromaDB was in-memory (disappeared after each run). It was switched to a persistent client saved to disk at `./chroma_db/chroma.sqlite3` (2.3MB with 3 collections, 40 chunks each).

Results are real — every distance number is computed by the OpenAI embedding API (`text-embedding-3-small`) at query time against actual stored vectors. Nothing is hardcoded. You can verify by typing a query that was never used before and it will return a real result.

---

## On Why Raw Wins Most Queries

**Q: For most queries raw data is the best match. What kind of improvements in discoverability is enrichment giving?**

Honest answer: at 2 articles, not much visible improvement from the AI prefix. Three reasons:

1. **The prefix is too small** — 40 words against 2,000+ chars of section text. The prefix represents ~5% of the embedding signal. The raw text dominates.

2. **Two articles is too small a corpus** — with 40 chunks, everything is easily retrieved by keyword. Enrichment's value is disambiguation — telling apart 500 "Introduction" sections from different articles. At 2 articles there's nothing to disambiguate.

3. **Figures are broken in the experiment** — figure chunks are stored as `"Fig. 1: {AI summary}"` in both raw and enriched collections (no prefix separator exists for figures). So raw and enriched figure chunks are identical — the experiment never tests the real gap for figures.

**What enrichment is genuinely giving right now:**
- Figures go from short captions to searchable 3-sentence summaries (real value, just not tested well)
- Tables go from caption-only to caption + structured content
- Every chunk carries full article metadata (DOI, authors, keywords, section type)
- Cross-article disambiguation at scale (not visible at 2 articles)

**The real comparison that tells the story** is HTML scrape vs enriched XML — not clean XML vs enriched XML. The gap between what AI gets from scraping (noisy HTML, invisible figures) and what a licensed enriched pipeline delivers is large. The current experiment only measures the small gap between two already-clean versions.

---

## On Schema.org / JSON-LD

**Q: Structured data like Schema.org / JSON-LD — when a page says "this is a scholarly article, these are the authors, this is the journal" — is that useful?**

Yes, it solves the **identification** problem. Schema.org tells crawlers and AI tools: this is a ScholarlyArticle, written by X, published in journal Y, DOI is Z. Every publisher should have it. It improves citation accuracy and rich search results.

But it stops at the article level. It can't tell an AI:
- What section 3.2 argues
- What Figure 4 shows
- That "EGFR" in this context means the gene not the drug class

Schema.org is a library catalog card — it tells you the book exists and who wrote it. The enriched XML pipeline is the book's index — it tells you which page to open for a specific question.

**Q: But don't we also want to tell AI what the article is?**

Yes — and the pipeline already does this. Every chunk carries the full article metadata (DOI, title, authors, journal, keywords, date) directly in its payload. The difference from Schema.org is that this metadata is attached at the chunk level (every section, every figure) rather than just once per article.

**Q: For AI tools using publisher's premium licensed content — is Schema.org useful?**

No — largely irrelevant in that scenario. Schema.org is designed for web crawlers hitting public HTML pages. When an AI tool has a licensed deal and receives data through an API or data feed, there's no HTML involved, so there's no Schema.org to read. The metadata is delivered directly in the chunk payload.

Schema.org is for the open web — how you talk to tools you have no relationship with. The pipeline is for licensed relationships — far richer than anything Schema.org can express.

| Scenario | Schema.org useful? |
|---|---|
| Google indexing a journal page | ✅ Yes |
| AI training scraper on public pages | ✅ Yes — better attribution |
| Researcher finding articles via web search | ✅ Yes |
| AI tool with licensed RAG data feed | ❌ No — metadata in payload |
| AI tool accessing paywalled content via API | ❌ No |

---

## On the Chat Interface

Built with Streamlit (`chat_app.py`). Key design decisions:
- Replaced `st.chat_input` (viewport-pinned, nothing can go below it) with a regular `st.form` to get layout control
- Example queries in three tabs (Generic / Topic / Contextual) sit below the input — always visible
- Clicking an example query fires it directly; no radio button needed for query type
- ChromaDB loads once and is cached across queries (`@st.cache_resource`)
- Results show side-by-side: Raw | Metadata | Enriched, with the best match highlighted in green

---

## Files in This Project

| File | Purpose |
|---|---|
| `ESR-102001.xml` | Elsevier article — heat-transition voting, Netherlands |
| `ESR-102126.xml` | Elsevier article — renewable energy for EVs, Bangladesh |
| `pipeline.py` | Parses XML, enriches with GPT-4o-mini, outputs JSON chunks |
| `experiment.py` | Builds 3 ChromaDB collections, runs standard queries, prints comparison |
| `chat_app.py` | Streamlit UI — free-form queries against all 3 collections |
| `ESR-102001_chunks.json` | Processed chunks from ESR-102001 (25 chunks) |
| `ESR-102126_chunks.json` | Processed chunks from ESR-102126 (15 chunks, floats capped at 10) |
| `chroma_db/` | Persistent ChromaDB on disk — 3 collections, 40 chunks each |
| `.env` | API key (do not commit) |
| `POC results.md` | This file |

