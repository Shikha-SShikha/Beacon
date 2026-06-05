"""
Attribution service — captures and serves publisher usage events.

Two event types flow into a single chronological feed:
  "served"  — query answered, sources cited, license verified
  "blocked" — query attempted, all content NO_ACCESS, agent revealed intent

Agent label overrides (for unlicensed/bot identities):
  guest → "Commercial AI agent"
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/attribution", tags=["attribution"])

AGENT_LABELS: dict[str, str] = {
    "ai_bot":    "Commercial AI agent",
    "tu_berlin": "Commercial AI agent",
    "guest":     "Unsubscribed institution",
}

# Single chronological log — both "served" and "blocked" events
_EVENTS: list[dict] = []


# ── Pydantic shapes ────────────────────────────────────────────────────────

class AttributionSourceEvent(BaseModel):
    citation_id: int
    title: str
    journal_code: str
    publisher_label: str
    doi: str
    sections_used: list[str]
    license_decision: str
    entity_count: int = 0


class BlockedAttempt(BaseModel):
    journal_code: str
    publisher_label: str
    article_count: int


class FeedEvent(BaseModel):
    event_id: str
    event_type: str               # "served" | "blocked"
    timestamp: str
    query: str
    institution_id: str
    agent_label: str              # display name for institution or agent
    # Served-only fields
    sources: list[AttributionSourceEvent] = []
    # Blocked-only fields
    attempted: list[BlockedAttempt] = []
    articles_attempted: int = 0
    articles_served: int = 0
    block_reason: str = ""


class PublisherSummary(BaseModel):
    label: str
    queries_served: int
    article_citations: int
    queries_blocked: int
    institution_count: int
    top_sections: list[dict]


class AttributionSummary(BaseModel):
    total_events: int
    total_served: int
    total_blocked: int
    publishers: list[PublisherSummary]


# ── Internal helpers ───────────────────────────────────────────────────────

def _agent_label(institution_id: str, institution_name: str) -> str:
    return AGENT_LABELS.get(institution_id, institution_name or institution_id)


def _extract_section_labels(sections: list) -> list[str]:
    IMRAD = {"results", "methods", "discussion", "introduction",
             "conclusion", "abstract", "figure", "table"}
    labels, seen = [], set()
    for sec in sections:
        section = (sec.section if hasattr(sec, "section") else sec.get("section", "")) or ""
        sub = (sec.subsection_title if hasattr(sec, "subsection_title")
               else sec.get("subsection_title", "")) or ""
        st  = (sec.section_title if hasattr(sec, "section_title")
               else sec.get("section_title", "")) or ""
        label = section.capitalize() if section.lower() in IMRAD else (st or section.capitalize())
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


# ── Log writers (called from ask.py) ──────────────────────────────────────

def log_event(
    query: str,
    institution_id: str,
    institution_name: str,
    sources: list[dict],
) -> None:
    """Log a successfully served query."""
    source_events = []
    for src in sources:
        publisher_real = src.get("publisher", "")
        source_events.append({
            "citation_id":     src.get("citation_id", 0),
            "title":           src.get("title", ""),
            "journal_code":    src.get("journal_code", ""),
            "publisher_label": publisher_real or "Unknown",
            "doi":             src.get("doi", ""),
            "sections_used":   _extract_section_labels(src.get("sections", [])),
            "license_decision":src.get("license_decision", ""),
            "entity_count":    src.get("entity_count", 0),
        })
    _EVENTS.append({
        "event_id":       str(uuid.uuid4())[:8],
        "event_type":     "served",
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "query":          query,
        "institution_id": institution_id,
        "agent_label":    _agent_label(institution_id, institution_name),
        "sources":        source_events,
        "attempted":      [],
        "articles_attempted": len(source_events),
        "articles_served":    len(source_events),
        "block_reason":   "",
    })


def log_blocked_event(
    query: str,
    institution_id: str,
    institution_name: str,
    blocked_hits: list[dict],
    journal_config: dict,
) -> None:
    """Log a fully blocked query — agent revealed intent, got nothing back."""
    # Group blocked hits by journal code and count
    journal_counts: dict[str, int] = {}
    for hit in blocked_hits:
        meta = hit.get("metadata", {})
        jcode = meta.get("journal_code") or ""
        if not jcode:
            # Try to derive from source filename
            source = meta.get("source", "")
            jcode = source.split("_")[0] if "_" in source else "UNKNOWN"
        journal_counts[jcode] = journal_counts.get(jcode, 0) + 1

    attempted = []
    for jcode, count in journal_counts.items():
        publisher_real = journal_config.get(jcode, {}).get("publisher", "")
        attempted.append({
            "journal_code":    jcode,
            "publisher_label": publisher_real or "Unknown",
            "article_count":   count,
        })

    _EVENTS.append({
        "event_id":           str(uuid.uuid4())[:8],
        "event_type":         "blocked",
        "timestamp":          datetime.now(timezone.utc).isoformat(),
        "query":              query,
        "institution_id":     institution_id,
        "agent_label":        _agent_label(institution_id, institution_name),
        "sources":            [],
        "attempted":          attempted,
        "articles_attempted": len(blocked_hits),
        "articles_served":    0,
        "block_reason":       "No active license for this agent",
    })


# ── API endpoints ──────────────────────────────────────────────────────────

@router.get("/summary", response_model=AttributionSummary)
def get_summary():
    pub_stats: dict[str, dict] = {}

    for ev in _EVENTS:
        if ev["event_type"] == "served":
            for src in ev["sources"]:
                label = src["publisher_label"]
                s = pub_stats.setdefault(label, {
                    "served_ids": set(), "citations": 0,
                    "blocked_ids": set(), "institutions": set(), "section_counts": {},
                })
                s["served_ids"].add(ev["event_id"])
                s["citations"] += 1
                s["institutions"].add(ev["institution_id"])
                for sec in src["sections_used"]:
                    s["section_counts"][sec] = s["section_counts"].get(sec, 0) + 1

        elif ev["event_type"] == "blocked":
            for att in ev["attempted"]:
                label = att["publisher_label"]
                s = pub_stats.setdefault(label, {
                    "served_ids": set(), "citations": 0,
                    "blocked_ids": set(), "institutions": set(), "section_counts": {},
                })
                s["blocked_ids"].add(ev["event_id"])

    publishers = []
    for label in sorted(pub_stats.keys()):
        s = pub_stats[label]
        top_sections = sorted(
            [{"section": k, "count": v} for k, v in s["section_counts"].items()],
            key=lambda x: -x["count"]
        )[:5]
        publishers.append(PublisherSummary(
            label=label,
            queries_served=len(s["served_ids"]),
            article_citations=s["citations"],
            queries_blocked=len(s["blocked_ids"]),
            institution_count=len(s["institutions"]),
            top_sections=top_sections,
        ))

    served  = sum(1 for e in _EVENTS if e["event_type"] == "served")
    blocked = sum(1 for e in _EVENTS if e["event_type"] == "blocked")

    return AttributionSummary(
        total_events=len(_EVENTS),
        total_served=served,
        total_blocked=blocked,
        publishers=publishers,
    )


@router.get("/feed", response_model=list[FeedEvent])
def get_feed(publisher: str | None = None):
    """All events newest-first, optionally filtered to a publisher's content."""
    events = list(reversed(_EVENTS))

    if publisher:
        filtered = []
        for ev in events:
            if ev["event_type"] == "served":
                sources = [s for s in ev["sources"] if s["publisher_label"] == publisher]
                if sources:
                    filtered.append({**ev, "sources": sources})
            elif ev["event_type"] == "blocked":
                attempted = [a for a in ev["attempted"] if a["publisher_label"] == publisher]
                if attempted:
                    filtered.append({**ev, "attempted": attempted})
        events = filtered

    return [FeedEvent(**ev) for ev in events]
