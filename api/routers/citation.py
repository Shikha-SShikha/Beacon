from fastapi import APIRouter, Query
from pydantic import BaseModel
from ..services.citation_service import get_context, get_foundational_for_sources

router = APIRouter(prefix="/citation", tags=["citation"])


class FoundationalRequest(BaseModel):
    sources: list[str]


@router.get("/context")
def citation_context(source: str = Query(..., description="Source filename, e.g. BJ_100828.xml")):
    return get_context(source)


@router.post("/foundational")
def foundational_papers(req: FoundationalRequest):
    return {"foundational": get_foundational_for_sources(req.sources)}
