"""
Step 7: JSON-LD Serializer

Transforms enriched chunk JSON (output of pipeline.py) into
schema.org JSON-LD for web discoverability.

Each article becomes a schema:ScholarlyArticle with:
  - Entities as schema:mentions with canonical @id IRIs
  - Broader MeSH terms as skos:broader hierarchy
  - Relations as beacon:relations (subject-predicate-object triples)
  - Sections as schema:hasPart with beacon:sectionType
  - Figures as schema:image, tables as schema:table

Usage:
    python jsonld_serializer.py                           # all chunks/
    python jsonld_serializer.py chunks/BJ_100828_chunks.json
"""

import json
import sys
from pathlib import Path

# ─── JSON-LD Context ──────────────────────────────────────────────────────────

CONTEXT = {
    "schema":   "https://schema.org/",
    "beacon":   "https://beacon-enrichment.io/vocab#",
    "skos":     "http://www.w3.org/2004/02/skos/core#",
    "ncbigene": "https://www.ncbi.nlm.nih.gov/gene/",
    "mesh":     "https://id.nlm.nih.gov/mesh/",
    "doid":     "http://purl.obolibrary.org/obo/DOID_",
    "chebi":    "http://purl.obolibrary.org/obo/CHEBI_",
    "taxon":    "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=",
    "cvcl":     "https://www.cellosaurus.org/",
}

# ─── IRI builders ─────────────────────────────────────────────────────────────

def entity_iri(entity: dict) -> str | None:
    """Build a canonical IRI for an entity from its ontology + id."""
    eid = entity.get("id")
    ont = entity.get("ontology", "")
    if not eid:
        return None
    if ont == "NCBI Gene":
        return f"https://www.ncbi.nlm.nih.gov/gene/{eid}"
    elif ont == "MeSH":
        return f"https://id.nlm.nih.gov/mesh/{eid}"
    elif ont == "Disease Ontology":
        numeric = eid.replace("DOID:", "")
        return f"http://purl.obolibrary.org/obo/DOID_{numeric}"
    elif ont == "ChEBI":
        numeric = eid.replace("CHEBI:", "")
        return f"http://purl.obolibrary.org/obo/CHEBI_{numeric}"
    elif ont == "Cellosaurus":
        return f"https://www.cellosaurus.org/{eid}"
    elif ont == "NCBI Taxonomy":
        return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={eid}"
    return None


# ─── Node serializers ─────────────────────────────────────────────────────────

def serialize_entity(entity: dict) -> dict:
    node: dict = {
        "@type":           "schema:Thing",
        "schema:name":     entity["text"],
        "beacon:entityType": entity["type"],
    }
    iri = entity_iri(entity)
    if iri:
        node["@id"] = iri
    broader = entity.get("broader_terms", [])
    if broader:
        node["skos:broader"] = [{"schema:name": t} for t in broader]
    return node


def serialize_relation(rel: dict) -> dict:
    return {
        "@type":           "beacon:Relation",
        "beacon:subject":  rel["subject"],
        "beacon:predicate": rel["predicate"],
        "beacon:object":   rel["object"],
        "beacon:evidence": rel.get("evidence", ""),
    }


def serialize_section(chunk: dict) -> dict:
    node: dict = {
        "@type":             "schema:WebPageElement",
        "beacon:chunkId":    chunk.get("id", ""),
        "beacon:sectionType": chunk.get("section", "other"),
        "schema:text":       chunk.get("text", ""),
    }
    if chunk.get("section_title"):
        node["schema:name"] = chunk["section_title"]
    if chunk.get("subsection_title"):
        node["beacon:subsectionTitle"] = chunk["subsection_title"]
    entities = chunk.get("entities", [])
    if entities:
        node["schema:mentions"] = [serialize_entity(e) for e in entities]
    relations = chunk.get("relations", [])
    if relations:
        node["beacon:relations"] = [serialize_relation(r) for r in relations]
    if chunk.get("figure_refs"):
        node["beacon:figureRefs"] = chunk["figure_refs"]
    return node


def serialize_visual(chunk: dict) -> dict:
    chunk_type = chunk.get("type", "figure")
    schema_type = "schema:ImageObject" if chunk_type == "figure" else "schema:Table"
    node: dict = {
        "@type":          schema_type,
        "beacon:chunkId": chunk.get("id", ""),
        "schema:name":    chunk.get("label", ""),
        "schema:caption": chunk.get("caption", ""),
        "schema:text":    chunk.get("text", ""),
    }
    entities = chunk.get("entities", [])
    if entities:
        node["schema:mentions"] = [serialize_entity(e) for e in entities]
    if chunk.get("cited_in"):
        node["beacon:citedInChunks"] = chunk["cited_in"]
    return node


# ─── Main transform ───────────────────────────────────────────────────────────

def chunks_to_jsonld(data: dict) -> dict:
    chunks = data.get("processed_chunks", [])
    if not chunks:
        return {}

    meta = chunks[0].get("metadata", {})
    doi  = meta.get("doi", "")

    text_chunks   = [c for c in chunks if c.get("type") == "text"]
    figure_chunks = [c for c in chunks if c.get("type") == "figure"]
    table_chunks  = [c for c in chunks if c.get("type") == "table"]

    # Deduplicate entities across all chunks for article-level schema:mentions
    seen: dict[tuple, dict] = {}
    for chunk in chunks:
        for e in chunk.get("entities", []):
            key = (e["text"].lower(), e["type"])
            if key not in seen:
                seen[key] = e

    article: dict = {
        "@context":              CONTEXT,
        "@type":                 "schema:ScholarlyArticle",
        "schema:name":           meta.get("title", ""),
        "schema:datePublished":  meta.get("publication_date", ""),
        "schema:isPartOf": {
            "@type":       "schema:Periodical",
            "schema:name": meta.get("journal_id", ""),
        },
        "beacon:sourceFile":     data.get("source_file", ""),
        "beacon:totalRelations": data.get("total_relations", 0),
        "beacon:enrichedBy":     "Beacon Enrichment Pipeline",
    }

    if doi:
        article["@id"]              = f"https://doi.org/{doi}"
        article["schema:identifier"] = doi

    authors = meta.get("authors", [])
    if authors:
        article["schema:author"] = [
            {"@type": "schema:Person", "schema:name": a} for a in authors
        ]

    abstract = meta.get("abstract", "")
    if abstract:
        article["schema:abstract"] = abstract

    keywords = meta.get("keywords", [])
    if keywords:
        article["schema:keywords"] = keywords

    if seen:
        article["schema:mentions"] = [serialize_entity(e) for e in seen.values()]

    if text_chunks:
        article["schema:hasPart"] = [serialize_section(c) for c in text_chunks]

    if figure_chunks:
        article["schema:image"] = [serialize_visual(c) for c in figure_chunks]

    if table_chunks:
        article["schema:table"] = [serialize_visual(c) for c in table_chunks]

    return article


# ─── File I/O ─────────────────────────────────────────────────────────────────

def process_file(chunks_path: Path, output_dir: Path) -> None:
    with open(chunks_path, encoding="utf-8") as f:
        data = json.load(f)

    doc = chunks_to_jsonld(data)
    if not doc:
        print(f"  [SKIP] {chunks_path.name} — no chunks")
        return

    out_name = chunks_path.name.replace("_chunks.json", ".jsonld")
    out_path  = output_dir / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    n_mentions  = len(doc.get("schema:mentions", []))
    n_sections  = len(doc.get("schema:hasPart", []))
    n_relations = doc.get("beacon:totalRelations", 0)
    n_figures   = len(doc.get("schema:image", []))
    n_tables    = len(doc.get("schema:table", []))
    print(f"  {chunks_path.name}")
    print(f"    → {out_name}")
    print(f"    sections: {n_sections}  |  entities: {n_mentions}  |  "
          f"relations: {n_relations}  |  figures: {n_figures}  |  tables: {n_tables}")


if __name__ == "__main__":
    chunks_dir = Path(__file__).parent / "chunks"
    output_dir = Path(__file__).parent / "jsonld"
    output_dir.mkdir(exist_ok=True)

    if len(sys.argv) > 1:
        files = [Path(p) for p in sys.argv[1:]]
    else:
        files = sorted(chunks_dir.glob("*_chunks.json"))

    if not files:
        print("No chunk files found.")
        sys.exit(1)

    print(f"Serializing {len(files)} file(s) to JSON-LD...\n")
    for chunk_file in files:
        process_file(chunk_file, output_dir)

    print(f"\nOutput: {output_dir}/")
