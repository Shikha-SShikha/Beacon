import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routers import institutions, search, citation, ask, baseline, analytics, collections, attribution
from .models import JournalsResponse, JournalInfo
from governance.license_service import load_config

app = FastAPI(title="Beacon API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(institutions.router)
app.include_router(search.router)
app.include_router(citation.router)
app.include_router(ask.router)
app.include_router(baseline.router)
app.include_router(analytics.router)
app.include_router(collections.router)
app.include_router(attribution.router)


@app.get("/journals", response_model=JournalsResponse, tags=["journals"])
def get_journals():
    config = load_config()
    return JournalsResponse(
        journals={
            code: JournalInfo(**info)
            for code, info in config["journals"].items()
        }
    )


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Serve React build in production
_ui_dist = Path(__file__).parent.parent / "beacon-ui" / "dist"
if _ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_ui_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        candidate = _ui_dist / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_ui_dist / "index.html"))
