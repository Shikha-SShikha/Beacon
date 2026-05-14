"""
analytics.py — Usage analytics and metered tracking endpoints

Provides endpoints for viewing metered usage statistics per institution.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from ..services.attribution_service import get_usage_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


class UsageStats(BaseModel):
    by_domain: dict[str, int]
    by_journal: dict[str, int]
    by_access_level: dict[str, int]
    total_accesses: int


@router.get("/usage/{institution_id}", response_model=UsageStats)
def get_institution_usage(institution_id: str):
    """
    Get metered usage statistics for an institution.

    Returns:
        - by_domain: count by research domain
        - by_journal: count by journal code
        - by_access_level: count by access level (FULL_TEXT, SNIPPET_ONLY, OPEN_ACCESS)
        - total_accesses: total number of articles accessed
    """
    stats = get_usage_stats(institution_id=institution_id)
    return UsageStats(**stats)


@router.get("/usage", response_model=UsageStats)
def get_global_usage():
    """Get global metered usage statistics across all institutions."""
    stats = get_usage_stats()
    return UsageStats(**stats)
