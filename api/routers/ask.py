"""
/ask endpoint - RAG answer synthesis.

Retrieves top-k chunks via the enriched pipeline, groups them by source paper,
sends everything to GPT-4o-mini for a synthesized answer with inline citations,
and returns the answer + structured source list.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models import (
    AskRequest, AskResponse, CitedSource, SourceSection,
    LicenseDecision, ChunkMetadata,
)
from ..services.search_service import embed_query, hybrid_search, fetch_linked_figures
from ..services.reranker import rerank
from ..services.clients import get_openai
from governance.license_service import check_license, load_config, get_journal_code
from .attribution import log_event, log_blocked_event

router = APIRouter(prefix="/ask", tags=["ask"])

CHUNKS_DIR = Path(__file__).parent.parent.parent / "chunks"

# Lower rank = more specific/trustworthy type. Used to resolve duplicate entity text.
_TYPE_RANK: dict[str, int] = {
    "GENE": 1, "PROTEIN": 2, "RNA": 3, "ENZYME": 4,
    "DISEASE": 5, "CHEMICAL": 6, "DRUG": 7, "COMPOUND": 8,
    "CELL_LINE": 9, "VIRUS": 10, "ORGANISM": 11,
    "ANATOMY": 12, "BIOLOGICAL_PROCESS": 13, "SIGNALING_PATHWAY": 14,
    "ELEMENT": 15,
    "METHOD": 20, "TECHNOLOGY": 21, "SOFTWARE": 22, "TOOL": 23,
    "CONCEPT": 30, "ENTITY": 31, "OTHER": 32,
}

def _ent_score(ent: dict) -> tuple:
    """Lower = better. Prefer ontology-linked first, then more specific type."""
    has_id = 0 if ent.get("id") else 1
    rank = _TYPE_RANK.get(ent.get("type", "OTHER"), 25)
    return (has_id, rank)


def _load_article_stats() -> dict[str, dict]:
    """Pre-load per-article stats and deduplicated entity lists from chunk files."""
    stats = {}
    for path in CHUNKS_DIR.glob("*_chunks.json"):
        try:
            data = json.loads(path.read_text())
            source = data.get("source_file", path.stem.replace("_chunks", "") + ".xml")
            # Deduplicate by text, keeping the most specific/ontology-linked type
            entity_map: dict[str, dict] = {}
            for chunk in data.get("processed_chunks", []):
                for ent in chunk.get("entities", []):
                    text = ent.get("text", "")
                    key = text.lower()
                    if not key or len(key) <= 2:
                        continue
                    candidate = {
                        "text": text,
                        "type": ent.get("type", "ENTITY"),
                        "id": ent.get("id"),
                        "ontology": ent.get("ontology"),
                    }
                    if key not in entity_map or _ent_score(candidate) < _ent_score(entity_map[key]):
                        entity_map[key] = candidate
            entities = list(entity_map.values())
            # Build chunk_id → {section_title, subsection_title} lookup
            chunk_titles = {}
            for chunk in data.get("processed_chunks", []):
                cid = chunk.get("id")
                if cid:
                    chunk_titles[cid] = {
                        "section_title": chunk.get("section_title") or "",
                        "subsection_title": chunk.get("subsection_title") or "",
                    }

            stats[source] = {
                "total_entities": data.get("total_entities", 0),
                "total_relations": data.get("total_relations", 0),
                "entities": entities,
                "chunk_titles": chunk_titles,
            }
        except Exception:
            pass
    return stats

_ARTICLE_STATS = _load_article_stats()


def _group_by_source(hits: list[dict]) -> dict[str, list[dict]]:
    """Group hits by source article."""
    groups: dict[str, list[dict]] = {}
    for hit in hits:
        src = hit["metadata"].get("source", "unknown")
        groups.setdefault(src, []).append(hit)
    return groups


def _build_context_block(
    groups: dict[str, list[dict]],
    license_map: dict[str, dict],
    journal_config: dict,
) -> tuple[str, list[CitedSource]]:
    """Build the context string for the LLM and the CitedSource list."""
    context_parts = []
    sources = []

    for cid, (source, hits) in enumerate(groups.items(), start=1):
        first_meta = hits[0]["metadata"]
        title = first_meta.get("title", "Untitled")
        # Use license_service DOI-aware journal code extraction
        journal = get_journal_code(first_meta)
        year = first_meta.get("publication_date", "")[:4] if first_meta.get("publication_date") else ""
        doi = first_meta.get("doi", "")

        lic = license_map.get(source, {})
        license_decision = lic.get("decision", "ALLOWED")
        publisher = journal_config.get(journal, {}).get("publisher", "")

        article_stats = _ARTICLE_STATS.get(source, {})
        source_entities = article_stats.get("entities", [])
        chunk_title_map = article_stats.get("chunk_titles", {})

        # Count entities from the retrieved chunks only (query-specific, not article total)
        entity_count = 0
        sections = []
        chunk_texts = []
        for hit in hits:
            meta = hit["metadata"]
            section = meta.get("section", "other") or "other"
            chunk_type = meta.get("type", "text")
            text_snippet = hit["text"]

            ents_raw = meta.get("entities", "[]")
            try:
                ents = json.loads(ents_raw) if isinstance(ents_raw, str) else (ents_raw or [])
                entity_count += len(ents)
            except Exception:
                pass

            # Resolve actual section/subsection heading from chunk JSON files
            raw_chunk_id = hit["id"].split("::", 1)[-1] if "::" in hit["id"] else ""
            titles = chunk_title_map.get(raw_chunk_id, {})

            sections.append(SourceSection(
                section=section,
                chunk_type=chunk_type,
                text=text_snippet,
                section_title=titles.get("section_title", ""),
                subsection_title=titles.get("subsection_title", ""),
            ))
            chunk_texts.append(f"  [{section}] {text_snippet}")

        # Add linked figures (via figure_refs on text chunks)
        # Only include figures that the retrieved text explicitly references — no fallback dump
        linked_map = fetch_linked_figures(hits)
        added_fig_ids: set[str] = set()
        for hit in hits:
            for fig in linked_map.get(hit["id"], []):
                if fig["id"] not in added_fig_ids:
                    added_fig_ids.add(fig["id"])
                    sections.append(SourceSection(
                        section=fig["type"],
                        chunk_type=fig["type"],
                        text=fig["text"],
                    ))
                    chunk_texts.append(f"  [{fig['type']}] {fig['text']}")

        sources.append(CitedSource(
            citation_id=cid,
            source=source,
            title=title,
            journal_code=journal,
            year=year,
            doi=doi,
            sections=sections,
            license_decision=license_decision,
            publisher=publisher,
            entity_count=entity_count,
            relation_count=0,
            entities=source_entities,
        ))

        # Compact entity summary — gives LLM types + ontology IDs to reference
        entity_summary = ""
        if source_entities:
            parts = []
            for e in source_entities[:30]:
                label = e["text"]
                etype = e.get("type", "")
                eid = e.get("id", "")
                ontology = e.get("ontology", "")
                detail = etype
                if eid:
                    detail += f" · {ontology + ':' if ontology else ''}{eid}"
                parts.append(f"{label} [{detail}]" if detail else label)
            entity_summary = "  Entities: " + ", ".join(parts) + "\n"

        context_parts.append(
            f"[{cid}] {title} ({source}, {year})\n"
            + entity_summary
            + "\n".join(chunk_texts)
        )

    return "\n\n".join(context_parts), sources


SYSTEM_PROMPT = """You are a scientific research assistant with access to entity-enriched research articles.

Each source you receive includes:
- The section each passage came from (Results, Methods, Introduction, Discussion, etc.)
- A list of named scientific entities extracted from that article — each with its type (GENE, PROTEIN, DISEASE, BIOLOGICAL_PROCESS, DRUG, CHEMICAL, etc.) and, where available, a database ID (UniProt, MeSH, ChEBI, NCBI Gene)

Use this enriched structure to write a substantively better answer than plain text retrieval would produce:
- Name entities precisely with their type when it clarifies meaning: "GPX4 (protein)" not just "GPX4"
- Include database IDs for key entities when available: "GPX4 (UniProt P36969)", "RSL3 (ChEBI:138488)"
- Reference section provenance when it adds weight: "The Results section of [1] demonstrates...", "Methods in [2] describe..."
- When the same entity appears across multiple papers, synthesise confidently: "Three studies [1][2][3] confirm that GPX4 inhibition triggers ferroptosis"
- Distinguish gene-level from protein-level evidence where both appear

Rules:
- Every factual claim must have at least one citation [1], [2]
- Cite all supporting papers for a point: [1][3] not just [1]
- Do NOT start with "Based on the sources" — answer directly
- Do NOT fabricate information not in the sources
- If sources partially answer the query, state what is known and note the gap"""


@router.post("", response_model=AskResponse)
def ask(req: AskRequest):
    config = load_config()
    if req.institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")

    # Retrieve via enriched pipeline
    q_embed = embed_query(req.query)
    fetch_n = min(req.top_k * 3, 30)
    raw_hits = hybrid_search(req.query, q_embed, n=fetch_n)
    raw_hits = rerank(raw_hits, query=req.query, section_boost=True, recency_weight=0.10)

    institution_name = config["institutions"].get(req.institution_id, {}).get("name", req.institution_id)

    # License filter — collect both allowed and blocked hits
    allowed_hits, blocked_hits = [], []
    for hit in raw_hits:
        decision = check_license(req.institution_id, hit["metadata"])
        hit["_license"] = decision
        if decision["decision"] != "NO_ACCESS":
            allowed_hits.append(hit)
        else:
            blocked_hits.append(hit)
        if len(allowed_hits) >= req.top_k:
            break

    if not allowed_hits:
        log_blocked_event(
            query=req.query,
            institution_id=req.institution_id,
            institution_name=institution_name,
            blocked_hits=blocked_hits,
            journal_config=config.get("journals", {}),
        )
        return AskResponse(query=req.query, answer="No accessible results found for this query.", sources=[])

    # Group by source paper
    groups = _group_by_source(allowed_hits)
    license_map = {
        hit["metadata"].get("source", ""): hit["_license"]
        for hit in allowed_hits
    }
    context_block, sources = _build_context_block(groups, license_map, config.get("journals", {}))

    # Synthesize answer via LLM
    client = get_openai()
    user_prompt = f"Question: {req.query}\n\nSources:\n{context_block}\n\nWrite a comprehensive answer with inline citations."

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    answer = completion.choices[0].message.content.strip()

    # Write attribution event — one entry per query, one record per cited source
    log_event(
        query=req.query,
        institution_id=req.institution_id,
        institution_name=institution_name,
        sources=[s.model_dump() for s in sources],
    )

    return AskResponse(
        query=req.query,
        answer=answer,
        sources=sources,
    )
