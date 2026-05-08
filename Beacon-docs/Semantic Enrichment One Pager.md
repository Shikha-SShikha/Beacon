# Semantic Content Enrichment — One Pager
*Prototype 7 · Scientific Articles → AI-Enriched Search Index*

---

## What We Built

A seven-step enrichment pipeline that takes raw publisher article files and makes them smarter for AI-powered search. Each article is broken into passages, and each passage is annotated with context, key scientific terms, figures, and relationships before being stored in a search index.

| Step | What it does |
|---|---|
| Read & split | Parse the publisher article file, split it into sections and passages, and stitch together passages that are too short to stand alone |
| Add context labels | AI writes a short label for each passage stating which article it is from, what section, who wrote it, and what the topic is — so passages make sense on their own |
| Turn figures into findings | AI reads each figure and table caption and rewrites it as a plain finding ("Treatment X reduced tumour size by 40%") instead of leaving a blank image placeholder |
| Tag key scientific terms | AI identifies genes, diseases, chemicals, cell lines, and organisms mentioned in each passage |
| Link terms to standard IDs | Each tagged term is matched to a shared ID in a public scientific database (e.g. NCBI, MeSH, ChEBI) — so the same entity is recognised across different papers regardless of how it is spelled |
| Extract relationships | AI reads each passage and pulls out explicit relationships between terms — e.g. "Gene X inhibits Protein Y" — so search can answer "what interacts with X?" directly |
| Connect figures to text | Passages that mention a figure are linked to that figure, and vice versa — so evidence in a chart can be found even when the query matches the surrounding text |

*A separate JSON-LD export step (`jsonld_serializer.py`) converts the enriched index into a structured data file where each article is described using standard web vocabularies and all term IDs point to live database records. This is run manually after the main pipeline.*

---

## Failure Modes Addressed

### Reading & Splitting

| Failure Mode | Problem | Solution |
|---|---|---|
| DTD parsing failure | Publisher XML uses a non-standard format that most tools reject outright | Custom parser strips the problematic header and uses fault-tolerant parsing |
| Short passage problem | Very short paragraphs carry no useful meaning on their own | Short passages are merged with neighbours; last sentence of prior passage is prepended |
| Cross-boundary evidence loss | A finding spanning a paragraph boundary gets split across two chunks | One-sentence overlap carries trailing context forward into the next chunk |

### Context Labels

| Failure Mode | Problem | Solution |
|---|---|---|
| Orphaned passages | A passage pulled out of its article looks meaningless without knowing what paper it is from | AI adds a label to every passage: article, section type, first author, and year |
| Section blindness | A methods paragraph and a results paragraph on the same topic look identical to search | Section type is embedded in the label so methods and results are distinguishable |
| Author & recency blindness | No signal in the passage for who wrote it or when | First author and publication year included in every passage label |

### Figures & Tables

| Failure Mode | Problem | Solution |
|---|---|---|
| Blank figure placeholders | Baseline system stored figures as [IMAGE] with no searchable content | AI rewrites each caption as a plain-language finding with specific values |
| Descriptive captions only | Captions describe what a figure contains, not what it proves | Finding is written as a result claim, not a description |
| Numbers visible only in a chart | Values that appear only in the visual (axis labels, bar heights) are not in the caption and cannot be extracted without the image | Current pipeline captures only values stated in the caption. Full extraction requires a separate vision model step — a planned roadmap item |

### Key Term Tagging & ID Linking

| Failure Mode | Problem | Solution |
|---|---|---|
| Same term, different spellings | m6A, N6-methyladenosine, and m⁶A are the same chemical but look different to search | All three resolve to the same database ID and are treated as one entity |
| Opaque abbreviations | Short abbreviations like PAI-1 or YY1 mean nothing to a general search model | Each abbreviation is linked to its full database ID, making it findable by meaning |
| Same entity, different papers | The same gene in two papers appears as two unrelated strings with no connection | Shared database IDs link the same entity across the entire article corpus |
| Mislabelled terms | AI occasionally tags an imaging score as a gene or an author name as a protein | Batch: no gate, errors enter the index. Staged: editor review filters these out before storage |

### Relationships

| Failure Mode | Problem | Solution |
|---|---|---|
| Co-occurrence ≠ interaction | Two terms in the same passage does not mean they interact | Only explicitly stated relationships are stored; proximity alone creates no link |
| Implicit findings | "Knockdown of X reduced Y" not surfaced by a query for "what inhibits X" | AI extracts the explicit triple (X reduces Y) with a supporting evidence snippet |
| Query-predicate mismatch | "What inhibits X" should match a passage asserting Y inhibits X | Predicate stored as a typed field enabling predicate-aware search |

### Vocabulary & Hierarchy

| Failure Mode | Problem | Solution |
|---|---|---|
| Specificity mismatch | A query uses a broad term while the article uses a highly specific one | Medical vocabulary hierarchy matches queries to articles even when the exact term differs |
| Each paper uses its own terms | Vocabulary varies across papers making cross-corpus search unreliable | Broader parent terms stored on each entity normalise upward to shared concepts |

### Figure–Text Linking

| Failure Mode | Problem | Solution |
|---|---|---|
| Split evidence | A finding is described in text but the data is only in the figure | Text passages citing a figure are linked to it; figure is linked back to the citing passage |
| Orphaned figures | A figure with rich quantitative content may not match the query string at all | Figure is surfaced via its linked text passage, which will match the query |

### JSON-LD Export

| Failure Mode | Problem | Solution |
|---|---|---|
| Enrichment is internal only | Without export, all enrichment is locked inside the pipeline and not interoperable | Separate export step writes each article as a structured web document with standard vocabularies |
| Same entity stored many times | The same entity in 12 passages should produce one canonical record, not 12 | Export step deduplicates by entity text and type before writing |
| IDs don't resolve externally | Entity IDs should point to live database records to be truly interoperable | Canonical URLs used for all resolved entities so IDs resolve to live ontology records |

---

## Two Approaches: Batch vs. Embedded in Editorial Workflow

| | Batch (run after publication) | Embedded (runs during editing) |
|---|---|---|
| **When it runs** | After the article is fully produced | During the editorial process, across two stages |
| **Input** | Single final article file | Two files — the draft being edited and the final proof |
| **Term tagging** | AI tags and links all terms in one pass | AI tags terms at draft stage → editor reviews → IDs resolved at final stage |
| **Human review** | None | Editor scans AI-tagged terms and removes obvious mistakes in about a minute |
| **Mislabelled terms** | Enter the search index undetected | Caught by the editor before IDs are looked up; never stored |
| **Output** | Same search-ready file format | Same — compatible with the same search index |
| **Complexity** | One command, one file | Two processing stages plus a review screen |
| **Best for** | Enriching an existing article archive in bulk | New articles passing through an active editorial workflow |

The one meaningful difference: AI occasionally mislabels terms (e.g. an imaging score tagged as a gene, or an author name as a protein). The batch pipeline has no way to catch this — bad labels go straight into the index. The embedded pipeline adds a one-minute editor review that filters these out before they are stored.

Of 22 failure modes: 21 are handled the same way in both approaches · 1 is handled better in the embedded version · 3 (JSON-LD export) require a separate manual step in both.
