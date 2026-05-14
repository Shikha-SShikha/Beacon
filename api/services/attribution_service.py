"""
attribution_service.py — Metered usage tracking and attribution logging

Logs all article accesses to JSONL format for billing and usage analytics.
Records: timestamp, institution, article, journal, domain, access_level, query, rank, session_id
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Domain mapping: which journals belong to which research domain
DOMAIN_MAPPING = {
    "BJ": "Biomedical",           # Biochemical Journal
    "REDOX": "Biomedical",        # Redox Biology
    "CELREP": "Biomedical",       # Cell Reports
    "BIOPHA": "Biomedical",       # Biomedicine & Pharmacotherapy
    "GENDIS": "Biomedical",       # Genes & Diseases
    "CLNVES": "Biomedical",       # Clinical and Experimental Medicine
    "AJPS": "Biomedical",         # Asian Journal of Pharmaceutical Sciences
    "CTARC": "Biomedical",        # Clinical and Translational Radiation Oncology
    "ESR": "Energy & Engineering", # Energy Systems Research
    "PLAS": "Policy & Leadership", # Project Leadership & Society
}

ATTRIBUTION_LOG = Path(__file__).parent.parent.parent / ".tmp" / "attribution.jsonl"


def get_journal_code_from_source(source: str) -> str:
    """
    Extract journal code from source string.
    Examples: "BJ_100828" -> "BJ", "ESR-102001" -> "ESR"
    """
    if not source:
        return "UNKNOWN"
    # Split on underscore or dash and take first part
    code = source.split("_")[0].split("-")[0]
    return code


def get_domain_for_journal(journal_code: str) -> str:
    """Get research domain for a given journal code."""
    return DOMAIN_MAPPING.get(journal_code, "Other")


def log_search_attribution(
    institution_id: str,
    article_id: str,
    query: str,
    access_level: str,
    rank: int,
    session_id: Optional[str] = None,
) -> None:
    """
    Log an article appearing in search results.

    Args:
        institution_id: e.g. "uni_edinburgh"
        article_id: e.g. "BJ_100850" (from metadata.source)
        query: search query string
        access_level: "FULL_TEXT" | "SNIPPET_ONLY" | "OPEN_ACCESS"
        rank: position in results (1-indexed)
        session_id: optional session identifier
    """
    journal_code = get_journal_code_from_source(article_id)
    domain = get_domain_for_journal(journal_code)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "search_result",
        "institution_id": institution_id,
        "article_id": article_id,
        "journal_code": journal_code,
        "domain": domain,
        "access_level": access_level,
        "query": query,
        "rank": rank,
        "session_id": session_id,
    }

    _append_log(log_entry)


def log_collection_view(
    institution_id: str,
    domain: str,
    journals: list[str],
    action: str = "browse",
    session_id: Optional[str] = None,
) -> None:
    """
    Log a user browsing/viewing a collection.

    Args:
        institution_id: e.g. "uni_edinburgh"
        domain: e.g. "Biomedical"
        journals: list of journal codes, e.g. ["BJ", "REDOX"]
        action: "browse" | "filter" | "expand"
        session_id: optional session identifier
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "collection_view",
        "institution_id": institution_id,
        "domain": domain,
        "journals": journals,
        "action": action,
        "session_id": session_id,
    }

    _append_log(log_entry)


def _append_log(entry: dict) -> None:
    """Append a log entry to the JSONL attribution log."""
    ATTRIBUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTRIBUTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_usage_stats(institution_id: Optional[str] = None) -> dict:
    """
    Read attribution log and compute usage statistics.

    Args:
        institution_id: if provided, filter to this institution only

    Returns:
        dict with stats by journal, domain, access_level
    """
    if not ATTRIBUTION_LOG.exists():
        return {}

    stats = {
        "by_domain": {},
        "by_journal": {},
        "by_access_level": {},
        "total_accesses": 0,
    }

    with open(ATTRIBUTION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)

                # Filter by institution if specified
                if institution_id and entry.get("institution_id") != institution_id:
                    continue

                # Only count search_result events for metered usage
                if entry.get("event_type") != "search_result":
                    continue

                stats["total_accesses"] += 1

                # Track by domain
                domain = entry.get("domain", "Other")
                stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

                # Track by journal
                journal = entry.get("journal_code", "UNKNOWN")
                stats["by_journal"][journal] = stats["by_journal"].get(journal, 0) + 1

                # Track by access level
                access = entry.get("access_level", "UNKNOWN")
                stats["by_access_level"][access] = stats["by_access_level"].get(access, 0) + 1

            except json.JSONDecodeError:
                continue

    return stats
