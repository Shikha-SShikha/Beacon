"""
stage_mastercopy.py — Verified Enrichment Pass (Mastercopy/Proof Stage)

Parses the mastercopied (proof) XML, diffs it against the copyedited XML to
surface what the human corrected, then runs full enrichment:
  - NER Stage 2 (GPT extraction + ontology ID resolution)
  - Semantic relation extraction
  - Contextual prefix generation
  - Figure/table claim extraction
  - Figure cross-linking

Output:
  .tmp/enrichment_mastercopy.json  — verified manifest (human-review artefact)
  chunks/<stem>_chunks.json        — pipeline-compatible chunks for ChromaDB ingestion

The chunks output is identical in structure to pipeline.py output, so it feeds
directly into experiment.py and chat_app.py without any changes.

Usage:
    python stage_mastercopy.py <proof_xml> [--copyedit <copyedit_xml>]
                               [--manifest <enrichment_copyedit.json>]
                               [--output <manifest.json>] [--dry-run]
"""

import re
import json
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher
from lxml import etree
from openai import OpenAI

# Import from existing pipeline modules — no changes to those files needed
from pipeline import (
    load_xml,
    extract_metadata,
    extract_section_chunks,
    extract_floats,
    generate_contextual_prefix,
    summarise_float,
    cross_link_figures,
    format_chunk,
    format_float,
)
from ner import enrich_entities
from relations import extract_relations

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())




# ─── Diff Helpers ─────────────────────────────────────────────────────────────

def _section_text_map(sections_or_chunks: list) -> dict[str, str]:
    """
    Build {section_type → combined text} map for diffing.
    Accepts both copyedit manifest sections and pipeline.py chunks.
    """
    by_type: dict[str, list[str]] = {}
    for item in sections_or_chunks:
        # Copyedit manifest format: section with paragraphs list
        if "paragraphs" in item:
            stype = item.get("section_type", "other")
            for p in item["paragraphs"]:
                by_type.setdefault(stype, []).append(p.get("text", ""))
        # Pipeline chunk format: flat chunk with chunk_text
        elif "chunk_text" in item:
            stype = item.get("section_type", "other")
            by_type.setdefault(stype, []).append(item.get("chunk_text", ""))
    return {k: " ".join(v) for k, v in by_type.items()}


def diff_stages(copyedit_sections: list, proof_chunks: list) -> dict:
    """
    Compare copyedit and mastercopy text by section type.

    Returns a diff summary with similarity scores per section and a list
    of changed vs unchanged section types.
    """
    ce_map = _section_text_map(copyedit_sections)
    mc_map = _section_text_map(proof_chunks)

    all_types = sorted(set(ce_map) | set(mc_map))
    section_diffs = []
    changed = []
    unchanged = []

    for stype in all_types:
        ce_text = ce_map.get(stype, "")
        mc_text = mc_map.get(stype, "")

        if not ce_text and not mc_text:
            continue

        ratio = SequenceMatcher(None, ce_text, mc_text).ratio()
        changed_flag = ratio < 0.95

        entry = {
            "section_type": stype,
            "similarity": round(ratio, 3),
            "changed": changed_flag,
            "ce_chars": len(ce_text),
            "mc_chars": len(mc_text),
        }
        section_diffs.append(entry)

        if changed_flag:
            changed.append(stype)
        else:
            unchanged.append(stype)

    return {
        "sections": section_diffs,
        "changed": changed,
        "unchanged": unchanged,
        "total_sections": len(section_diffs),
        "changed_count": len(changed),
    }


# ─── Enrichment ───────────────────────────────────────────────────────────────

def _stamp_verified(items: list[dict]) -> list[dict]:
    """Mark entity/relation/claim dicts as verified."""
    ts = datetime.now(timezone.utc).isoformat()
    for item in items:
        item["status"] = "verified"
        item["verified_by"] = "stage_mastercopy"
        item["verified_at"] = ts
    return items


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def run_stage_mastercopy(
    proof_xml: str,
    copyedit_xml: str | None = None,
    copyedit_manifest: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    print(f"\n{'='*60}")
    print(f"Stage: Mastercopy  |  {Path(proof_xml).name}")
    if dry_run:
        print("  [DRY RUN — AI calls skipped]")
    print("=" * 60)

    # Step 1 — Parse mastercopy XML
    print("\n[1/8] Parsing mastercopy XML...")
    root = load_xml(proof_xml)
    metadata = extract_metadata(root)
    chunks_raw = extract_section_chunks(root, metadata)
    floats_raw = extract_floats(root, metadata)
    print(f"      Title   : {metadata.get('title', 'n/a')[:70]}")
    print(f"      DOI     : {metadata.get('doi', 'n/a')}")
    print(f"      Chunks  : {len(chunks_raw)}  |  Floats: {len(floats_raw)}")

    # Step 2 — Load reviewed copyedit manifest (if provided)
    print("\n[2/8] Loading reviewed copyedit manifest...")
    ce_manifest: dict | None = None
    if copyedit_manifest:
        manifest_path = Path(copyedit_manifest)
    else:
        manifest_path = Path(__file__).parent / ".tmp" / "enrichment_copyedit.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            ce_manifest = json.load(f)
        print(f"      Loaded: {manifest_path}")
    else:
        print(f"      Not found: {manifest_path} — proceeding without copyedit context")

    # Build rejected entity set from human review decisions
    # Format: {(text.lower(), type)} for post-filtering after enrichment
    rejected_entities: set[tuple[str, str]] = set()
    if ce_manifest:
        for sec in ce_manifest.get("sections", []):
            for para in sec.get("paragraphs", []):
                for e in para.get("entities", []):
                    if e.get("status") == "rejected":
                        rejected_entities.add((e["text"].lower(), e["type"]))
        n_rejected = len(rejected_entities)
        if n_rejected:
            print(f"      Human review: {n_rejected} entity type(s) rejected — will be filtered from output")
        else:
            print(f"      Human review: no rejections")

    # Step 3 — Diff copyedit vs mastercopy
    print("\n[3/8] Diffing stages...")
    diff = None
    if ce_manifest:
        diff = diff_stages(ce_manifest.get("sections", []), chunks_raw)
        print(f"      Changed sections  : {diff['changed_count']} / {diff['total_sections']}")
        for sd in diff["sections"]:
            flag = "CHANGED" if sd["changed"] else "unchanged"
            print(f"        [{flag}] {sd['section_type']} (similarity={sd['similarity']})")
    else:
        print("      No copyedit manifest — skipping diff")

    # Step 4 — Contextual prefix generation
    client = None if dry_run else OpenAI()
    print(f"\n[4/8] Generating contextual prefixes ({len(chunks_raw)} chunks)...")
    enriched_chunks = []
    for i, chunk in enumerate(chunks_raw, 1):
        label = chunk["section_title"][:40]
        print(f"      [{i}/{len(chunks_raw)}] {label}", end=" ", flush=True)
        if dry_run:
            prefix = f"[DRY RUN] This {chunk['section_type']} section covers {chunk['section_title']}."
        else:
            prefix = generate_contextual_prefix(client, chunk)
        enriched_text = f"{prefix}\n\n{chunk['chunk_text']}"
        enriched_chunks.append(format_chunk(chunk, enriched_text))
        print("OK")

    # Step 5 — Figure/table summaries
    print(f"\n[5/8] Summarising figures and tables ({len(floats_raw)} items)...")
    summarised_floats = []
    for i, item in enumerate(floats_raw, 1):
        print(f"      [{i}/{len(floats_raw)}] {item['label']}", end=" ", flush=True)
        if dry_run:
            summary = f"[DRY RUN] {item['caption']}"
        else:
            summary = summarise_float(client, item)
        summarised_floats.append(format_float(item, summary))
        print("OK")

    # Step 6 — NER Stage 2: GPT extraction + ontology ID resolution
    all_chunks_pre = enriched_chunks + summarised_floats
    print(f"\n[6/8] NER Stage 2 — entities + ontology IDs ({len(all_chunks_pre)} chunks)...")
    all_chunks_enriched = []
    for i, chunk in enumerate(all_chunks_pre, 1):
        label = (chunk.get("section") or chunk.get("type") or "chunk")[:30]
        print(f"      [{i}/{len(all_chunks_pre)}] {label}", end=" ", flush=True)
        if dry_run:
            entities = []
        else:
            entities = enrich_entities(client, chunk)
            _stamp_verified(entities)
        # Post-filter entities rejected during human review
        if rejected_entities:
            entities = [
                e for e in entities
                if (e["text"].lower(), e["type"]) not in rejected_entities
            ]
        chunk["entities"] = entities
        all_chunks_enriched.append(chunk)
        n = len(entities)
        ids_found = sum(1 for e in entities if e.get("id"))
        print(f"→ {n} entities ({ids_found} with IDs)")

    # Step 7 — Relation extraction
    print(f"\n[7/8] Extracting semantic relations (text chunks)...")
    text_chunks = [c for c in all_chunks_enriched if c.get("type") == "text"]
    total_relations = 0
    for i, chunk in enumerate(text_chunks, 1):
        label = (chunk.get("section") or "chunk")[:30]
        print(f"      [{i}/{len(text_chunks)}] {label}", end=" ", flush=True)
        if dry_run:
            chunk["relations"] = []
            print("→ 0 triples (dry run)")
        else:
            rels = extract_relations(client, chunk)
            _stamp_verified(rels)
            chunk["relations"] = rels
            total_relations += len(rels)
            print(f"→ {len(rels)} triples")
    for chunk in all_chunks_enriched:
        if chunk.get("type") in ("figure", "table"):
            chunk.setdefault("relations", [])

    # Step 8 — Figure cross-linking
    print("\n[8/8] Cross-linking figures and tables...")
    text_only = [c for c in all_chunks_enriched if c.get("type") == "text"]
    float_only = [c for c in all_chunks_enriched if c.get("type") in ("figure", "table")]
    cross_link_figures(text_only, float_only)
    linked_text = sum(1 for c in text_only if c.get("figure_refs"))
    cited_floats = sum(1 for c in float_only if c.get("cited_in"))
    print(f"      {linked_text} text chunks reference figures/tables")
    print(f"      {cited_floats}/{len(float_only)} figures/tables cited in text")

    # ── Assemble verified manifest ────────────────────────────────────────────
    total_entities = sum(len(c.get("entities", [])) for c in all_chunks_enriched)
    entities_with_id = sum(
        1 for c in all_chunks_enriched for e in c.get("entities", []) if e.get("id")
    )

    manifest = {
        "source_file": Path(proof_xml).name,
        "copyedit_file": Path(copyedit_xml).name if copyedit_xml else None,
        "stage": "mastercopy",
        "manifest_status": "verified",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "diff": diff,
        "chunks": all_chunks_enriched,
    }

    # ── Save manifest ─────────────────────────────────────────────────────────
    tmp_dir = Path(__file__).parent / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    manifest_file = output_path or str(tmp_dir / "enrichment_mastercopy.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # ── Save pipeline-compatible chunk JSON (for ChromaDB ingestion) ──────────
    chunks_dir = Path(__file__).parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    stem = Path(proof_xml).stem.replace(" ", "_")
    chunk_file = str(chunks_dir / f"{stem}_chunks.json")

    pipeline_output = {
        "source_file": Path(proof_xml).name,
        "article_doi": metadata.get("doi"),
        "total_chunks": len(all_chunks_enriched),
        "text_chunks": len(enriched_chunks),
        "visual_chunks": len(summarised_floats),
        "total_entities": total_entities,
        "entities_with_ontology_id": entities_with_id,
        "total_relations": total_relations,
        "processed_chunks": all_chunks_enriched,
    }
    with open(chunk_file, "w", encoding="utf-8") as f:
        json.dump(pipeline_output, f, indent=2, ensure_ascii=False)

    print(f"\n Done!")
    print(f"      Chunks      : {len(all_chunks_enriched)}")
    print(f"      Entities    : {total_entities} ({entities_with_id} with ontology IDs)")
    print(f"      Relations   : {total_relations} triples")
    print(f"      Manifest    : {manifest_file}")
    print(f"      Chunks JSON : {chunk_file}  ← drop-in for pipeline.py output")
    return manifest


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mastercopy stage: full enrichment with ontology IDs + verified manifest"
    )
    parser.add_argument("proof_xml", help="Path to mastercopied (proof) XML")
    parser.add_argument(
        "--copyedit",
        metavar="XML",
        default=None,
        help="Path to copyedited XML (for diff display)",
    )
    parser.add_argument(
        "--manifest",
        metavar="JSON",
        default=None,
        help="Path to enrichment_copyedit.json (defaults to .tmp/enrichment_copyedit.json)",
    )
    parser.add_argument("--output", help="Output manifest JSON path", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip AI calls; use placeholder output (no API key needed)",
    )
    args = parser.parse_args()

    result = run_stage_mastercopy(
        proof_xml=args.proof_xml,
        copyedit_xml=args.copyedit,
        copyedit_manifest=args.manifest,
        output_path=args.output,
        dry_run=args.dry_run,
    )
