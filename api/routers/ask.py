"""
/ask endpoint - RAG answer synthesis.

Retrieves top-k chunks via the enriched pipeline, groups them by source paper,
sends everything to GPT-4o-mini for a synthesized answer with inline citations,
and returns the answer + structured source list.
"""

import json
from fastapi import APIRouter, HTTPException
from ..models import (
    AskRequest, AskResponse, CitedSource, SourceSection,
    LicenseDecision, ChunkMetadata,
)
from ..services.search_service import embed_query, hybrid_search, fetch_linked_figures
from ..services.reranker import rerank
from ..services.clients import get_openai
from governance.license_service import check_license, load_config

router = APIRouter(prefix="/ask", tags=["ask"])


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
        journal = first_meta.get("journal_code", first_meta.get("source", "")[:2]) if "journal_code" in first_meta else source.split("_")[0] if "_" in source else ""
        year = first_meta.get("publication_date", "")[:4] if first_meta.get("publication_date") else ""
        doi = first_meta.get("doi", "")

        lic = license_map.get(source, {})
        license_decision = lic.get("decision", "ALLOWED")
        publisher = journal_config.get(journal, {}).get("publisher", "")

        sections = []
        chunk_texts = []
        for hit in hits:
            meta = hit["metadata"]
            section = meta.get("section", "other")
            chunk_type = meta.get("type", "text")
            text_snippet = hit["text"]

            sections.append(SourceSection(
                section=section,
                chunk_type=chunk_type,
                text=text_snippet,
            ))
            chunk_texts.append(f"  [{section}] {text_snippet}")

        # Add linked figures as sections too
        linked_map = fetch_linked_figures(hits)
        for hit in hits:
            for fig in linked_map.get(hit["id"], []):
                fig_text = fig["text"]
                sections.append(SourceSection(
                    section=fig["type"],
                    chunk_type=fig["type"],
                    text=fig_text,
                ))
                chunk_texts.append(f"  [{fig['type']}] {fig_text}")

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
        ))

        context_parts.append(
            f"[{cid}] {title} ({source}, {year})\n" + "\n".join(chunk_texts)
        )

    return "\n\n".join(context_parts), sources


SYSTEM_PROMPT = """You are a scientific research assistant. You synthesize information from research articles into clear, comprehensive answers.

Rules:
- Write a complete, well-structured answer using the provided sources
- Use inline citations like [1], [2] to reference source papers
- Every factual claim must have a citation
- If multiple papers support the same point, cite all of them: [1][3]
- Use precise scientific language but keep it readable
- Include specific values, gene names, protein names when available in the sources
- Structure longer answers with clear paragraphs
- Do NOT start with "Based on the sources" or similar - just answer directly
- Do NOT make up information not present in the sources
- If the sources don't fully answer the query, say what is known and note the gap"""


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

    # License filter
    allowed_hits = []
    for hit in raw_hits:
        decision = check_license(req.institution_id, hit["metadata"])
        if decision["decision"] != "NO_ACCESS":
            hit["_license"] = decision
            allowed_hits.append(hit)
        if len(allowed_hits) >= req.top_k:
            break

    if not allowed_hits:
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

    return AskResponse(
        query=req.query,
        answer=answer,
        sources=sources,
    )
