# Publisher Attribution & Agentic Access Control

> Last updated: 2026-05-11

---

## The Question That Started This

A publisher asked: **"How can I control Agentic AI bots through content vectorization?"**

This feature is the answer.

---

## Ideation: What Options Were Considered

We mapped out three possible framings for showing attribution:

| Option | Framing | Audience |
|---|---|---|
| A | Institution usage analytics — which universities used what content | Institutional/licensing sales |
| B | Enrichment value dashboard — quality and coverage metrics | Technical/publisher editorial |
| C | Publisher-facing control panel — what AI accessed, who was blocked, what rights were applied | **Publisher rights/revenue teams** |

**Decision: Option C.**

Publishers need to see Beacon as a *control mechanism*, not just a reporting tool. The value proposition is not "here's what happened" — it's "here's what we allowed, what we blocked, and why." That distinction is the commercial insight.

---

## The Core Demo Scenario

**The setup that tells the story:**

A commercial AI company (e.g. a GPT-powered research tool) is crawling and vectorizing academic content. Without Beacon, it just scrapes and serves your content freely. With Beacon, every access attempt hits a license check — and the attempt is logged, regardless of outcome.

**Two outcomes in the feed:**

| Scenario | Who | What happened |
|---|---|---|
| Served | Licensed institution (e.g. University of Edinburgh) | Query answered, sources cited, license verified |
| Blocked | Commercial AI agent (unlicensed crawler) | Query attempted, all content NO_ACCESS, event logged with attempted journals |

The key insight: **even when blocked, the publisher can see exactly what was attempted.** That's intelligence a paywall can't give you — a paywall just refuses; Beacon records intent.

---

## How Commercial AI Bots Are Represented

### Why not a real "bot" persona?

We considered making the bot a known identity (like a GPT plugin). Instead, we use a synthetic institution: `ai_bot`.

**Why `ai_bot` and not `tu_berlin`:**
- `tu_berlin` has a real ESR journal subscription — it's a legitimate institution with narrow scope
- We needed a truly unlicensed identity to guarantee fully-blocked events
- `ai_bot` has empty collections (`{}`) AND `"no_oa": true` — it can't access anything, including open access content

### The open access nuance

Open access content on the web does NOT mean permission to vectorize and use in a RAG pipeline. That's a commercially critical distinction. In the demo, `ai_bot` is configured with `"no_oa": true` in `license_config.json`, which causes `license_service.py` to skip the OA bypass for that identity. This was intentional and surfaced during implementation when BJ_100950.xml was leaking through as OPEN_ACCESS for all institutions.

---

## What the Publisher Sees

### Attribution Page (`/attribution` in the UI)

**Summary cards (top):**
- Total events, queries served, article citations, queries blocked (amber when >0)

**Publisher tabs:**
- Filterable feed per publisher (Publisher A, B, C — anonymized)
- Each publisher sees their own served/blocked counts

**Event feed (newest first):**

*Served event (white card):*
- Query text
- Agent label (institution name) + timestamp
- Each cited source: title, journal badge, sections surfaced (Methods, Results etc.), license decision
- Article entity count
- Expandable raw JSON

*Blocked event (amber card):*
- Query text (always visible — the bot's intent is the important data)
- "Access blocked" badge + "0 served / N attempted"
- Attempted journals table: journal code, publisher label, article count
- Block reason
- Expandable raw JSON

**Section distribution bar chart:**
- Which paper sections are most surfaced by AI queries (Methods, Results, Discussion etc.)
- Reveals which parts of papers AI actually consumes — informs licensing tier design

**"How It Works" panel:**
- 4-step mechanism explained for publisher audience
- Code block showing what a blocked event looks like
- Callout: "What login walls can't do" — paywalls refuse silently; Beacon records intent

**"Simulate blocked request" button:**
- Fires the current query as `ai_bot` in background
- Creates a blocked event in the feed with 0 served, N attempted
- Demonstrates the detection mechanism without needing a real bot

---

## Publisher Anonymization

Publishers are identified by stable alphabetical labels in all UI-facing text:

| Real name | Display label |
|---|---|
| Elsevier | Publisher A |
| Pleiades Publishing | Publisher B |
| Portland Press | Publisher C |

Applied in:
- `api/routers/attribution.py` — `PUBLISHER_LABELS` dict
- `beacon-ui/src/components/layout/Sidebar.tsx` — journal hover tooltips
- `beacon-ui/src/pages/AttributionPage.tsx` — all UI text

---

## Technical Implementation

### Event log

In-memory `_EVENTS: list[dict]` in `api/routers/attribution.py`. Populated at runtime — no persistence between server restarts (intentional for demo, designed for DB in prod).

**Event types:**

`served` — logged at end of every successful `/ask` call via `log_event()`:
```python
log_event(query, institution_id, institution_name, sources=[s.model_dump() for s in sources])
```

`blocked` — logged when `/ask` finds zero allowed hits via `log_blocked_event()`:
```python
log_blocked_event(query, institution_id, institution_name, blocked_hits, journal_config)
```

### License layer

`governance/license_service.py` — `check_license(institution_id, chunk_metadata)`:

- Returns `ALLOWED`, `SNIPPET_ONLY`, `OPEN_ACCESS`, or `NO_ACCESS`
- `NO_ACCESS` → hit goes to `blocked_hits` list, NOT served
- If ALL hits are NO_ACCESS → blocked event logged, `"No accessible results found"` returned

The `no_oa` institution flag (added for `ai_bot`):
```python
if is_open_access(source, config) and not institution_cfg.get("no_oa"):
    return LicenseDecision(decision="OPEN_ACCESS", ...)
```

### Institutions used in demo

| ID | Label in feed | Purpose |
|---|---|---|
| `uni_edinburgh` | University of Edinburgh | Full-access licensed institution |
| `global_policy` | Global Policy Institute | Partial-access (energy + policy journals) |
| `tu_berlin` | TU Berlin | Narrow-access (energy journals only) |
| `guest` | Unsubscribed institution | OA content only |
| `ai_bot` | Commercial AI agent | Zero access, no OA bypass — fully blocked |

### API endpoints

`GET /attribution/summary` — aggregate stats (total events, per-publisher served/blocked counts, section distribution)

`GET /attribution/feed?publisher=<label>` — full chronological event feed, optionally filtered to one publisher's content

### Frontend simulate flow

`simulateBlockedRequest(query)` in `beacon-ui/src/api/client.ts`:
- Fires POST /ask with `institution_id: "ai_bot"`
- Swallows the "No accessible results" error response
- The backend `log_blocked_event()` fires before returning, populating the feed
- UI refreshes the feed after button click to show the new blocked event

---

## Files Changed

| File | What changed |
|---|---|
| `governance/license_config.json` | Added `ai_bot` institution with `no_oa: true`, empty collections |
| `governance/license_service.py` | Added `no_oa` check before OA bypass; load institution cfg early |
| `api/routers/attribution.py` | Complete rewrite — served + blocked event types, PUBLISHER_LABELS, AGENT_LABELS, FeedEvent/BlockedAttempt models, `log_event()`, `log_blocked_event()`, `/summary` + `/feed` endpoints |
| `api/routers/ask.py` | Added blocked_hits collection in license filter; calls `log_blocked_event()` |
| `api/main.py` | Added attribution router; CORS ports 5175/5176/5177 |
| `beacon-ui/src/types/index.ts` | Added AttributionSourceEvent, BlockedAttempt, FeedEvent, PublisherSummary, AttributionSummary |
| `beacon-ui/src/api/client.ts` | Added fetchAttributionSummary, fetchAttributionFeed, simulateBlockedRequest |
| `beacon-ui/src/pages/AttributionPage.tsx` | New page — ServedCard, BlockedCard, HowItWorksPanel, publisher tabs, section distribution |
| `beacon-ui/src/App.tsx` | Added /attribution route |
| `beacon-ui/src/pages/SearchPage.tsx` | Added "Publisher Attribution" nav button in sidebar |
| `beacon-ui/src/components/layout/Sidebar.tsx` | Journal display as dot-grid pills with hover tooltips; publisher labels anonymized |

---

## Design Decisions Log

**Why an in-memory event log?**
Keeps the demo self-contained and restartable. Real deployment would use a database (Postgres append-only table or a message queue like Kafka → analytics DB).

**Why show blocked events in the same feed as served events?**
Publishers need unified visibility. Separating them would suggest they're unrelated — but the whole point is that an attempted access and a successful access are both data points for the publisher.

**Why show the query text on blocked events?**
The bot's intent is the commercially valuable insight. "Someone asked about BRCA1 and you blocked them" tells the publisher which topics are being targeted by unlicensed agents. That's market intelligence.

**Why not show article titles on blocked events?**
Titles aren't served — the agent never received them. Showing titles would misrepresent what was disclosed. The feed shows journal codes and article counts, which is what the publisher legitimately knows was attempted.

**Why alphabetical publisher labels (A, B, C)?**
Demo requirement — avoid showing real publisher names in screenshots. Stable alphabetical mapping (Elsevier→A, Pleiades→B, Portland Press→C) applied at backend so it's consistent everywhere.

---

## Stale Reference

`ATTRIBUTION_IMPLEMENTATION.md` at the project root documents an earlier prototype (Phase 1 analytics — JSONL file logging, domain bucketing). That approach was superseded. The current implementation is in `api/routers/attribution.py` and the wiki page you're reading now.
