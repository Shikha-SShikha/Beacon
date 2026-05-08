# Brainstorming: AI Governance Module + Discoverability Module

## What we're working with

**Discoverability Module** (built)
Entity-enriched content pipeline: JATS XML → NER + ontology linking → ChromaDB → precise AI retrieval. The "make our content findable by AI" layer.

**Governance Module** (from AI Governance doc)
License-aware AI search gateway: controlled delivery, real-time license enforcement, BYOS (bring your own subscription), usage tracking, monetization. The "make sure AI pays for what it finds" layer.

Two rights types:
- `RAG` — snippet only + DOI redirect; no full source access
- `READ_RAG_SOURCE` — full context viewing; enables richer AI workflows

---

## The Core Opportunity

These two modules are two halves of the same product pitch to publishers:

> "We make your content **findable** by AI — and we make sure you **get paid** when AI finds it."

Neither module alone is the full story:
- Discoverability without governance = better scraping, unmonetizable
- Governance without discoverability = a tollgate on content that isn't even indexed well
- **Both are needed together. Discoverability is done — governance is the critical next step.**

---

## How They Fit Together

**The user journey (researcher using an AI tool):**
1. Researcher/institution comes to an AI platform for discovery and research
2. They log in using their publisher-issued subscription (BYOS)
3. AI tool queries Beacon → hits the **Discoverability layer** (entity-enriched index, precise retrieval)
4. Beacon checks the **Governance layer** → does this user/institution have a license for this content?
5. If `RAG` right only: returns snippet + DOI link
6. If `RAG + READ_RAG_SOURCE`: returns full context
7. Usage logged → publisher gets attribution + revenue

**The handoff between modules:**
- Discoverability answers: *"what content is relevant?"*
- Governance answers: *"what can this requester see?"*

These are two sequential gates in the same request pipeline.

---

## Clarifications

**1. End user**
The researcher or institution arriving at the AI platform is the end user. Content and API responses are directed at the AI tool, which surfaces it to the researcher. No researcher-facing UI needed for MVP — the AI tool is the interface.

**2. BYOS — publisher-issued subscriptions only (for now)**
Two possible paths:
- Publisher-issued subscription: researcher carries their existing publisher subscription to the AI tool ← **this is the POC path**
- Beacon-issued subscription: Beacon manages its own subscription and payments module ← out of scope for now

For the POC, use the simplest possible implementation: a mock or hardcoded institution → collection mapping (e.g., "Institution X is licensed for Journal Y"). No real OAuth or payment flow needed at this stage.

**3. Build sequence**
Governance and discoverability must launch together. A discoverable but ungoverned index is unmonetizable — publishers won't accept it. Discoverability creates the asset; governance is what makes it a product.

**4. Demo vision**
Show the end-to-end governed search experience:
1. Researcher arrives at an AI platform (mock UI)
2. Prompted to log in with their publisher subscription
3. After login: visible indicator showing which publisher's content they're authorized to access
4. They search → results are filtered/gated by their license rights
5. If `RAG` only: snippet + redirect link to full article
6. If `RAG + READ_RAG_SOURCE`: full content visible in-context

---

## MVP PRD Validation

**What the PRD gets right:**
- Scope is tight and correct. No billing, no paragraph-level rules, no researcher UI, no marketplace. All the right things to cut.
- BYOS as "institution → collection" mapping is the right simplification. One service call: `(institution_id, chunk_id) → ALLOWED or DENIED + reason`.
- Policy layer (4.3) maps cleanly to the `RAG` / `READ_RAG_SOURCE` rights model: what AI can do = search, snippets, summaries; training allowed = yes/no.
- Safety switches (4.6) are smart — publisher kill switch, per-client kill switch, per-journal kill switch. These will be important for early publisher conversations.
- API design (4.4) is correct: search (DOI/keyword → chunk IDs + snippets) and fetch (chunk ID + institution → content or DENIED). Responses always include rule summary and source info.

**One tension to resolve:**
The PRD says "no UI for end readers or researchers" but the demo vision requires showing a researcher logging in and seeing gated content. This is fine — the demo UI is a POC artifact, not a production feature. Worth being explicit in the PRD that the demo UI is illustrative only and not part of the MVP build scope.

**Suggested addition to the PRD:**
Add a section on how BYOS token/credential works for the POC. Simplest approach:
- A hardcoded lookup table: `{institution_id: [collection_ids]}`
- Institution ID passed as a header or query param by the AI tool client
- No real SSO or OAuth needed for the POC — just demonstrate the enforcement logic works

**What to reference:**
Cashmere.io API docs (linked in the PRD) are worth reviewing to understand how a comparable system structures its content API — good benchmark for API design decisions.

---

## Open Questions for Next Session

- What does the mock AI platform UI look like for the demo? (simple web app, Streamlit, or just Postman-level API demo?)
- Which journals/collections from the existing corpus (BJ, REDOX, PLAS, ESR) will be used for the governance POC?
- What is the simplest institution mock we can stand up — hardcoded config file, or a small DB table?
