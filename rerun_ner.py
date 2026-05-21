"""
Targeted re-NER: re-runs entity extraction on chunk files that were
processed with the wrong domain hint (missing journal ID mappings).
Updates chunk JSONs in-place. Does NOT re-embed or re-index ChromaDB.
"""
import json
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from ner import enrich_entities

CHUNKS_DIR = Path(__file__).parent / "chunks"

# Files to reprocess: PII → correct journal_id
TARGETS = {
    "S0753332224001124_chunks.json": "BIOPHA",
    "S1818087624000564_chunks.json": "AJPS",
    "S2211124725015803_chunks.json": "CELREP",
    "S2352304225003629_chunks.json": "GENDIS",
    "S2468294225000504_chunks.json": "CTARC",
    "S3050538025000432_chunks.json": "CLNVES",
}

client = OpenAI()

for filename, journal_id in TARGETS.items():
    path = CHUNKS_DIR / filename
    if not path.exists():
        print(f"SKIP (not found): {filename}")
        continue

    data = json.loads(path.read_text())
    chunks = data.get("processed_chunks", [])
    print(f"\n{'='*60}")
    print(f"{filename} ({journal_id}) — {len(chunks)} chunks")

    total_entities = 0
    total_with_id = 0

    for i, chunk in enumerate(chunks, 1):
        # Inject correct journal_id into metadata so NER picks up the right hint
        meta = chunk.get("metadata", {})
        if isinstance(meta, dict):
            meta["journal_id"] = journal_id
            chunk["metadata"] = meta
        else:
            chunk["metadata"] = {"journal_id": journal_id}

        label = (chunk.get("section") or chunk.get("type") or "chunk")[:40]
        print(f"  [{i:3d}/{len(chunks)}] {label}", end=" ", flush=True)

        entities = enrich_entities(client, chunk)
        chunk["entities"] = entities

        n = len(entities)
        ids_found = sum(1 for e in entities if e.get("id"))
        total_entities += n
        total_with_id += ids_found
        print(f"→ {n} entities ({ids_found} with IDs)")

    # Recalculate totals
    data["processed_chunks"] = chunks
    data["total_entities"] = sum(len(c.get("entities", [])) for c in chunks)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  SAVED — {total_entities} entities ({total_with_id} ontology-linked)")

print("\nDone. Restart the backend to reload updated entity data.")
