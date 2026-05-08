"""
Citation context service.

Wraps citation_graph.json to answer three questions per result card:
  1. Related corpus articles  - articles sharing the most references (same topic)
  2. By same author           - other corpus articles by the same author(s)
  3. Foundational references  - external papers cited by multiple corpus articles

Also answers a query-level question:
  4. Foundational for a set   - papers most cited across a returned result set
"""

import json
from pathlib import Path
from collections import Counter

GRAPH_PATH = Path(__file__).parent.parent.parent / "citation_graph.json"

_graph: dict | None = None


def _get_graph() -> dict:
    global _graph
    if _graph is None:
        _graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    return _graph


def get_context(source: str) -> dict:
    """
    Given a source filename (e.g. 'BJ_100828.xml'), return citation context:
      - related_corpus: top-3 corpus articles with most shared references
      - by_same_author: other corpus articles sharing ≥1 author surname
      - foundational:   top-5 external refs from this article also cited elsewhere
    """
    graph = _get_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]
    index = graph.get("index", {})

    corpus_node = next(
        (n for n in nodes.values() if n.get("type") == "corpus" and n.get("source") == source),
        None,
    )
    if corpus_node is None:
        return {"related_corpus": [], "by_same_author": [], "foundational": []}

    doi = corpus_node["id"]
    our_refs = {e["to"] for e in edges if e["from"] == doi}
    our_surnames = {a.split(",")[0].strip().lower() for a in corpus_node.get("authors", []) if a}

    # 1. Related corpus articles - highest shared-reference overlap
    overlap: Counter = Counter()
    for edge in edges:
        if edge["from"] != doi and edge["to"] in our_refs:
            overlap[edge["from"]] += 1

    related_corpus = []
    for other_doi, count in overlap.most_common(3):
        n = nodes.get(other_doi)
        if n and n.get("type") == "corpus":
            related_corpus.append({
                "doi": other_doi,
                "title": n.get("title", ""),
                "authors": n.get("authors", []),
                "year": n.get("year", ""),
                "journal_code": n.get("journal", ""),
                "source": n.get("source", ""),
                "shared_refs": count,
            })

    # 2. By same author
    by_same_author = []
    for node in nodes.values():
        if node.get("type") != "corpus" or node["id"] == doi:
            continue
        node_surnames = {a.split(",")[0].strip().lower() for a in node.get("authors", []) if a}
        shared = our_surnames & node_surnames
        if shared:
            by_same_author.append({
                "doi": node["id"],
                "title": node.get("title", ""),
                "authors": node.get("authors", []),
                "year": node.get("year", ""),
                "journal_code": node.get("journal", ""),
                "source": node.get("source", ""),
                "shared_authors": sorted(shared),
            })

    # 3. Foundational refs - external refs from this article most cited across corpus
    ref_corpus_count: Counter = Counter()
    for ref_id in our_refs:
        citers = index.get(ref_id, [])
        if len(citers) > 0:
            ref_corpus_count[ref_id] = len(citers)

    foundational = []
    for ref_id, count in ref_corpus_count.most_common(5):
        n = nodes.get(ref_id)
        if n:
            foundational.append({
                "title": n.get("title") or n.get("source_text", ""),
                "authors": n.get("authors", []),
                "year": n.get("year", ""),
                "journal": n.get("journal", ""),
                "cited_by_corpus": count,
            })

    return {
        "related_corpus": related_corpus,
        "by_same_author": by_same_author,
        "foundational": foundational,
    }


def get_foundational_for_sources(sources: list[str]) -> list[dict]:
    """
    Given a list of source filenames, find the external papers most cited
    across those corpus articles. Surfaces the shared intellectual foundation
    of a result set.
    """
    graph = _get_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    source_dois = {
        n["id"]
        for n in nodes.values()
        if n.get("type") == "corpus" and n.get("source") in sources
    }

    ref_counts: Counter = Counter()
    for edge in edges:
        if edge["from"] in source_dois:
            ref_counts[edge["to"]] += 1

    result = []
    for ref_id, count in ref_counts.most_common(5):
        n = nodes.get(ref_id)
        if n and n.get("type") == "external":
            result.append({
                "title": n.get("title") or n.get("source_text", ""),
                "authors": n.get("authors", []),
                "year": n.get("year", ""),
                "journal": n.get("journal", ""),
                "cited_by_count": count,
            })

    return result
