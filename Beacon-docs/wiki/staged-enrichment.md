# Staged Enrichment (HITL POC)

**Status:** Complete — both stage scripts and review app built and tested.

---

## Concept

Embed semantic enrichment into the editorial workflow at two human-in-the-loop (HITL) touchpoints, rather than running as a post-publication batch job.

Two XML versions of the same article represent two editorial stages:
- **Copyedited XML** (`Copyedit.xml`) — copyeditor has reviewed
- **Proofed XML** (`Proof .xml`) — author/editor has approved

---

## Stage 1: Copyedit → Draft Enrichment

**Script:** `stage_copyedit.py`
**Input:** `Copyedit.xml`
**Output:** `.tmp/enrichment_copyedit.json`

Runs NER Stage 1 on the copyedited XML. Extracts entity names and types (GENE, DISEASE, CHEMICAL, CELL_LINE, ORGANISM, METHOD, etc.). All entities marked `status: draft`.

No ontology ID resolution at this stage — that requires the final proofed text.

---

## Human Review

**Script:** `review_app.py`
**Run:** `streamlit run review_app.py`

Streamlit HITL interface. Shows draft entities grouped by type as coloured chips. Copyeditor/scientist can:
- Click any entity to reject it
- Correct its type via dropdown in the Rejected panel
- Hit **Approve** to write decisions back to the manifest and trigger Stage 2

Decisions stored in the manifest as `status: approved | rejected` with `verified_by` and `verified_at` timestamps.

---

## Stage 2: Mastercopy → Verified Enrichment

**Script:** `stage_mastercopy.py`
**Input:** `Proof .xml` + `.tmp/enrichment_copyedit.json`
**Output:** `.tmp/enrichment_mastercopy.json`

Diffs proofed XML against copyedited XML. On changed sections:
1. Re-runs NER Stage 1 (or full re-run — configured by diff size)
2. Ontology ID resolution: NCBI Gene, MeSH, ChEBI, Cellosaurus, NCBI Taxonomy
3. MeSH hierarchy traversal — broader terms for diseases and chemicals
4. Contextual prefix generation
5. Paragraph chunking with merge and overlap
6. Figure cross-linking

Output manifest has resolved IDs. Entities marked `status: verified`.

---

## Enrichment Manifest Schema

```json
{
  "entities": [
    {
      "text": "METTL3",
      "type": "GENE",
      "status": "approved",
      "ontology_id": "NCBI:56339",
      "verified_by": "copyeditor",
      "verified_at": "2026-04-05T23:04:00Z"
    }
  ],
  "chunks": [...],
  "stage": "mastercopy"
}
```

---

## Post-Publication (Out of POC Scope)

- JSON-LD serialization (needs DOI)
- Embedding + ChromaDB ingestion

These steps would follow the same pipeline.py flow once the article is published and has a DOI.

---

## Files

| File | Purpose |
|---|---|
| `stage_copyedit.py` | Stage 1 runner |
| `stage_mastercopy.py` | Stage 2 runner |
| `review_app.py` | Streamlit HITL review UI |
| `.tmp/enrichment_copyedit.json` | Draft manifest (107KB) |
| `.tmp/enrichment_mastercopy.json` | Verified manifest (179KB) |
| `Copyedit.xml` | Source: copyedited stage (195KB) |
| `Proof .xml` | Source: proofed stage (85KB) |
