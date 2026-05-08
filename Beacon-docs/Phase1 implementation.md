# Phase 1 — Chunking Overhaul

**Addresses:** B1 (buried findings), B3 (cross-chunk dependency), B4 (granularity mismatch), truncation crisis

**Status:** Complete

---

## Problem

Section-level chunking produced ~7 chunks per article. With the 1,500-char embed limit:
- `ESR-102126`: avg chunk = 31,065 chars → only ~5% embedded
- `BJ_100828`: avg chunk = 8,345 chars → only ~18% embedded
- Content wasn't "buried" — it literally didn't exist in the index

---

## What Was Built

### 1. Paragraph-Level Chunking

Replaced one-chunk-per-section with one-chunk-per-paragraph at XML `<ce:para>` boundaries.

**Function:** `extract_section_chunks()` in `pipeline.py:171`

- Recursively collects paragraphs via `_collect_paragraphs()` (line 233)
- Preserves subsection context by prepending `### {subsection_title}` to the first paragraph of each subsection
- Stores `parent_section_id` and `paragraph_index` as metadata for context retrieval

### 2. Small Paragraph Merging

**Function:** `_merge_small_paragraphs()` in `pipeline.py:310`

- Paragraphs under `min_size=200` chars are merged forward with the next paragraph
- Merging continues until combined text exceeds `target_min=300` chars
- Only merges within the same subsection (subsection boundary = merge boundary)
- Prevents micro-chunks that would waste embedding slots

### 3. Cross-Chunk Overlap

**Function:** `_add_overlap()` in `pipeline.py:339`

- Prepends the last sentence of the previous paragraph to each chunk
- Creates 1-sentence overlap between consecutive chunks within the same section
- Addresses failure mode B3 (cross-chunk dependency)
- Sentence splitting via regex: `(?<=[.!?])\s+`
- Only applies when previous paragraph has >= 2 sentences (avoids duplicating very short paragraphs)

### 4. Section Role Normalisation

**Function:** `_normalise_role()` in `pipeline.py:292`

Maps XML `role` attributes and title text to canonical section types:
- `introduction`, `methods`, `results`, `discussion`, `conclusion`, `other`
- Keyword matching on both role and title (handles inconsistent XML tagging)

---

## Results

| Metric | Before (section-level) | After (paragraph-level) |
|---|---|---|
| Total chunks (15 articles) | ~105 (~7/article) | 903 |
| Avg chunk size | ~6,808 chars | ~400-600 chars |
| Content indexed (at 1500-char limit) | ~5-22% | ~100% |
| ESR-102126 chunks | 5 | 225 |
| BJ_100828 chunks | ~7 | 52 |

### Chunk distribution by article

| Article | Chunks |
|---|---|
| BJ_100828 | 52 |
| BJ_100833 | 30 |
| BJ_100840 | 28 |
| BJ_100850 | 19 |
| BJ_100854 | 15 |
| BJ_100876 | 50 |
| BJ_100877 | 37 |
| BJ_100885 | 41 |
| BJ_100950 | 46 |
| ESR-102001 | 119 |
| ESR-102126 | 225 |
| PLAS-100213 | 80 |
| PLAS-100214 | 98 |
| REDOX-104080 | 0 |
| REDOX-104085 | 63 |
| **Total** | **903** |

### REDOX-104080: 0 chunks (expected)

This is a corrigendum (`<simple-article docsubtype="err">`), not a research article. It has 2 bare `<ce:para>` elements directly under `<ce:sections>` with no wrapping `<section>` tag. The parser correctly skips it — no meaningful content to chunk.

---

## Chunk Schema

```json
{
  "chunk_id": "article-10-1042-BCJ20240535-sec1-p0",
  "type": "text",
  "section_type": "introduction",
  "section_title": "Introduction:",
  "subsection_title": null,
  "paragraph_index": 0,
  "parent_section_id": "sec1",
  "chunk_text": "This introduction section from... [AI prefix]\n\n[paragraph text]",
  "metadata": {
    "journal_id": "BJ",
    "article_id": "100828",
    "doi": "10.1042/BCJ20240535",
    "title": "...",
    "authors": [...],
    "publication_date": "2025-01-02",
    "abstract": "...",
    "keywords": [...]
  }
}
```

---

## Files Changed

| File | Change |
|---|---|
| `pipeline.py` | Rewrote `extract_section_chunks()`. Added `_collect_paragraphs()`, `_merge_small_paragraphs()`, `_add_overlap()`, `_normalise_role()`. |
| `chunks/*.json` | All 15 articles re-processed with paragraph-level chunks. |

---

## Known Issue

The docstring on `extract_section_chunks()` (line 172-174) still says "Extract one chunk per top-level section" — stale from before the overhaul. The function now extracts one chunk per paragraph.
