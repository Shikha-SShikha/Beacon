"""
stage_copyedit.py — Draft Enrichment Pass (Copyedit Stage)

Parses the flat editorial XML (pre-proof format) and produces a draft
enrichment manifest with NER Stage 1 entities only. No ontology ID
resolution, no relations, no figure claims — those all run once at
the mastercopy stage after human review.

Usage:
    python stage_copyedit.py <copyedit_xml> [--output <manifest.json>] [--dry-run]

Output:
    .tmp/enrichment_copyedit.json  (default)
"""

import re
import json
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from lxml import etree
from openai import OpenAI
from ner import gpt_extract_entities

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Journal ID remap: keys without a native hint fall back to nearest domain.
# CCC now has its own hint in ner.py; keep this dict for any future gaps.
_JID_REMAP: dict[str, str] = {}


# ─── Text Helpers ─────────────────────────────────────────────────────────────

def local(tag: str) -> str:
    if "}" in tag:
        return tag.split("}")[-1]
    if ":" in tag:
        return tag.split(":")[-1]
    return tag


# Elements to skip entirely (content + tail dropped)
_SKIP_ALL = {"role", "linenumber", "query", "xref"}
# Elements whose own text is skipped but whose tail (following prose) is kept
_SKIP_TEXT = {"del", "sup"}


def _collect(node, parts: list, skip_all: set, skip_text: set) -> None:
    """
    Recursively collect text content from an editorial XML element.

    Rules:
    - del elements: skip their text (old content), keep their tail (following prose)
    - sup elements: skip their text (citation numbers), keep their tail
    - role / linenumber / query / xref: skip entirely — no text, no tail
    - Everything else (ins, x, fnm, snm, para, etc.): include text + tail
    """
    loc = local(node.tag)

    # Include this node's own text unless it's a skip_text type
    if loc not in skip_text and node.text:
        parts.append(node.text)

    for child in node:
        cloc = local(child.tag)
        if cloc in skip_all:
            continue  # drop child entirely, including its tail

        _collect(child, parts, skip_all, skip_text)

        # Tail belongs to the parent's text flow; add after the child's subtree
        if child.tail:
            parts.append(child.tail)


def apply_edits(el) -> str:
    """
    Extract clean text from an editorial XML element, applying ins/del track changes.

    The copyeditor XML uses <ins> / <del> elements:
      <ins>A</ins><del>a</del>nalysis  →  "Analysis"  (capital correction)
      <del> </del>                      →  (space deletion around citations)

    This function includes ins.text, skips del.text, and always keeps
    element tails (which carry the following prose).
    """
    parts: list[str] = []
    _collect(el, parts, _SKIP_ALL, _SKIP_TEXT)
    # Concatenate without adding extra spaces between parts; normalize runs of spaces
    return re.sub(r" {2,}", " ", "".join(parts)).strip()


# ─── XML Parsing ──────────────────────────────────────────────────────────────

def load_xml(file_path: str) -> etree._Element:
    with open(file_path, "rb") as f:
        content = f.read()
    content = re.sub(rb"<!DOCTYPE[^[]*\[.*?\]>", b"", content, flags=re.DOTALL)
    parser = etree.XMLParser(recover=True, resolve_entities=False)
    return etree.fromstring(content, parser=parser)


def extract_metadata(root: etree._Element) -> dict:
    """Extract article metadata from coversheet, articletitle, authors, abstract, keywords."""
    meta: dict = {}

    for child in root:
        loc = local(child.tag)

        if loc == "coversheet":
            for cc in child:
                cloc = local(cc.tag)
                t = (cc.text or "").strip()
                if cloc == "doi" and t:
                    meta["doi"] = t
                elif cloc == "jid" and t:
                    meta["journal_id"] = t
                elif cloc == "pii" and t:
                    meta["pii"] = t
                elif cloc == "aid" and t:
                    meta["article_id"] = t

        elif loc == "articletitle":
            meta["title"] = apply_edits(child)

        elif loc == "authors":
            authors = []
            for au in child:
                if local(au.tag) == "au":
                    name = apply_edits(au).strip(" *,")
                    if name and len(name) > 2:
                        authors.append(name)
            meta["authors"] = authors

        elif loc == "abstract":
            text = apply_edits(child)
            if text:
                existing = meta.get("abstract", "")
                meta["abstract"] = (existing + " " + text).strip() if existing else text

        elif loc == "keywordsdefault":
            text = apply_edits(child)
            text = re.sub(r"^Keywords?\s*:?\s*", "", text, flags=re.IGNORECASE)
            kws = [k.strip() for k in re.split(r"[;,]", text) if k.strip()]
            meta["keywords"] = kws

    return meta


def _normalise_role(title: str) -> str:
    t = title.lower()
    if "introduction" in t:
        return "introduction"
    if "method" in t or "material" in t:
        return "methods"
    if "result" in t:
        return "results"
    if "discussion" in t:
        return "discussion"
    if "conclusion" in t:
        return "conclusion"
    if "funding" in t:
        return "funding"
    if "competing" in t or "conflict" in t:
        return "competing_interests"
    if "ethic" in t:
        return "ethics"
    if "contribution" in t:
        return "author_contribution"
    if "data" in t or "availab" in t:
        return "data_availability"
    return "other"


def extract_sections_and_floats(root: etree._Element) -> tuple[list, list]:
    """
    Walk flat editorial XML children and reconstruct section hierarchy.

    The editorial format uses flat siblings (sectiona, sectionb, paragraph)
    rather than the nested <section> elements in the Elsevier DTD format.

    Returns:
        sections: [{section_id, section_type, section_title, paragraphs: [{...}]}]
        floats:   [{id, type, label, caption, content}]
    """
    sections: list[dict] = []
    floats: list[dict] = []

    current_section: dict | None = None
    current_subsection: str | None = None
    fig_count = 0
    tbl_count = 0
    pending_caption: str | None = None

    for child in root:
        loc = local(child.tag)

        if loc == "sectiona":
            title = apply_edits(child)
            if not title:
                continue
            sec_id = f"sec{len(sections)}"
            current_section = {
                "section_id": sec_id,
                "section_type": _normalise_role(title),
                "section_title": title,
                "paragraphs": [],
            }
            sections.append(current_section)
            current_subsection = None

        elif loc == "sectionb":
            current_subsection = apply_edits(child) or None

        elif loc == "paragraph":
            if current_section is None:
                continue
            text = apply_edits(child)
            if not text.strip():
                continue
            para_id = f"{current_section['section_id']}-p{len(current_section['paragraphs'])}"
            current_section["paragraphs"].append(
                {
                    "para_id": para_id,
                    "subsection_title": current_subsection,
                    "text": text,
                }
            )

        elif loc == "figcaption":
            fig_count += 1
            caption = apply_edits(child)
            floats.append(
                {
                    "id": f"fig{fig_count}",
                    "type": "figure",
                    "label": f"Figure {fig_count}",
                    "caption": caption,
                    "content": None,
                }
            )

        elif loc == "tablecaption":
            pending_caption = apply_edits(child)

        elif loc == "table":
            tbl_count += 1
            content = apply_edits(child)
            floats.append(
                {
                    "id": f"tbl{tbl_count}",
                    "type": "table",
                    "label": f"Table {tbl_count}",
                    "caption": pending_caption or "",
                    "content": content[:800],  # truncated for AI calls
                }
            )
            pending_caption = None

    return sections, floats


# ─── AI Enrichment ────────────────────────────────────────────────────────────

def _make_chunk(text: str, chunk_type: str, metadata: dict) -> dict:
    """Build a minimal chunk dict compatible with ner.py and relations.py."""
    # Remap journal_id so ner.py picks the right domain hint
    jid = metadata.get("journal_id", "")
    effective_jid = _JID_REMAP.get(jid, jid)
    return {
        "text": text,
        "type": chunk_type,
        "metadata": {**metadata, "journal_id": effective_jid},
    }


def _stamp_draft(items: list[dict]) -> list[dict]:
    """Add draft status fields to entity/relation/claim dicts."""
    for item in items:
        item["status"] = "draft"
        item["verified_by"] = None
        item["verified_at"] = None
    return items


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def run_stage_copyedit(
    xml_path: str,
    output_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    print(f"\n{'='*60}")
    print(f"Stage: Copyedit  |  {Path(xml_path).name}")
    if dry_run:
        print("  [DRY RUN — AI calls skipped]")
    print("=" * 60)

    # Step 1 — Parse XML
    print("\n[1/4] Parsing editorial XML...")
    root = load_xml(xml_path)
    print("      Done.")

    # Step 2 — Extract structure
    print("[2/4] Extracting metadata and sections...")
    metadata = extract_metadata(root)
    sections, floats = extract_sections_and_floats(root)
    total_paras = sum(len(s["paragraphs"]) for s in sections)
    print(f"      Title   : {metadata.get('title', 'n/a')[:70]}")
    print(f"      DOI     : {metadata.get('doi', 'n/a')}")
    print(f"      Authors : {', '.join(metadata.get('authors', [])[:3])}")
    print(f"      Journal : {metadata.get('journal_id', 'n/a')}")
    print(f"      Sections: {len(sections)}  |  Paragraphs: {total_paras}  |  Floats: {len(floats)}")

    # Step 3 — NER Stage 1: entity extraction only (no IDs, no relations)
    # Relations, ontology IDs, and figure claims all run once at mastercopy stage.
    print(f"\n[3/3] NER Stage 1 — entity names + types ({total_paras} paragraphs)...")
    client = None if dry_run else OpenAI()
    total_entities = 0

    for sec in sections:
        print(f"      [{sec['section_type']}] {sec['section_title'][:50]}")
        for para in sec["paragraphs"]:
            chunk = _make_chunk(para["text"], "text", metadata)

            if dry_run:
                entities: list = []
            else:
                entities = _stamp_draft(gpt_extract_entities(client, chunk))

            para["entities"] = entities
            total_entities += len(entities)
            print(f"        {para['para_id']}: {len(entities)} entities")

    # Assemble manifest
    manifest = {
        "source_file": Path(xml_path).name,
        "stage": "copyedit",
        "manifest_status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "sections": sections,
        "floats": floats,
    }

    # Save output
    tmp_dir = Path(__file__).parent / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    out_file = output_path or str(tmp_dir / "enrichment_copyedit.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n Done!")
    print(f"      Sections  : {len(sections)}")
    print(f"      Paragraphs: {total_paras}")
    print(f"      Floats    : {len(floats)} (no enrichment yet — runs at mastercopy)")
    print(f"      Entities  : {total_entities}  (draft, no ontology IDs yet)")
    print(f"      Manifest  : {out_file}")
    return manifest


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Copyedit stage: NER Stage 1 entity extraction (draft, no IDs)"
    )
    parser.add_argument("xml_file", help="Path to copyedited editorial XML")
    parser.add_argument("--output", help="Output manifest JSON path", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI calls; use placeholder output (no API key needed)",
    )
    args = parser.parse_args()

    result = run_stage_copyedit(
        args.xml_file,
        output_path=args.output,
        dry_run=args.dry_run,
    )

    # Print a sample entity from the first paragraph that has any
    sample_entity = next(
        (
            e
            for s in result["sections"]
            for p in s["paragraphs"]
            for e in p.get("entities", [])
        ),
        None,
    )
    if sample_entity:
        print(f"\nSample entity: {json.dumps(sample_entity, indent=2)}")
