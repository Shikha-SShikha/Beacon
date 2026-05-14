"""
Beacon License Service
Checks whether an institution has rights to a given content chunk.
Decisions: ALLOWED | SNIPPET_ONLY | OPEN_ACCESS
"""
import re
import json
from pathlib import Path
from typing import TypedDict

# Force absolute path resolution
CONFIG_PATH = Path(__file__).parent / "license_config.json"


class LicenseDecision(TypedDict):
    decision: str   # "ALLOWED" | "SNIPPET_ONLY" | "OPEN_ACCESS"
    rights: str     # "RAG_READ_RAG_SOURCE" | "RAG" | "OPEN_ACCESS"
    journal_code: str
    reason: str


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def get_journal_code(metadata: dict) -> str:
    """Extract journal code from filename or DOI. 
    'BJ_100828.xml' -> 'BJ'
    '10.1016/j.ajps.2024.100939' -> 'AJPS'
    """
    source = metadata.get("source", "")
    doi = metadata.get("doi", "")

    # 1. Try filename (legacy format: BJ_123.xml)
    m = re.match(r"^([A-Z]+)[_\-]", source)
    if m:
        return m.group(1).upper()
        
    # 2. Try DOI (10.1016/j.ctarc.2025.100913)
    if doi:
        # Handles slashes or dots before the 'j': /j.ctarc. or .j.ctarc.
        m_doi = re.search(r"[./]j\.([a-z0-9]+)\.", doi.lower())
        if m_doi:
            return m_doi.group(1).upper()
            
    return "UNKNOWN"


def is_open_access(source: str, config: dict) -> bool:
    return source in config.get("open_access_sources", [])


def check_license(institution_id: str, chunk_metadata: dict) -> LicenseDecision:
    config = load_config()
    source = chunk_metadata.get("source", "")
    journal_code = get_journal_code(chunk_metadata)

    # Open access content is readable unless the institution explicitly opts out
    # (e.g. commercial bots — OA on the web does not grant RAG vectorization rights)
    institution_cfg = config["institutions"].get(institution_id, {})
    if is_open_access(source, config) and not institution_cfg.get("no_oa"):
        return LicenseDecision(
            decision="OPEN_ACCESS",
            rights="OPEN_ACCESS",
            journal_code=journal_code,
            reason="Freely available under open access",
        )

    institution = config["institutions"].get(institution_id)
    if not institution:
        return LicenseDecision(
            decision="SNIPPET_ONLY",
            rights="RAG",
            journal_code=journal_code,
            reason="Unknown institution - snippet only",
        )

    collections = institution.get("collections", {})
    rights = collections.get(journal_code)

    if rights == "RAG_READ_RAG_SOURCE":
        return LicenseDecision(
            decision="ALLOWED",
            rights="RAG_READ_RAG_SOURCE",
            journal_code=journal_code,
            reason=f"Full access under {institution['name']} subscription",
        )
    elif rights == "RAG":
        publisher = config["journals"].get(journal_code, {}).get("publisher", "the publisher")
        return LicenseDecision(
            decision="SNIPPET_ONLY",
            rights="RAG",
            journal_code=journal_code,
            reason=f"Snippet access only - upgrade on {publisher} for full text",
        )
    else:
        return LicenseDecision(
            decision="NO_ACCESS",
            rights="NONE",
            journal_code=journal_code,
            reason=f"Not in this institution's licensed collection (Code: {journal_code})",
        )

def get_institution_licensed_codes(institution_id: str) -> list[str]:
    """Return journal codes this institution has any access to."""
    config = load_config()
    institution = config["institutions"].get(institution_id, {})
    return list(institution.get("collections", {}).keys())

def get_institution_summary(institution_id: str) -> dict:
    config = load_config()
    institution = config["institutions"].get(institution_id, {})
    collections = institution.get("collections", {})

    licensed = []
    for journal_code, rights in collections.items():
        if journal_code == "OA":
            continue
        journal_info = config["journals"].get(journal_code, {})
        licensed.append({
            "code": journal_code,
            "name": journal_info.get("name", journal_code),
            "publisher": journal_info.get("publisher", ""),
            "color": journal_info.get("color", "#64748b"),
            "rights": rights,
        })

    return {
        "id": institution_id,
        "name": institution.get("name", "Unknown"),
        "avatar": institution.get("avatar", "👤"),
        "description": institution.get("description", ""),
        "licensed_journals": licensed,
    }
