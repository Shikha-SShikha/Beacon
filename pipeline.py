"""
Elsevier XML → Enriched Chunks Pipeline

Processes Elsevier DTD v5.7 XML articles and produces AI-enriched chunks
ready for vector database ingestion.

Usage:
    python pipeline.py <xml_file> [--output <output.json>]
"""

import re
import json
import argparse
import sys
import os
from pathlib import Path
from lxml import etree
from openai import OpenAI
from ner import enrich_entities, tag_string
from relations import extract_relations

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# ─── XML Helpers ────────────────────────────────────────────────────────────

def local(tag) -> str:
    """Return local part of a tag name (strips namespace prefix or URI).
    Returns empty string for non-element nodes (comments, entities, PIs).
    """
    if callable(tag):  # _Entity, _Comment, _ProcessingInstruction nodes
        return ""
    if "}" in tag:
        return tag.split("}")[-1]
    if ":" in tag:
        return tag.split(":")[-1]
    return tag


def find_local(el, *local_names) -> list:
    """Find direct children whose local tag name is in local_names."""
    names = set(local_names)
    return [c for c in el if local(c.tag) in names]


def find_local_recursive(el, *local_names) -> list:
    """Find all descendants whose local tag name is in local_names."""
    names = set(local_names)
    return [c for c in el.iter() if local(c.tag) in names]


def get_text(el) -> str:
    """Get all text content from an element, collapsing whitespace."""
    parts = []
    for node in el.iter():
        if callable(node.tag):  # skip _Entity, _Comment, _ProcessingInstruction
            if node.tail:
                parts.append(node.tail)
            continue
        loc = local(node.tag)
        if loc in ("float-anchor",):
            continue
        if node.text:
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    text = " ".join(parts)
    return " ".join(text.split()) if text else ""


def table_to_markdown(table_el) -> str:
    """Convert a CALS table (tgroup > thead/tbody > row > entry) to Markdown table format."""
    tgroup = next((c for c in table_el if local(c.tag) == "tgroup"), None)
    if tgroup is None:
        return get_text(table_el)

    headers = []
    rows = []
    for section in tgroup:
        loc = local(section.tag)
        if loc == "thead":
            for row in section:
                if local(row.tag) == "row":
                    headers = [get_text(e) for e in row if local(e.tag) == "entry"]
        elif loc == "tbody":
            for row in section:
                if local(row.tag) == "row":
                    cells = [get_text(e) for e in row if local(e.tag) == "entry"]
                    if cells:
                        rows.append(cells)

    if not headers and not rows:
        return ""

    lines = []
    if headers:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# ─── Parsing ────────────────────────────────────────────────────────────────

def load_xml(file_path: str) -> etree._Element:
    """Load Elsevier XML, stripping DOCTYPE entity declarations that block parsing."""
    with open(file_path, "rb") as f:
        content = f.read()
    # Remove internal DTD subset (entity declarations cause parse errors without the DTD)
    content = re.sub(rb"<!DOCTYPE[^[]*\[.*?\]>", b"", content, flags=re.DOTALL)
    parser = etree.XMLParser(recover=True, resolve_entities=False)
    return etree.fromstring(content, parser=parser)


def extract_metadata(root: etree._Element) -> dict:
    """Extract article-level metadata from <item-info> and <head>."""
    meta = {}

    # item-info: doi, pii, jid, aid
    item_info = next(iter(find_local(root, "item-info")), None)
    if item_info is not None:
        for child in item_info:
            loc = local(child.tag)
            if loc == "doi":
                meta["doi"] = child.text
            elif loc == "pii":
                meta["pii"] = child.text
            elif loc == "jid":
                meta["journal_id"] = child.text
            elif loc == "aid":
                meta["article_id"] = child.text

    # Support both <head> (standard Elsevier DTD) and <simple-head> (proof/mastercopy format)
    head = next(iter(find_local(root, "head", "simple-head")), None)
    if head is None:
        return meta

    for child in head:
        loc = local(child.tag)

        if loc == "title":
            meta["title"] = get_text(child)

        elif loc == "author-group":
            authors = []
            for au in find_local(child, "author"):
                given = next((get_text(c) for c in au if local(c.tag) == "given-name"), "")
                surname = next((get_text(c) for c in au if local(c.tag) == "surname"), "")
                name = f"{given} {surname}".strip()
                if name:
                    authors.append(name)
            meta["authors"] = authors

        elif loc == "date-accepted":
            y = child.get("year", "")
            m = child.get("month", "").zfill(2)
            d = child.get("day", "").zfill(2)
            if y:
                meta["publication_date"] = f"{y}-{m}-{d}"

        elif loc == "abstract":
            # Skip highlights abstract (class="author-highlights")
            if child.get("class") == "author-highlights":
                continue
            paras = find_local_recursive(child, "simple-para", "para")
            abstract_text = " ".join(get_text(p) for p in paras if get_text(p))
            # simple-head abstract: text is directly in the element
            if not abstract_text:
                abstract_text = get_text(child)
            if abstract_text:
                meta["abstract"] = abstract_text

        elif loc == "keywords":
            kws = find_local_recursive(child, "text")
            if kws:
                meta["keywords"] = [get_text(k) for k in kws if get_text(k)]
            else:
                # simple-head: keywords are direct text children
                kw_text = get_text(child)
                kw_text = re.sub(r"^Keywords?\s*:?\s*", "", kw_text, flags=re.IGNORECASE)
                meta["keywords"] = [k.strip() for k in kw_text.split() if k.strip()]

    return meta


def extract_section_chunks(root: etree._Element, metadata: dict) -> list[dict]:
    """
    Extract one chunk per top-level section.
    Nested subsections are folded into the parent's text with their title as a header.
    """
    body = next(iter(find_local(root, "body")), None)
    if body is None:
        return []

    ce_sections = next((c for c in body if local(c.tag) == "sections"), None)
    if ce_sections is None:
        return []

    chunks = []
    doi = metadata.get("doi", metadata.get("article_id", "unknown"))
    doi_safe = doi.replace("/", "-").replace(".", "-")

    for idx, section in enumerate(ce_sections):
        if local(section.tag) != "section":
            continue

        role = section.get("role") or "other"
        sec_id = section.get("id", f"sec{idx}")

        # Collect the section title from the top-level section
        title_el = next((c for c in section if local(c.tag) == "section-title"), None)
        section_title = get_text(title_el) if title_el is not None else role

        # Skip author-disclosure / credit sections
        if role == "author-disclosure":
            continue

        # Collect paragraph-level records from the section tree
        paragraphs = _collect_paragraphs(section, top_level=True)
        if not paragraphs:
            continue

        # Merge tiny paragraphs, then add 1-sentence overlap
        paragraphs = _merge_small_paragraphs(paragraphs)
        paragraphs = _add_overlap(paragraphs)

        # Normalise role
        norm_role = _normalise_role(role, section_title)

        for para_idx, para in enumerate(paragraphs):
            if not para["text"].strip():
                continue
            chunks.append({
                "chunk_id": f"article-{doi_safe}-{sec_id}-p{para_idx}",
                "type": "text",
                "section_type": norm_role,
                "section_title": section_title,
                "subsection_title": para["subsection_title"],
                "paragraph_index": para_idx,
                "parent_section_id": sec_id,
                "chunk_text": para["text"],
                "metadata": metadata,
            })

    return chunks


def _collect_paragraphs(section_el, top_level: bool = False,
                        subsection_title: str | None = None) -> list[dict]:
    """Recursively collect paragraphs as structured records.

    Returns a list of dicts, each with:
        text: paragraph text (subsection title prepended to first para of each subsection)
        subsection_title: name of the enclosing subsection, or None
    """
    paragraphs: list[dict] = []
    first_in_subsection = True

    for child in section_el:
        loc = local(child.tag)

        if loc == "section-title" and top_level:
            continue  # already captured by caller

        elif loc == "section-title":
            # Nested subsection title - store for context, handled on recursion
            continue

        elif loc == "para":
            text = get_text(child)
            if not text:
                continue
            # Prepend subsection header to the first paragraph of a subsection
            if subsection_title and first_in_subsection:
                text = f"### {subsection_title}\n\n{text}"
                first_in_subsection = False
            paragraphs.append({
                "text": text,
                "subsection_title": subsection_title,
            })

        elif loc == "section":
            # Nested section - get its title, then recurse
            nested_title_el = next(
                (c for c in child if local(c.tag) == "section-title"), None
            )
            nested_title = get_text(nested_title_el) if nested_title_el is not None else None
            paragraphs.extend(
                _collect_paragraphs(child, top_level=False,
                                    subsection_title=nested_title)
            )
        # ignore float-anchor, cross-ref, label etc.

    # Fallback: if section has direct text content but no <para> children,
    # treat the section's own text as a single paragraph.
    if not paragraphs:
        direct_text = get_text(section_el).strip()
        if direct_text:
            paragraphs.append({
                "text": direct_text,
                "subsection_title": subsection_title,
            })

    return paragraphs


def _normalise_role(role: str, title: str) -> str:
    title_lower = title.lower()
    role_lower = (role or "").lower()
    if "introduction" in role_lower or "introduction" in title_lower:
        return "introduction"
    if "method" in role_lower or "method" in title_lower or "material" in title_lower:
        return "methods"
    if "result" in role_lower or "result" in title_lower:
        return "results"
    if "discussion" in role_lower or "discussion" in title_lower:
        return "discussion"
    if "conclusion" in role_lower or "conclusion" in title_lower:
        return "conclusion"
    if role_lower in ("introduction", "materials-methods", "results", "conclusion"):
        return role_lower
    return "other"


def _merge_small_paragraphs(paragraphs: list[dict],
                            min_size: int = 200,
                            target_min: int = 300) -> list[dict]:
    """Merge consecutive tiny paragraphs in the same subsection.

    If a paragraph's text is shorter than *min_size* chars, merge it forward
    with the next paragraph(s) until the combined text exceeds *target_min*
    or the subsection changes.
    """
    if not paragraphs:
        return paragraphs

    merged: list[dict] = []
    acc_text = paragraphs[0]["text"]
    acc_sub = paragraphs[0]["subsection_title"]

    for para in paragraphs[1:]:
        same_sub = para["subsection_title"] == acc_sub
        if same_sub and len(acc_text) < min_size:
            acc_text = acc_text + "\n\n" + para["text"]
        else:
            merged.append({"text": acc_text, "subsection_title": acc_sub})
            acc_text = para["text"]
            acc_sub = para["subsection_title"]

    merged.append({"text": acc_text, "subsection_title": acc_sub})
    return merged


def _add_overlap(paragraphs: list[dict]) -> list[dict]:
    """Prepend the last sentence of the previous paragraph to each chunk.

    This creates a 1-sentence overlap between consecutive chunks within the
    same section, addressing cross-chunk dependency (failure mode B3).
    """
    if len(paragraphs) <= 1:
        return paragraphs

    result = [paragraphs[0]]
    for i in range(1, len(paragraphs)):
        prev_text = paragraphs[i - 1]["text"]
        curr = paragraphs[i]

        # Split previous text into sentences
        sentences = re.split(r'(?<=[.!?])\s+', prev_text.strip())
        if len(sentences) >= 2:
            last_sent = sentences[-1]
            curr = {
                "text": last_sent + " " + curr["text"],
                "subsection_title": curr["subsection_title"],
            }
        result.append(curr)

    return result


def extract_floats(root: etree._Element, metadata: dict) -> list[dict]:
    """
    Extract all figures and tables from <ce:floats>.
    Returns one item per figure/table with label, caption, and table text.
    """
    items = []
    floats_el = next((c for c in root if local(c.tag) == "floats"), None)
    if floats_el is None:
        return items

    for child in floats_el:
        loc = local(child.tag)

        if loc == "figure":
            label_el = next((c for c in child if local(c.tag) == "label"), None)
            caption_el = next((c for c in child if local(c.tag) == "caption"), None)
            label = get_text(label_el) if label_el is not None else child.get("id", "")
            caption = get_text(caption_el) if caption_el is not None else ""
            items.append({
                "id": child.get("id", label),
                "type": "figure",
                "label": label,
                "caption": caption,
                "content": None,
                "metadata": metadata,
            })

        elif loc == "table-wrap" or loc == "table":
            label_el = next((c for c in child if local(c.tag) == "label"), None)
            caption_el = next((c for c in child if local(c.tag) == "caption"), None)
            label = get_text(label_el) if label_el is not None else child.get("id", "")
            caption = get_text(caption_el) if caption_el is not None else ""
            table_text = table_to_markdown(child)
            items.append({
                "id": child.get("id", label),
                "type": "table",
                "label": label,
                "caption": caption,
                "content": table_text,
                "metadata": metadata,
            })

    return items


# ─── AI Enrichment ──────────────────────────────────────────────────────────

def generate_contextual_prefix(client: OpenAI, chunk: dict) -> str:
    """Generate a one-sentence contextual prefix for a text chunk."""
    meta = chunk["metadata"]
    first_author = meta.get("authors", ["Unknown"])[0] if meta.get("authors") else "Unknown"
    year = meta.get("publication_date", "")[:4] or "n.d."

    subsection = chunk.get('subsection_title') or "N/A"
    prompt = f"""Article: {meta.get('title', 'Unknown title')}
Journal: {meta.get('journal_id', '')}
First Author: {first_author}
Year: {year}
Section: {chunk['section_title']} ({chunk['section_type']})
Subsection: {subsection}

Paragraph text (first 400 chars):
{chunk['chunk_text'][:400]}

Write a single sentence (max 40 words) that contextualises this chunk for a reader using search. \
Start with "This [section_type] section from..." and end with what the chunk covers. \
Return only the sentence, no quotes, no extra text."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=120,
        messages=[
            {"role": "system", "content": "You generate concise contextual prefixes for scientific article chunks to improve retrieval quality."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def summarise_float(client: OpenAI, item: dict,
                    citing_texts: list[str] | None = None) -> str:
    """Generate a claim-extracting summary for a figure or table.

    For tables: the finding is derived from the actual table content (rows/values).
    For figures: the caption alone is used unless citing_texts are provided — passages
    from the article that reference this figure and typically state its finding explicitly.
    """
    meta = item["metadata"]
    kind = item["type"].capitalize()
    label = item["label"]
    caption = item["caption"]
    content = item.get("content") or ""

    content_block = f"\nTable content (excerpt):\n{content[:600]}" if content else ""

    citing_block = ""
    if citing_texts:
        excerpts = "\n---\n".join(t[:500] for t in citing_texts)
        citing_block = (
            f"\nParagraph(s) from the article that cite this {item['type']} "
            f"(authors typically state the finding here):\n{excerpts}"
        )

    prompt = f"""Article: {meta.get('title', 'Unknown title')}
{kind}: {label}
Caption: {caption}{content_block}{citing_block}

Extract the scientific finding or claim this {item['type']} supports. Write 2-3 sentences:
1. State the key finding as a factual claim (e.g. "X inhibits Y", "Treatment A increases B by N%").
2. Include specific values, comparisons, or trends visible in the data.
3. End with what the {item['type']} demonstrates in the context of the article's argument.

Use active, definitive language. Avoid "this figure shows" or "this table presents" - \
state the finding directly. Return only the sentences."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[
            {"role": "system", "content": (
                "You extract scientific findings from figures and tables in research articles. "
                "State findings as factual claims with specific values, not descriptions of what "
                "the figure contains. Your output will be used for search retrieval - a researcher "
                "searching for 'X inhibits Y' should match your summary."
            )},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


# ─── Output Formatting ──────────────────────────────────────────────────────

# ─── Figure-Claim Cross-Linking (Phase 5) ────────────────────────────────────

# Patterns that indicate a text chunk references a figure or table.
# Handles: Figure 1, Fig. 1, Figure. 1 A, Figure.1B, Fig. S1 (supplementary)
_FIGURE_REF_RE = re.compile(
    r'(?:Fig(?:ure|\.)?\.?\s*([A-Za-z]?\d+[A-Za-z]?))'
    r'|(?:Table\.?\s*([A-Za-z]?\d+[A-Za-z]?))',
    re.IGNORECASE,
)


def cross_link_figures(text_chunks: list[dict], float_chunks: list[dict]) -> None:
    """Add bidirectional cross-links between text chunks and figure/table chunks.

    Mutates chunks in place:
      - text chunks get  `figure_refs`: list of float IDs (e.g. ["fig1", "fig3"])
      - float chunks get `cited_in`:    list of text chunk IDs that reference them
    """
    # Build lookup: normalised label → float chunk ID
    # "fig1" → "fig1", "tbl2" → "tbl2"
    float_id_map: dict[str, str] = {}
    for fc in float_chunks:
        fid = fc["id"]  # e.g. "fig1", "tbl1"
        float_id_map[fid] = fid
        # Also index by bare number for matching
        if fid.startswith("fig"):
            float_id_map[("figure", fid[3:])] = fid
        elif fid.startswith("tbl"):
            float_id_map[("table", fid[3:])] = fid

    # Initialise cited_in on all float chunks
    cited_in_map: dict[str, list[str]] = {fc["id"]: [] for fc in float_chunks}

    for tc in text_chunks:
        matches = _FIGURE_REF_RE.findall(tc["text"])
        if not matches:
            tc["figure_refs"] = []
            continue

        refs: list[str] = []
        for fig_num, tbl_num in matches:
            if fig_num:
                key = ("figure", fig_num.rstrip("A-Za-z").strip() if fig_num else "")
                # Try exact match first (e.g. "3" → fig3)
                fid = float_id_map.get(("figure", fig_num))
                if not fid:
                    fid = float_id_map.get(f"fig{fig_num}")
                if fid and fid not in refs:
                    refs.append(fid)
            elif tbl_num:
                fid = float_id_map.get(("table", tbl_num))
                if not fid:
                    fid = float_id_map.get(f"tbl{tbl_num}")
                if fid and fid not in refs:
                    refs.append(fid)

        tc["figure_refs"] = refs

        # Back-link: record which text chunks cite each float
        for fid in refs:
            if fid in cited_in_map:
                cited_in_map[fid].append(tc["id"])

    # Write cited_in back onto float chunks
    for fc in float_chunks:
        fc["cited_in"] = cited_in_map.get(fc["id"], [])


def format_chunk(chunk: dict, enriched_text: str, entities: list | None = None) -> dict:
    """Format an enriched text chunk for vector DB ingestion."""
    return {
        "id": chunk["chunk_id"],
        "type": "text",
        "section": chunk["section_type"],
        "section_title": chunk.get("section_title"),
        "subsection_title": chunk.get("subsection_title"),
        "paragraph_index": chunk.get("paragraph_index"),
        "parent_section_id": chunk.get("parent_section_id"),
        "text": enriched_text,
        "entities": entities or [],
        "metadata": chunk["metadata"],
    }


def format_float(item: dict, summary: str, entities: list | None = None) -> dict:
    """Format a summarised figure/table for vector DB ingestion.

    Text layout for tables:
        {label}: {AI summary}
        Caption: {caption}

        {Markdown table}

    Figures omit the Markdown block (no structured content).
    """
    label   = item["label"] or item["id"]
    caption = item["caption"]
    content = item.get("content") or ""   # Markdown table; empty for figures

    parts = [f"{label}: {summary}"]
    if caption:
        parts.append(f"Caption: {caption}")
    if content:
        parts.append(content)

    return {
        "id":       item["id"],
        "type":     item["type"],
        "section":  None,
        "text":     "\n\n".join(parts),
        "label":    label,
        "caption":  caption,
        "entities": entities or [],
        "metadata": item["metadata"],
    }


# ─── Pipeline ───────────────────────────────────────────────────────────────

def run_pipeline(
    xml_path: str,
    output_path: str | None = None,
    dry_run: bool = False,
    max_floats: int | None = None,
) -> dict:
    print(f"\n{'='*60}")
    print(f"Processing: {xml_path}")
    if dry_run:
        print("  [DRY RUN - AI calls skipped]")
    print("=" * 60)

    # Step 1 – Parse XML
    print("\n[1/7] Parsing XML...")
    root = load_xml(xml_path)
    print("      Done.")

    # Step 2 – Extract metadata + section chunks
    print("[2/7] Extracting metadata and sections...")
    metadata = extract_metadata(root)
    chunks = extract_section_chunks(root, metadata)
    floats = extract_floats(root, metadata)
    if max_floats is not None:
        floats = floats[:max_floats]
    print(f"      Article : {metadata.get('title', 'n/a')[:70]}")
    print(f"      DOI     : {metadata.get('doi', 'n/a')}")
    print(f"      Authors : {', '.join(metadata.get('authors', [])[:3])}")
    print(f"      Chunks  : {len(chunks)}  |  Figures/Tables: {len(floats)}")

    # Step 3 – AI: contextual prefixes for text chunks
    print(f"\n[3/7] Generating contextual prefixes ({len(chunks)} chunks)...")
    client = None if dry_run else OpenAI()
    enriched_chunks = []
    for i, chunk in enumerate(chunks, 1):
        label = chunk["section_title"][:50]
        print(f"      [{i}/{len(chunks)}] {label}", end=" ", flush=True)
        if dry_run:
            prefix = f"[DRY RUN] This {chunk['section_type']} section from the article covers {chunk['section_title']}."
        else:
            prefix = generate_contextual_prefix(client, chunk)
        enriched_text = f"{prefix}\n\n{chunk['chunk_text']}"
        enriched_chunks.append(format_chunk(chunk, enriched_text))
        print("OK")

    # Step 4 – AI: summarise figures/tables
    # Preliminary cross-link: run before summarisation so figure chunks know
    # which text passages cite them. Those passages often contain the explicit
    # finding statement (e.g. "as shown in Fig. 1, levels were elevated by X%").
    print(f"\n[4/7] Summarising figures and tables ({len(floats)} items)...")
    cross_link_figures(enriched_chunks, floats)
    chunk_lookup = {c["id"]: c for c in enriched_chunks}

    summarised_floats = []
    for i, item in enumerate(floats, 1):
        print(f"      [{i}/{len(floats)}] {item['label']}", end=" ", flush=True)
        if dry_run:
            summary = f"[DRY RUN] {item['caption']}"
        else:
            citing_ids = item.get("cited_in", [])
            citing_texts = [chunk_lookup[cid]["text"] for cid in citing_ids
                            if cid in chunk_lookup] or None
            summary = summarise_float(client, item, citing_texts=citing_texts)
        summarised_floats.append(format_float(item, summary))
        print("OK")

    # Step 5 – NER + ontology linking
    all_chunks_pre = enriched_chunks + summarised_floats
    journal = metadata.get("journal_id", "?")
    source  = "GPT + NCBI/MeSH" if journal in ("BJ", "REDOX") else "GPT-4o-mini"
    print(f"\n[5/7] Entity tagging ({len(all_chunks_pre)} chunks via {source})...")
    all_chunks_enriched = []
    for i, chunk in enumerate(all_chunks_pre, 1):
        label = (chunk.get("section") or chunk.get("type") or "chunk")[:30]
        print(f"      [{i}/{len(all_chunks_pre)}] {label}", end=" ", flush=True)
        if dry_run:
            entities = []
        else:
            entities = enrich_entities(client, chunk)
        # Store entities back into the chunk dict
        chunk["entities"] = entities
        all_chunks_enriched.append(chunk)
        n = len(entities)
        ids_found = sum(1 for e in entities if e.get("id"))
        print(f"→ {n} entities ({ids_found} with IDs)")

    # Step 5b – Relation & event extraction
    print(f"\n[5b/7] Extracting semantic relations (text chunks only)...")
    text_chunks_for_rel = [c for c in all_chunks_enriched if c.get("type") == "text"]
    total_relations = 0
    for i, chunk in enumerate(text_chunks_for_rel, 1):
        label = (chunk.get("section") or "chunk")[:30]
        print(f"      [{i}/{len(text_chunks_for_rel)}] {label}", end=" ", flush=True)
        if dry_run:
            chunk["relations"] = []
            print("→ 0 triples (dry run)")
        else:
            rels = extract_relations(client, chunk)
            chunk["relations"] = rels
            total_relations += len(rels)
            print(f"→ {len(rels)} triples")
    # Ensure float chunks have an empty relations list for schema consistency
    for chunk in all_chunks_enriched:
        if chunk.get("type") in ("figure", "table"):
            chunk.setdefault("relations", [])

    # Step 6 – Figure-claim cross-linking (Phase 5)
    print("\n[6/7] Cross-linking figures and tables...")
    text_only = [c for c in all_chunks_enriched if c.get("type") == "text"]
    float_only = [c for c in all_chunks_enriched if c.get("type") in ("figure", "table")]
    cross_link_figures(text_only, float_only)
    linked_text = sum(1 for c in text_only if c.get("figure_refs"))
    cited_floats = sum(1 for c in float_only if c.get("cited_in"))
    print(f"      {linked_text} text chunks reference figures/tables")
    print(f"      {cited_floats}/{len(float_only)} figures/tables are cited in text")

    # Step 7 – Combine + aggregate
    print("\n[7/7] Combining and aggregating...")
    all_chunks = all_chunks_enriched
    total_entities   = sum(len(c.get("entities", [])) for c in all_chunks)
    entities_with_id = sum(1 for c in all_chunks for e in c.get("entities", []) if e.get("id"))
    total_rels       = sum(len(c.get("relations", [])) for c in all_chunks)
    output = {
        "source_file": Path(xml_path).name,
        "article_doi": metadata.get("doi"),
        "total_chunks": len(all_chunks),
        "text_chunks": len(enriched_chunks),
        "visual_chunks": len(summarised_floats),
        "total_entities": total_entities,
        "entities_with_ontology_id": entities_with_id,
        "total_relations": total_rels,
        "processed_chunks": all_chunks,
    }

    chunks_dir = Path(__file__).parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    out_file = output_path or str(chunks_dir / (Path(xml_path).stem + "_chunks.json"))
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n Done!")
    print(f"      Total chunks   : {len(all_chunks)}")
    print(f"      Total entities : {total_entities} ({entities_with_id} with ontology IDs)")
    print(f"      Total relations: {total_rels} triples")
    print(f"      Output file    : {out_file}")
    return output


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elsevier XML → Enriched Chunks")
    parser.add_argument("xml_file", help="Path to Elsevier XML file")
    parser.add_argument("--output", help="Output JSON file path", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI calls; use placeholder text (no API key needed)",
    )
    parser.add_argument(
        "--max-floats",
        type=int,
        default=None,
        metavar="N",
        help="Limit figures/tables processed (useful for large files like ESR-102126 which has 62)",
    )
    args = parser.parse_args()

    result = run_pipeline(
        args.xml_file,
        output_path=args.output,
        dry_run=args.dry_run,
        max_floats=args.max_floats,
    )
    print(f"\nSample chunk (first text chunk):")
    print(json.dumps(result["processed_chunks"][0], indent=2)[:800] + "\n...")
