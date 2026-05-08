from fastapi import APIRouter, HTTPException
from ..models import InstitutionSummary, InstitutionsResponse, JournalsResponse, JournalInfo
from governance.license_service import get_institution_summary, load_config

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("", response_model=InstitutionsResponse)
def list_institutions():
    config = load_config()
    institutions = [
        InstitutionSummary(**get_institution_summary(iid))
        for iid in config["institutions"]
    ]
    return InstitutionsResponse(institutions=institutions)


@router.get("/{institution_id}", response_model=InstitutionSummary)
def get_institution(institution_id: str):
    config = load_config()
    if institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")
    return InstitutionSummary(**get_institution_summary(institution_id))
