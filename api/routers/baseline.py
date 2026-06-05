"""
/baseline endpoint - plain vector search comparison.

Uses the same entity_enriched corpus as /ask but with no enrichment:
pure cosine-similarity retrieval only — no BM25, no reranking, no entity linking.
Entity tag prefixes are stripped so the LLM sees plain text, not tagged text.

/baseline      → raw ranked chunks (for inspection)
/baseline/ask  → same retrieval + GPT synthesis (AskResponse shape)
                 Same LLM, same prompt as /ask — only the retrieval differs.
"""

import json as _json
from fastapi import APIRouter, HTTPException
from ..models import SearchRequest, AskRequest, AskResponse, CitedSource, SourceSection
from ..services.search_service import embed_query
from ..services.clients import get_chroma, get_openai
_BASELINE_SYSTEM_PROMPT = """You are a scientific research assistant. Answer the question using the provided sources.
- Use inline citations [1], [2] for every factual claim
- If multiple papers support a point, cite all of them
- Use precise scientific language
- Do NOT start with "Based on the sources" — answer directly
- Do NOT fabricate information not in the sources"""
from governance.license_service import check_license, load_config, get_journal_code

router = APIRouter(prefix="/baseline", tags=["baseline"])


@router.post("")
def baseline_search(req: SearchRequest):
    chroma = get_chroma()
    try:
        col = chroma.get_collection("html_scrape")
    except Exception:
        raise HTTPException(status_code=500, detail="html_scrape collection not found")

    q_embed = embed_query(req.query)
    res = col.query(query_embeddings=[q_embed], n_results=req.top_k)

    hits = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i]
        hits.append({
            "rank": i + 1,
            "distance": round(res["distances"][0][i], 4),
            "source": meta.get("source", ""),
            "title": meta.get("title", ""),
            "section": meta.get("section", ""),
            "chunk_type": meta.get("type", "text"),
            "text": res["documents"][0][i],
        })

    return {"query": req.query, "hits": hits}


@router.post("/ask", response_model=AskResponse)
def baseline_ask(req: AskRequest):
    """Plain vector-only search + GPT synthesis using entity_enriched corpus.
    Same licensed articles as /ask, but no BM25, no reranking, no entity linking.
    Entity tag prefixes are stripped so the LLM sees plain text only.
    """
    config = load_config()
    if req.institution_id not in config["institutions"]:
        raise HTTPException(status_code=404, detail="Institution not found")

    chroma = get_chroma()
    try:
        col = chroma.get_collection("entity_enriched")
    except Exception:
        raise HTTPException(status_code=500, detail="entity_enriched collection not found")

    q_embed = embed_query(req.query)
    fetch_n = min(req.top_k * 3, 30)
    res = col.query(query_embeddings=[q_embed], n_results=fetch_n)

    if not res["ids"][0]:
        return AskResponse(query=req.query, answer="No accessible results found for this query.", sources=[])

    # Same license filter as /ask
    allowed: list[dict] = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i]
        decision = check_license(req.institution_id, meta)
        if decision["decision"] != "NO_ACCESS":
            allowed.append({"text": res["documents"][0][i], "metadata": meta})
        if len(allowed) >= req.top_k:
            break

    if not allowed:
        return AskResponse(query=req.query, answer="No accessible results found for this query.", sources=[])

    # Group by source paper
    groups: dict[str, list[dict]] = {}
    for hit in allowed:
        src = hit["metadata"].get("source", "unknown")
        groups.setdefault(src, []).append(hit)

    # Build context block + CitedSource list (plain text — strip entity tag prefixes)
    context_parts = []
    sources = []
    for cid, (source, hits) in enumerate(groups.items(), start=1):
        first_meta = hits[0]["metadata"]
        title = first_meta.get("title", "Untitled")
        year = first_meta.get("publication_date", "")[:4] if first_meta.get("publication_date") else ""
        doi = first_meta.get("doi", "")
        journal = get_journal_code(first_meta)

        sections = []
        chunk_texts = []
        for hit in hits:
            section = hit["metadata"].get("section", "other")
            # Strip entity tag prefix — baseline sees plain text, not tagged text
            text = hit["text"]
            if "\n\n" in text:
                prefix, body = text.split("\n\n", 1)
                if prefix.startswith("["):
                    text = body
            sections.append(SourceSection(section=section, chunk_type="text", text=text))
            chunk_texts.append(f"  [{section}] {text}")

        sources.append(CitedSource(
            citation_id=cid,
            source=source,
            title=title,
            journal_code=journal,
            year=year,
            doi=doi,
            sections=sections,
        ))
        context_parts.append(f"[{cid}] {title} ({source}, {year})\n" + "\n".join(chunk_texts))

    context_block = "\n\n".join(context_parts)
    user_prompt = f"Question: {req.query}\n\nSources:\n{context_block}\n\nWrite a comprehensive answer with inline citations."

    client = get_openai()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    return AskResponse(
        query=req.query,
        answer=completion.choices[0].message.content.strip(),
        sources=sources,
    )


@router.post("/webai", response_model=AskResponse)
def webai_ask(req: AskRequest):
    """General web AI — no document context, pure LLM knowledge only.
    Simulates what ChatGPT / Gemini / Perplexity returns without
    access to the publisher's specific licensed articles.
    """
    client = get_openai()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a scientific research assistant. Answer the question using your "
                    "general training knowledge. Do not invent citations. If you reference "
                    "published work, say so in general terms (e.g. 'studies show') but do not "
                    "fabricate paper titles or authors. Be accurate but acknowledge when "
                    "specific recent or niche findings may lie beyond your training data."
                ),
            },
            {"role": "user", "content": req.query},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return AskResponse(
        query=req.query,
        answer=completion.choices[0].message.content.strip(),
        sources=[],
    )
