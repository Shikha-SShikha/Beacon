"""
collections.py — Collections browsing endpoints

Provides article collections grouped by research domain and journal.
Integrated with license checking and attribution logging.
"""

from fastapi import APIRouter, HTTPException
from ..models import CollectionsSummary
from ..services.collections_service import get_collections_summary
from ..services.attribution_service import log_collection_view
from governance.license_service import load_config

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("/{institution_id}", response_model=CollectionsSummary)
def get_collections(institution_id: str):
    """
    Get all article collections for an institution, organized by domain.

    Args:
        institution_id: e.g., "uni_edinburgh"

    Returns:
        Collections grouped by research domain, with journals and articles
    """
    config = load_config()
    if institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")

    collections = get_collections_summary(institution_id)

    # Log the collection view
    domains = [c["domain"] for c in collections["collections"]]
    if domains:
        all_journals = []
        for collection in collections["collections"]:
            for journal in collection["journals"]:
                all_journals.append(journal["journal_code"])

        log_collection_view(
            institution_id=institution_id,
            domain=" & ".join(domains),
            journals=list(set(all_journals)),
            action="browse",
        )

    return CollectionsSummary(**collections)


@router.get("/{institution_id}/domain/{domain_name}", response_model=dict)
def get_domain_collection(institution_id: str, domain_name: str):
    """
    Get articles in a specific domain for an institution.

    Args:
        institution_id: e.g., "uni_edinburgh"
        domain_name: e.g., "Biomedical"

    Returns:
        Domain collection with journals and articles
    """
    config = load_config()
    if institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")

    collections = get_collections_summary(institution_id)

    domain_collection = None
    for collection in collections["collections"]:
        if collection["domain"] == domain_name:
            domain_collection = collection
            break

    if not domain_collection:
        raise HTTPException(
            status_code=404,
            detail=f"Domain '{domain_name}' not found for this institution"
        )

    # Log the domain view
    journals = [j["journal_code"] for j in domain_collection["journals"]]
    log_collection_view(
        institution_id=institution_id,
        domain=domain_name,
        journals=journals,
        action="view",
    )

    return domain_collection
