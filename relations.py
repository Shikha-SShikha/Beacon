"""
Relation & Event Extraction — Step 5b

Extracts typed subject-predicate-object triples from enriched chunks.
Runs after NER (Step 5) so entity names are already confirmed.

Triple format:
  {
    "subject":   "METTL3",
    "predicate": "methylates",
    "object":    "m6A",
    "evidence":  "METTL3 methylates m6A on mRNA transcripts"   # verbatim snippet
  }

Domain-specific predicate vocabularies keep triples meaningful per journal type:
  BJ / REDOX  → molecular biology predicates
  PLAS        → project management / social science predicates
  ESR         → energy systems / engineering predicates
"""

import json
from openai import OpenAI

# ─── Domain predicate sets ────────────────────────────────────────────────────

_PREDICATES: dict[str, str] = {
    "BJ": (
        "regulates, inhibits, activates, binds, methylates, demethylates, "
        "phosphorylates, promotes, suppresses, causes, treats, associated_with, "
        "encodes, produces, interacts_with, cleaves, recruits, stabilizes, degrades"
    ),
    "REDOX": (
        "regulates, inhibits, activates, oxidizes, reduces, generates, scavenges, "
        "promotes, suppresses, causes, treats, associated_with, induces, protects_against, "
        "interacts_with, modulates, mediates, triggers"
    ),
    "PLAS": (
        "enables, constrains, influences, implements, evaluates, supports, conflicts_with, "
        "extends, applies_to, depends_on, validates, challenges, integrates_with"
    ),
    "ESR": (
        "uses, produces, measures, optimizes, affects, requires, improves, reduces, "
        "integrates_with, replaces, models, evaluates, compares, scales_with"
    ),
}
_DEFAULT_PREDICATES = (
    "relates_to, causes, enables, supports, contradicts, produces, requires, associated_with"
)

# ─── Extraction ───────────────────────────────────────────────────────────────

def extract_relations(client: OpenAI, chunk: dict) -> list[dict]:
    """
    Extract semantic triples from a text chunk.

    Uses already-extracted entities as anchors for higher precision.
    Returns up to 5 triples per chunk.
    """
    text = chunk.get("text", "")[:900]
    if not text.strip():
        return []

    journal = chunk.get("metadata", {}).get("journal_id", "").upper()
    predicates = _PREDICATES.get(journal, _DEFAULT_PREDICATES)

    # Format confirmed entities as anchor hints
    entities = chunk.get("entities", [])
    entity_hints = ""
    if entities:
        names = [e["text"] for e in entities[:10]]
        entity_hints = f"\nKnown entities in this chunk: {', '.join(names)}\n"

    prompt = f"""Extract semantic relations from this scientific text as subject-predicate-object triples.
{entity_hints}
Allowed predicates: {predicates}

Text:
{text}

Rules:
- Only extract relations between named entities that appear explicitly in the text
- Subject and object must be specific named entities (genes, proteins, chemicals, concepts, technologies, etc.), not generic words
- Evidence must be a verbatim phrase from the text (max 120 chars) showing the relation
- Up to 5 triples maximum
- Return [] if no clear named-entity relations exist

Return JSON array only, no extra text:
[{{"subject": "...", "predicate": "...", "object": "...", "evidence": "..."}}]"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=400,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract semantic relations from scientific text as structured triples. "
                        "Be precise: only extract relations that are explicitly stated, not implied."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.strip("` \n").removeprefix("json").strip()
        parsed = json.loads(raw)
        return [
            {
                "subject":   r["subject"],
                "predicate": r["predicate"],
                "object":    r["object"],
                "evidence":  r.get("evidence", ""),
            }
            for r in parsed
            if isinstance(r, dict)
            and r.get("subject") and r.get("predicate") and r.get("object")
        ]
    except Exception:
        return []
