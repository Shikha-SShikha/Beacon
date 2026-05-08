"""
Retrieval Experiment: Raw vs Enriched vs Entity-Enriched

Three collections built from the same source articles:
  1. raw            - plain section text only
  2. enriched       - metadata header + AI contextual prefix + text (merged)
  3. entity_enriched - named entity tags + enriched text

Usage:
    python experiment.py
"""

import json
import os
import argparse
from pathlib import Path
from openai import OpenAI
import chromadb
from ner import gpt_extract_entities, tag_string

# Load .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

CHROMA_PATH = Path(__file__).parent / "chroma_db"
CHUNKS_DIR  = Path(__file__).parent / "chunks"
EMBED_MODEL = "text-embedding-3-small"

QUERIES = [
    # Energy
    "How does social network structure affect collective energy transition decisions?",
    "Hybrid renewable energy system optimization for EV charging stations",
    # Biomedical - entity-specific
    "TM5614 clinical trial results in chronic myeloid leukemia",
    "PAI-1 inhibition as a therapeutic target in leukemia",
    "YY1 and ANXA3 nitration in diabetic cardiomyopathy",
    "ALK translocation FISH detection in non-small cell lung cancer",
    # Project management
    "How do dark personality traits affect project outcomes?",
    "Paradox of autonomy and control in agile teams",
    # Cross-domain
    "What methodology was used to collect and analyse data?",
    "What are the main conclusions of the study?",
    # Figures & Tables - these expose the html_scrape gap most clearly
    "What does Figure 1 show in the agent-based model?",
    "What performance metrics are shown in the EV charging station results tables?",
]


# ─── Entity Extraction ───────────────────────────────────────────────────────

def _get_entities(client: OpenAI, chunk: dict) -> list[dict]:
    """
    Return entities for a chunk.
    Prefers pre-computed entities stored in chunk JSON (from pipeline.py NER step).
    Falls back to GPT extraction if chunk has no pre-computed entities.
    """
    entities = chunk.get("entities")
    if entities is not None:   # pre-computed (may be empty list - that's fine)
        return entities
    # Fallback: run GPT extraction on the fly (old chunks without NER)
    return gpt_extract_entities(client, chunk)


# ─── Embeddings ──────────────────────────────────────────────────────────────

def embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ─── Collection Builder ───────────────────────────────────────────────────────

def build_collections(client: OpenAI, chroma: chromadb.Client, chunks_by_file: list[dict]):
    """
    Build two ChromaDB collections:
      html_scrape     - simulated HTML scrape: figures=[IMAGE], tables=caption only, text=plain
      entity_enriched - entity tags + AI prefix + full text (full Beacon pipeline)

    These are the two comparison points: standard RAG vs Beacon.
    Also deletes any stale 'enriched' collection left from the original 3-collection experiment.
    """
    for name in ("html_scrape", "enriched", "entity_enriched"):
        try:
            chroma.delete_collection(name)
        except Exception:
            pass

    col_html   = chroma.create_collection("html_scrape")
    col_entity = chroma.create_collection("entity_enriched")

    ids_html,   texts_html,   metas_html   = [], [], []
    ids_entity, texts_entity, metas_entity = [], [], []

    total = sum(len(f["processed_chunks"]) for f in chunks_by_file)
    print(f"  Building texts for {total} chunks...")

    for file_data in chunks_by_file:
        # Use article_doi if available, otherwise source_file, otherwise "unknown"
        doi = file_data.get("article_doi") or file_data.get("source_file") or "unknown"
        doi_prefix = doi.replace("/", "-")
        for i, chunk in enumerate(file_data["processed_chunks"]):
            cid        = f"{doi_prefix}::{chunk['id']}"
            meta       = chunk.get("metadata", {})
            full_text  = chunk["text"]  # AI prefix + section text
            chunk_type = chunk.get("type", "text")

            # ── html_scrape: plain text, figures=[IMAGE], tables=caption only
            #    Simulates what a standard RAG pipeline gets from publisher HTML
            parts     = full_text.split("\n\n", 1)
            core_text = parts[1] if len(parts) == 2 else full_text
            if chunk_type == "figure":
                text_html = "[IMAGE]"
            elif chunk_type == "table":
                caption = chunk.get("caption", "")
                text_html = f"[TABLE]{(': ' + caption[:300]) if caption else ': visual content only, structure not available'}"
            else:
                text_html = core_text

            # ── entity_enriched: entity tags + AI prefix + section text
            #    Full Beacon enrichment — used by /ask hybrid search
            entities    = _get_entities(client, chunk)
            text_entity = tag_string(entities) + full_text

            chroma_meta = {
                "source":            file_data["source_file"],
                "doi":               file_data.get("article_doi", ""),
                "type":              chunk.get("type", ""),
                "section":           chunk.get("section") or "",
                "title":             meta.get("title", "")[:100],
                "publication_date":  meta.get("publication_date", ""),
                "entities":          json.dumps(entities),
                "figure_refs":       json.dumps(chunk.get("figure_refs", [])),
                "cited_in":          json.dumps(chunk.get("cited_in", [])),
            }

            ids_html.append(cid);   texts_html.append(text_html[:1500]);     metas_html.append(chroma_meta)
            ids_entity.append(cid); texts_entity.append(text_entity[:1500]); metas_entity.append(chroma_meta)

            label = chunk.get("section") or chunk.get("type") or "chunk"
            ent_summary = f"({len(entities)} entities)" if entities else "(no entities)"
            print(f"    [{i+1}/{len(file_data['processed_chunks'])}] {file_data['source_file']} · {label[:30]} {ent_summary}")

    BATCH = 20

    def add_batches(col, ids, texts, metas):
        for i in range(0, len(ids), BATCH):
            embs = embed(client, texts[i:i+BATCH])
            col.add(ids=ids[i:i+BATCH], embeddings=embs,
                    documents=texts[i:i+BATCH], metadatas=metas[i:i+BATCH])

    print(f"\n  Embedding into collections...")
    print("  [html_scrape]     ", end="", flush=True)
    add_batches(col_html, ids_html, texts_html, metas_html)
    print("done")
    print("  [entity_enriched] ", end="", flush=True)
    add_batches(col_entity, ids_entity, texts_entity, metas_entity)
    print("done")

    return col_html, col_entity


# ─── Query & Compare ─────────────────────────────────────────────────────────

def query_collection(client: OpenAI, collection, query: str, n: int = 3) -> list[dict]:
    q_embed = embed(client, [query])[0]
    results = collection.query(query_embeddings=[q_embed], n_results=n)
    hits = []
    for i in range(len(results["ids"][0])):
        m = results["metadatas"][0][i]
        hits.append({
            "id":       results["ids"][0][i],
            "distance": round(results["distances"][0][i], 4),
            "section":  m.get("section", ""),
            "type":     m.get("type", ""),
            "source":   m.get("source", ""),
            "entities": json.loads(m.get("entities", "[]")),
            "snippet":  results["documents"][0][i][:200].replace("\n", " "),
        })
    return hits


def run_experiment(col_html, col_entity, client: OpenAI, top_k: int = 3):
    results = {}
    print(f"\n{'='*80}")
    print("RETRIEVAL EXPERIMENT  -  Standard RAG (html_scrape) vs Beacon (entity_enriched)")
    print(f"Embedding: {EMBED_MODEL}  |  Top-K: {top_k}")
    print("=" * 80)

    for query in QUERIES:
        print(f'\nQUERY: "{query}"')
        print("-" * 80)
        hits_html   = query_collection(client, col_html,   query, top_k)
        hits_entity = query_collection(client, col_entity, query, top_k)

        for rank, (h, t) in enumerate(zip(hits_html, hits_entity), 1):
            print(f"  #{rank}  standard={h['distance']:.4f} [{h['source'][:15]}/{h['section'][:10]}]  "
                  f"beacon={t['distance']:.4f} {[x['text'] for x in t['entities'][:3]]}")

        results[query] = {"standard": hits_html, "beacon": hits_entity}

    return results


def score_results(results: dict):
    print(f"\n{'='*80}")
    print("SUMMARY  (lower distance = better rank-1 match)")
    print(f"{'Query':<50} {'STANDARD':>10} {'BEACON':>8}")
    print("-" * 80)
    std_w = beacon_w = 0
    for query, hits in results.items():
        dh = hits["standard"][0]["distance"] if hits.get("standard") else 9.9
        dt = hits["beacon"][0]["distance"]   if hits.get("beacon")   else 9.9
        if dh <= dt: std_w    += 1; winner = "standard"
        else:        beacon_w += 1; winner = "beacon"
        print(f"  {query[:48]:<48} {dh:>10.4f} {dt:>8.4f}  ← {winner}")
    total = len(results)
    print("-" * 80)
    print(f"  Rank-1 wins:  standard={std_w}/{total}  beacon={beacon_w}/{total}")
    print("=" * 80)


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k",  type=int, default=3)
    parser.add_argument("--output", default="experiment_results.json")
    args = parser.parse_args()

    client = OpenAI()
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # Auto-discover all chunk files
    print("\nLoading chunk files...")
    chunks_by_file = []
    for path in sorted(CHUNKS_DIR.glob("*_chunks.json")):
        with open(path) as f:
            data = json.load(f)
        chunks_by_file.append(data)
        print(f"  {path.name}: {data['total_chunks']} chunks")

    if not chunks_by_file:
        print("No chunk files found. Run pipeline.py on XML files first.")
        return

    print("\nBuilding collections...")
    col_html, col_entity = build_collections(client, chroma, chunks_by_file)

    results = run_experiment(col_html, col_entity, client, top_k=args.top_k)
    score_results(results)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
