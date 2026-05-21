"""
NER + Ontology Linking - two-step approach

Step 1: GPT-4o-mini extracts entity names + types (domain-aware prompts)
Step 2: NCBI/NLM/EBI/Cellosaurus APIs resolve IDs

  GENE / PROTEIN  → NCBI Gene        (e.g., METTL3 → 56339)
  DISEASE         → MeSH             (e.g., Leukemia → D007938)
                    ↳ fallback: OLS Disease Ontology (e.g., theileriasis → DOID:3733)
  CHEMICAL / DRUG → MeSH             (e.g., Hepes → D006531)
                    ↳ fallback: OLS ChEBI  (e.g., m6A → CHEBI:21891)
  SPECIES/ORGANISM→ NCBI Taxonomy    (e.g., Theileria annulata → 5874)
  CELL_LINE       → Cellosaurus      (e.g., HeLa → CVCL_0030)

Non-biological types (METHOD, TECHNOLOGY, CONCEPT, etc.) are
extracted by GPT but not linked to ontologies - no suitable general
registry exists for them.

Entity format (unified):
  {
    "text":     "METTL3",
    "type":     "GENE",
    "id":       "56339",         # None if not resolved
    "ontology": "NCBI Gene",     # None if not resolved
    "source":   "gpt"
  }
"""

import json
import time
import os
import requests
from openai import OpenAI

# ─── Config ──────────────────────────────────────────────────────────────────

NCBI_BASE         = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MESH_BASE         = "https://id.nlm.nih.gov/mesh"
MESH_SPARQL       = "https://id.nlm.nih.gov/mesh/sparql"
OLS_BASE          = "https://www.ebi.ac.uk/ols4/api"
CELLOSAURUS_BASE  = "https://api.cellosaurus.org"
NCBI_DELAY        = 0.35   # stay within 3 req/sec free-tier limit

# Optional: set NCBI_API_KEY in .env for 10 req/sec
_NCBI_API_KEY = os.environ.get("NCBI_API_KEY")

# GPT domain hints per journal ID
_BIO_HINT    = "biomedical. Extract: GENE, PROTEIN, DISEASE, CHEMICAL, DRUG, COMPOUND, CELL_LINE, ORGANISM, ENZYME, BIOLOGICAL_PROCESS, SIGNALING_PATHWAY, ANATOMY, VIRUS, RNA"
_CLINICAL_HINT = "clinical/medical. Extract: DISEASE, DRUG, CHEMICAL, GENE, PROTEIN, ANATOMY, BIOLOGICAL_PROCESS, CELL_LINE, ORGANISM. Do NOT use GENE or CELL_LINE for imaging parameters or scores."

_GPT_DOMAIN_HINTS: dict[str, str] = {
    # Biochemical / molecular biology
    "BJ":      _BIO_HINT,
    "REDOX":   _BIO_HINT,
    "CELREP":  _BIO_HINT,   # Cell Reports
    "GENDIS":  _BIO_HINT,   # Genes & Diseases
    # Pharmacology / pharmaceutical
    "BIOPHA":  _BIO_HINT,   # Biomedicine & Pharmacotherapy
    "AJPS":    _BIO_HINT,   # Asian Journal of Pharmaceutical Sciences
    # Clinical / oncology
    "CCC":     _CLINICAL_HINT,
    "CTARC":   _CLINICAL_HINT,   # Cancer Treatment and Research Communications
    "CLNVES":  _CLINICAL_HINT,   # Clinical Investigation
    # Other domains
    "PLAS":  "project management / social science. Extract: THEORY, METHOD, CONCEPT, FRAMEWORK, TOOL",
    "ESR":   "energy systems / engineering. Extract: TECHNOLOGY, METHOD, LOCATION, CONCEPT, METRIC",
}
_GPT_DEFAULT_HINT = "scientific. Extract: GENE, PROTEIN, DISEASE, CHEMICAL, CONCEPT, METHOD, ENTITY"

# Entity types that support ID resolution
_RESOLVABLE = {"GENE", "PROTEIN", "DISEASE", "CHEMICAL", "DRUG", "SPECIES", "ORGANISM", "CELL_LINE"}

# In-memory cache: (entity_text_lower, type) → {"id":..., "ontology":...} | None
_id_cache: dict[tuple[str, str], dict | None] = {}

# Cache for MeSH broader terms: mesh_id → [label, ...]
_broader_cache: dict[str, list[str]] = {}


# ─── Step 1: GPT Entity Extraction ───────────────────────────────────────────

def gpt_extract_entities(client: OpenAI, chunk: dict) -> list[dict]:
    """Use GPT-4o-mini to extract named entities. Domain prompt adapts to journal."""
    meta    = chunk.get("metadata", {})
    journal = meta.get("journal_id", "").upper()
    text    = chunk.get("text", "")[:800]

    domain_hint = _GPT_DOMAIN_HINTS.get(journal, _GPT_DEFAULT_HINT)

    prompt = f"""You are an entity extractor for {domain_hint} articles.

Text:
{text}

Extract up to 8 important named entities. Return JSON array only, no extra text:
[{{"text": "entity name", "type": "ENTITY_TYPE"}}, ...]

Rules:
- Only clearly named entities (not generic words like "study" or "method")
- Use CELL_LINE for cell lines (e.g. HeLa, HEK293, TBL20), not ORGANISM
- Use the entity types listed above
- Return [] if no clear entities"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        raw = response.choices[0].message.content.strip()
        raw = raw.strip("` \n").removeprefix("json").strip()
        parsed = json.loads(raw)
        return [
            {"text": e["text"], "type": e["type"], "id": None, "ontology": None, "source": "gpt"}
            for e in parsed
            if isinstance(e, dict) and e.get("text") and e.get("type")
        ]
    except Exception:
        return []


# ─── Step 2: Ontology ID Resolution ──────────────────────────────────────────

def _ncbi_gene_id(name: str) -> dict | None:
    """Resolve gene/protein name → NCBI Gene ID. Tries human first, then any organism."""
    for organism in ["Homo sapiens", None]:
        term = f"{name}[gene name]"
        if organism:
            term += f" AND {organism}[Organism]"
        params: dict = {"db": "gene", "term": term, "retmax": 1, "retmode": "json"}
        if _NCBI_API_KEY:
            params["api_key"] = _NCBI_API_KEY
        try:
            time.sleep(NCBI_DELAY)
            r = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=10)
            ids = r.json()["esearchresult"]["idlist"]
            if ids:
                return {"id": ids[0], "ontology": "NCBI Gene"}
        except Exception:
            pass
    return None


def _mesh_descriptor_id(name: str) -> dict | None:
    """Resolve disease/chemical name → MeSH descriptor D-number."""
    for match in ("exact", "contains"):
        try:
            time.sleep(NCBI_DELAY)
            r = requests.get(
                f"{MESH_BASE}/lookup/descriptor",
                params={"label": name, "match": match, "limit": 1},
                timeout=10,
            )
            results = r.json()
            if results:
                uri = results[0]["resource"]
                mesh_id = uri.rstrip("/").split("/")[-1]
                if mesh_id.startswith("D"):
                    return {"id": mesh_id, "ontology": "MeSH"}
        except Exception:
            pass
    return None


def _ols_chebi_id(name: str) -> dict | None:
    """Resolve chemical name or abbreviation → ChEBI ID via OLS.
    Handles abbreviations like 'm6A' that are registered as synonyms in ChEBI."""
    for exact in ("true", "false"):
        try:
            time.sleep(NCBI_DELAY)
            r = requests.get(
                f"{OLS_BASE}/search",
                params={"q": name, "ontology": "chebi", "type": "class", "exact": exact, "rows": 1},
                timeout=10,
            )
            docs = r.json()["response"]["docs"]
            if docs:
                obo_id = docs[0].get("obo_id", "")   # e.g. "CHEBI:21891"
                if obo_id.startswith("CHEBI:"):
                    return {"id": obo_id, "ontology": "ChEBI"}
        except Exception:
            pass
    return None


def _ols_doid_id(name: str) -> dict | None:
    """Resolve disease name → Disease Ontology ID via OLS.
    Used as fallback when MeSH has no descriptor for specific sub-terms."""
    try:
        time.sleep(NCBI_DELAY)
        r = requests.get(
            f"{OLS_BASE}/search",
            params={"q": name, "ontology": "doid", "type": "class", "rows": 1},
            timeout=10,
        )
        docs = r.json()["response"]["docs"]
        if docs:
            obo_id = docs[0].get("obo_id", "")   # e.g. "DOID:3733"
            if obo_id.startswith("DOID:"):
                return {"id": obo_id, "ontology": "Disease Ontology"}
    except Exception:
        pass
    return None


def _cellosaurus_id(name: str) -> dict | None:
    """Resolve cell line name → Cellosaurus CVCL accession (e.g. CVCL_0030)."""
    try:
        time.sleep(NCBI_DELAY)
        r = requests.get(
            f"{CELLOSAURUS_BASE}/search/cell-line",
            params={"q": name, "fields": "id,ac", "format": "json"},
            timeout=10,
        )
        cell_lines = r.json().get("Cellosaurus", {}).get("cell-line-list", [])
        if cell_lines:
            accessions = cell_lines[0].get("accession-list", [])
            primary = next((a["value"] for a in accessions if a.get("type") == "primary"), None)
            if primary:
                return {"id": primary, "ontology": "Cellosaurus"}
    except Exception:
        pass
    return None


def _ncbi_taxonomy_id(name: str) -> dict | None:
    """Resolve species/organism name → NCBI Taxonomy ID."""
    params: dict = {
        "db": "taxonomy",
        "term": f"{name}[scientific name]",
        "retmax": 1,
        "retmode": "json",
    }
    if _NCBI_API_KEY:
        params["api_key"] = _NCBI_API_KEY
    try:
        time.sleep(NCBI_DELAY)
        r = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=10)
        ids = r.json()["esearchresult"]["idlist"]
        if ids:
            return {"id": ids[0], "ontology": "NCBI Taxonomy"}
    except Exception:
        pass
    return None


def _mesh_broader_terms(mesh_id: str) -> list[str]:
    """Walk one level up the MeSH hierarchy via SPARQL.

    Returns labels of direct broader descriptors (e.g. "Leukemia" → ["Neoplasms by Histologic Type"]).
    Uses meshv:broaderDescriptor which is the standard MeSH parent relation.
    """
    if mesh_id in _broader_cache:
        return _broader_cache[mesh_id]

    query = f"""
PREFIX mesh: <https://id.nlm.nih.gov/mesh/>
PREFIX meshv: <https://id.nlm.nih.gov/mesh/vocab#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label WHERE {{
  mesh:{mesh_id} meshv:broaderDescriptor ?parent .
  ?parent rdfs:label ?label .
  FILTER(lang(?label) = 'en')
}}
"""
    try:
        time.sleep(NCBI_DELAY)
        r = requests.get(
            MESH_SPARQL,
            params={"query": query, "format": "JSON"},
            timeout=10,
        )
        bindings = r.json()["results"]["bindings"]
        terms = [b["label"]["value"] for b in bindings]
        _broader_cache[mesh_id] = terms
        return terms
    except Exception:
        _broader_cache[mesh_id] = []
        return []


def _resolve_id(text: str, entity_type: str) -> dict | None:
    """Look up ontology ID for an entity by type. Cached per (text, type) pair.

    Resolution order:
      GENE/PROTEIN  → NCBI Gene
      DISEASE       → MeSH → OLS Disease Ontology (fallback)
      CHEMICAL/DRUG → MeSH → OLS ChEBI (fallback)
      CELL_LINE     → Cellosaurus
      SPECIES/ORGANISM → NCBI Taxonomy
    """
    cache_key = (text.lower(), entity_type)
    if cache_key in _id_cache:
        return _id_cache[cache_key]

    result: dict | None = None

    if entity_type in ("GENE", "PROTEIN"):
        result = _ncbi_gene_id(text)

    elif entity_type == "DISEASE":
        result = _mesh_descriptor_id(text) or _ols_doid_id(text)
        if result and result.get("ontology") == "MeSH":
            broader = _mesh_broader_terms(result["id"])
            if broader:
                result = {**result, "broader_terms": broader}

    elif entity_type in ("CHEMICAL", "DRUG"):
        result = _mesh_descriptor_id(text) or _ols_chebi_id(text)
        if result and result.get("ontology") == "MeSH":
            broader = _mesh_broader_terms(result["id"])
            if broader:
                result = {**result, "broader_terms": broader}

    elif entity_type == "CELL_LINE":
        result = _cellosaurus_id(text)

    elif entity_type in ("SPECIES", "ORGANISM"):
        result = _ncbi_taxonomy_id(text)

    # METHOD, TECHNOLOGY, CONCEPT, etc. → no ontology

    _id_cache[cache_key] = result
    return result


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def enrich_entities(client: OpenAI | None, chunk: dict) -> list[dict]:
    """
    Extract entities + resolve ontology IDs for a chunk.

    Args:
        client: OpenAI client. Pass None for dry-run (returns []).
        chunk:  Chunk dict with "text" and "metadata.journal_id".

    Returns:
        List of entity dicts with id/ontology filled in where resolved.
    """
    if client is None:
        return []

    # Step 1 - extract entity names + types via GPT
    entities = gpt_extract_entities(client, chunk)
    if not entities:
        return []

    # Step 2 - resolve IDs for supported types
    for e in entities:
        if e["type"] in _RESOLVABLE:
            resolved = _resolve_id(e["text"], e["type"])
            if resolved:
                e.update(resolved)

    return entities


# ─── Formatting ──────────────────────────────────────────────────────────────

def tag_string(entities: list[dict]) -> str:
    """
    Format entity list as a tag string to prepend to chunk text.

    With ID:    [GENE: METTL3 | NCBI Gene:56339]
    Without ID: [METHOD: CRISPR-Cas9]
    """
    if not entities:
        return ""
    tags = []
    for e in entities:
        eid = e.get("id")
        ont = e.get("ontology")
        if eid and ont:
            tags.append(f"[{e['type']}: {e['text']} | {ont}:{eid}]")
        else:
            tags.append(f"[{e['type']}: {e['text']}]")
    return " ".join(tags) + "\n\n"
