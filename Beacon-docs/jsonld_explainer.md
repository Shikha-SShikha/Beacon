# Understanding JSON-LD in the Beacon Pipeline

## What it is

JSON-LD (JSON for Linked Data) is a standard web format that makes data machine-readable across any system — without those systems needing to know your custom schema.

Our chunks JSON is internal format: field names like `"ontology": "NCBI Gene"` and `"id": "56339"` only mean something because our pipeline code knows how to interpret them.

JSON-LD makes the same data universally interpretable by using `@context` and `@id`.

---

## The two key ideas

### @context — defines shorthand prefixes

```json
"@context": {
  "schema": "https://schema.org/",
  "beacon": "https://beacon-enrichment.io/vocab#"
}
```

This means `schema:name` is shorthand for `https://schema.org/name` — a globally recognised property. Any system that follows schema.org standards already knows what it means. You don't have to explain your field names.

### @id — declares identity, not just a URL

```json
{
  "@id": "https://www.ncbi.nlm.nih.gov/gene/56339",
  "schema:name": "METTL3",
  "beacon:entityType": "PROTEIN"
}
```

This is not just storing a URL you could click. It is saying:

> "The text entity METTL3 **is** the thing at this URL. They are the same node."

The URL still works in a browser — that hasn't changed. The difference is that a machine can now treat the URL as a **canonical identity**, not just a string.

---

## Before and after

**In our chunks JSON:**
```json
{ "text": "METTL3", "type": "PROTEIN", "id": "56339", "ontology": "NCBI Gene" }
```
Four strings. A machine reading this has to know our schema to understand what `"NCBI Gene"` means or how `"56339"` maps to a URL.

**In JSON-LD:**
```json
{
  "@id": "https://www.ncbi.nlm.nih.gov/gene/56339",
  "@type": "schema:Thing",
  "schema:name": "METTL3",
  "beacon:entityType": "PROTEIN"
}
```
The entity is now a linked node. Any system — Google, a hospital knowledge graph, a SPARQL database — can read this without any custom code.

---

## The key benefit: identity across documents

If BJ_100828 and BJ_100850 both mention METTL3, both will have:
```json
"@id": "https://www.ncbi.nlm.nih.gov/gene/56339"
```

A knowledge graph automatically merges them — no string matching, no custom script. It knows they refer to the same thing because the `@id` matches.

**The analogy:** Two contact cards both say "John Smith" — you don't know if it's the same person. Two JSON-LD nodes both say `@id: linkedin.com/in/johnsmith123` — unambiguously the same person, across any system.

---

## What our serializer does (jsonld_serializer.py)

```
chunks/BJ_100828_chunks.json  →  jsonld/BJ_100828.jsonld
```

| Our chunk field | JSON-LD equivalent |
|---|---|
| Article DOI | `@id: https://doi.org/{doi}` |
| `"type": "PROTEIN", "id": "56339"` | `@id: https://www.ncbi.nlm.nih.gov/gene/56339` |
| `"type": "DISEASE", "id": "DOID:3733"` | `@id: http://purl.obolibrary.org/obo/DOID_3733` |
| Text chunks | `schema:hasPart` array |
| Figures | `schema:image` array |
| Tables | `schema:table` array |
| Relations (triples) | `beacon:relations` with subject/predicate/object |

---

## What you gain vs. not having it

| Without JSON-LD | With JSON-LD |
|---|---|
| `"METTL3"` — just a string | `@id: ncbi.nlm.nih.gov/gene/56339` — a linked node |
| Only our pipeline understands the schema | Any schema.org-compatible system can parse it |
| Entities isolated per article | Same entity across 15 articles resolves to one canonical record |
| ChromaDB / Python only | Indexable by Google, loadable into knowledge graphs, queryable with SPARQL |

---

## What doesn't change

- The URL still works if you paste it in a browser — that was always true
- The chunks JSON still works for ChromaDB — JSON-LD is an *additional* export, not a replacement
- Nothing in the pipeline breaks without JSON-LD; it's a layer on top for interoperability
