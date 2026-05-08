"""
Phase 2 — Post-retrieval reranking using section metadata and recency.

Applies two multipliers to raw vector distances:
  1. Section boost (query-dependent) — keyword intent detection → section multiplier
  2. Recency boost (linear decay)   — newer papers get lower distances

Combined: final_distance = raw_distance * section_multiplier * recency_multiplier
"""

from datetime import date, datetime

# ─── Intent Detection ────────────────────────────────────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "factual": [
        "finding", "result", "show", "demonstrate", "effect",
        "impact", "outcome", "cause", "inhibit", "express",
        "trial", "efficacy", "performance", "significant",
    ],
    "methodological": [
        "method", "methodology", "how was", "technique",
        "protocol", "procedure", "measure", "collect", "analyse",
        "analyze", "experiment", "assay", "workflow",
    ],
    "background": [
        "background", "context", "overview", "known", "prior",
        "previous", "literature", "review", "what is",
    ],
    "conclusion": [
        "conclusion", "summary", "main finding", "implication",
        "recommend", "takeaway", "overall",
    ],
}

# Section multipliers per intent.
# < 1.0 = boost (lower distance), > 1.0 = penalise (higher distance), 1.0 = neutral.
SECTION_MULTIPLIERS: dict[str, dict[str, float]] = {
    "factual": {
        "results": 0.85,
        "discussion": 0.85,
        "methods": 1.0,
        "introduction": 1.10,
        "conclusion": 1.0,
        "other": 1.10,
    },
    "methodological": {
        "results": 1.0,
        "discussion": 1.0,
        "methods": 0.85,
        "introduction": 1.10,
        "conclusion": 1.0,
        "other": 1.10,
    },
    "background": {
        "results": 1.0,
        "discussion": 1.0,
        "methods": 1.0,
        "introduction": 0.85,
        "conclusion": 1.0,
        "other": 1.0,
    },
    "conclusion": {
        "results": 1.0,
        "discussion": 0.85,
        "methods": 1.10,
        "introduction": 1.10,
        "conclusion": 0.85,
        "other": 1.0,
    },
}


def detect_intent(query: str) -> str:
    """Classify query intent via keyword matching. Returns the intent with the
    most keyword hits, or 'general' on ties / no matches."""
    query_lower = query.lower()
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for kw in keywords if kw in query_lower)

    if not scores or max(scores.values()) == 0:
        return "general"

    top_score = max(scores.values())
    winners = [k for k, v in scores.items() if v == top_score]
    return winners[0] if len(winners) == 1 else "general"


def get_section_multiplier(intent: str, section: str) -> float:
    """Return the section multiplier for a given intent and section type."""
    if intent == "general" or intent not in SECTION_MULTIPLIERS:
        return 1.0
    return SECTION_MULTIPLIERS[intent].get(section, 1.0)


# ─── Recency Boost ───────────────────────────────────────────────────────────

def get_recency_multiplier(
    publication_date: str | None,
    recency_weight: float = 0.10,
    max_age_years: float = 5.0,
) -> float:
    """Linear recency multiplier. Newer papers → multiplier closer to 1.0.
    Older papers → multiplier up to (1.0 + recency_weight)."""
    if not publication_date or recency_weight <= 0:
        return 1.0

    try:
        pub_date = datetime.strptime(publication_date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1.0

    age_years = (date.today() - pub_date).days / 365.25
    if age_years < 0:
        age_years = 0  # future date (preprint listed early)

    decay = min(age_years / max_age_years, 1.0)
    return 1.0 + (recency_weight * decay)


# ─── Rerank ──────────────────────────────────────────────────────────────────

def rerank(
    hits: list[dict],
    query: str,
    section_boost: bool = True,
    recency_weight: float = 0.10,
) -> list[dict]:
    """Apply section and recency reranking to raw search hits.

    Each hit dict is expected to have:
      - 'distance': float (raw cosine distance)
      - 'metadata': dict with 'section' and optionally 'publication_date'

    Returns hits sorted by final_distance, with rerank debug info attached.
    """
    intent = detect_intent(query) if section_boost else "general"

    for hit in hits:
        raw_dist = hit["distance"]
        section = (hit.get("metadata") or {}).get("section", "")
        pub_date = (hit.get("metadata") or {}).get("publication_date")

        sec_mult = get_section_multiplier(intent, section) if section_boost else 1.0
        rec_mult = get_recency_multiplier(pub_date, recency_weight)

        hit["raw_distance"] = raw_dist
        hit["distance"] = round(raw_dist * sec_mult * rec_mult, 4)
        hit["rerank_debug"] = {
            "intent": intent,
            "section_multiplier": sec_mult,
            "recency_multiplier": round(rec_mult, 4),
        }

    hits.sort(key=lambda h: h["distance"])

    # Re-assign ranks after sorting
    for i, hit in enumerate(hits):
        hit["rank"] = i + 1

    return hits
