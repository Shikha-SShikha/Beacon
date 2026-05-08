"""
Citation Graph Builder

Parses all XML articles, extracts structured references, and builds a
directed citation graph.

  Nodes  — papers: our corpus articles + every paper they reference
  Edges  — "cites" relationships: corpus_article → referenced_paper

Use cases:
  - Foundational papers: external papers cited by the most corpus articles
  - Shared references:   two corpus articles that cite the same paper → same topic
  - Co-cited articles:   corpus articles that appear together in reference lists
  - Reference list:      all papers cited by a specific article

Usage:
    python citation_graph.py            # build graph, print summary
    python citation_graph.py --query    # interactive query shell

Output:
    citation_graph.json
"""

import json
import hashlib
import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree
from pipeline import load_xml, extract_metadata, local, get_text

ARTICLES_DIR = Path(__file__).parent / "articles"
GRAPH_PATH   = Path(__file__).parent / "citation_graph.json"


# ─── Reference Extraction ─────────────────────────────────────────────────────

def _ref_id(title: str, year: str, first_author: str) -> str:
    """
    Stable ID for an external reference, based on title + year + first author.
    Uses a short hash so the same paper cited by two articles gets the same ID.
    """
    raw = f"{title.lower().strip()}|{year}|{first_author.lower().strip()}"
    return "ref:" + hashlib.md5(raw.encode()).hexdigest()[:10]


def extract_references(root: etree._Element, article_doi: str) -> list[dict]:
    """
    Parse <ce:bibliography> and return one dict per reference entry.
    """
    refs = []

    bib = next((el for el in root.iter() if local(el.tag) == "bibliography"), None)
    if bib is None:
        return refs

    for bib_ref in bib.iter():
        if local(bib_ref.tag) != "bib-reference":
            continue

        # Human-readable label: [1], [2], ...
        label_el = next((c for c in bib_ref if local(c.tag) == "label"), None)
        label = get_text(label_el).strip("[] ") if label_el is not None else ""

        # Formatted citation string — easiest to display
        src_el = next((c for c in bib_ref if local(c.tag) == "source-text"), None)
        source_text = get_text(src_el) if src_el is not None else ""

        # Structured fields from <sb:reference>
        title, journal, year, volume, first_page = "", "", "", "", ""
        authors: list[str] = []

        sb_ref = next((c for c in bib_ref.iter() if local(c.tag) == "reference"), None)
        if sb_ref is None:
            continue

        for el in sb_ref.iter():
            tag = local(el.tag)

            # Authors
            if tag == "author":
                surname  = next((get_text(c) for c in el if local(c.tag) == "surname"),    "")
                given    = next((get_text(c) for c in el if local(c.tag) == "given-name"), "")
                name = f"{surname}, {given}".strip(", ")
                if name:
                    authors.append(name)

            # maintitle appears twice: once for article title, once for journal name
            # Disambiguate by walking the parent chain
            elif tag == "maintitle":
                parent      = el.getparent()
                grandparent = parent.getparent() if parent is not None else None
                great       = grandparent.getparent() if grandparent is not None else None

                if grandparent is not None and local(grandparent.tag) == "contribution":
                    title = get_text(el)                 # article title
                elif grandparent is not None and local(grandparent.tag) == "series":
                    journal = get_text(el)               # journal name

            elif tag == "date" and not year:
                year = get_text(el)
            elif tag == "volume-nr" and not volume:
                volume = get_text(el)
            elif tag == "first-page" and not first_page:
                first_page = get_text(el)
            elif tag == "article-number" and not first_page:
                first_page = get_text(el)

        if not title and not source_text:
            continue

        first_author = authors[0].split(",")[0] if authors else "unknown"
        ref_id = _ref_id(title or source_text, year, first_author)

        refs.append({
            "id":          ref_id,
            "label":       label,
            "title":       title,
            "authors":     authors,
            "year":        year,
            "journal":     journal,
            "volume":      volume,
            "first_page":  first_page,
            "source_text": source_text,
            "cited_by":    article_doi,
        })

    return refs


# ─── Graph Builder ────────────────────────────────────────────────────────────

def build_graph() -> dict:
    """
    Parse all XML articles and build the citation graph.

    Returns a dict with:
        nodes  — {id: {title, authors, year, journal, type: "corpus"|"external"}}
        edges  — [{from, to, label}]
        index  — {ref_id: [corpus_doi, ...]}   (inverted index: who cites what)
    """
    nodes: dict[str, dict] = {}
    edges: list[dict]      = []
    index: dict[str, list] = defaultdict(list)  # ref_id → [citing_doi, ...]

    xml_files = sorted(ARTICLES_DIR.glob("*.xml"))

    for xml_path in xml_files:
        root     = load_xml(str(xml_path))
        metadata = extract_metadata(root)
        doi      = metadata.get("doi") or metadata.get("article_id") or xml_path.stem

        # Add corpus article as a node
        nodes[doi] = {
            "id":      doi,
            "title":   metadata.get("title", ""),
            "authors": metadata.get("authors", []),
            "year":    (metadata.get("publication_date") or "")[:4],
            "journal": metadata.get("journal_id", ""),
            "type":    "corpus",
            "source":  xml_path.name,
        }

        # Extract and record references
        refs = extract_references(root, doi)
        for ref in refs:
            ref_id = ref["id"]

            # Add external paper as a node (first encounter wins)
            if ref_id not in nodes:
                nodes[ref_id] = {
                    "id":          ref_id,
                    "title":       ref["title"],
                    "authors":     ref["authors"],
                    "year":        ref["year"],
                    "journal":     ref["journal"],
                    "source_text": ref["source_text"],
                    "type":        "external",
                }

            # Add citation edge
            edges.append({
                "from":  doi,
                "to":    ref_id,
                "label": ref["label"],
            })

            # Update inverted index
            index[ref_id].append(doi)

        print(f"  {xml_path.stem:20s}  {len(refs):3d} references")

    # Stats
    corpus_nodes   = sum(1 for n in nodes.values() if n["type"] == "corpus")
    external_nodes = sum(1 for n in nodes.values() if n["type"] == "external")
    print(f"\n  {corpus_nodes} corpus articles  |  {external_nodes} unique external references  |  {len(edges)} citation edges")

    return {
        "nodes": nodes,
        "edges": edges,
        "index": dict(index),
    }


def save_graph(graph: dict, path: Path = GRAPH_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved → {path}")


def load_graph(path: Path = GRAPH_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


# ─── Query Functions ──────────────────────────────────────────────────────────

def get_references(graph: dict, doi: str) -> list[dict]:
    """All papers cited by a corpus article."""
    return [
        graph["nodes"][e["to"]]
        for e in graph["edges"]
        if e["from"] == doi and e["to"] in graph["nodes"]
    ]


def get_citing_articles(graph: dict, ref_id: str) -> list[dict]:
    """Corpus articles that cite a given reference."""
    citing_dois = graph["index"].get(ref_id, [])
    return [graph["nodes"][d] for d in citing_dois if d in graph["nodes"]]


def get_most_cited(graph: dict, n: int = 15) -> list[tuple[dict, int]]:
    """
    External papers cited by the most corpus articles.
    These are the 'foundational' papers for the corpus as a whole.
    """
    counts = Counter({
        ref_id: len(citers)
        for ref_id, citers in graph["index"].items()
        if graph["nodes"].get(ref_id, {}).get("type") == "external"
    })
    return [
        (graph["nodes"][ref_id], count)
        for ref_id, count in counts.most_common(n)
    ]


def get_shared_references(graph: dict, doi_a: str, doi_b: str) -> list[dict]:
    """
    Papers cited by BOTH doi_a and doi_b.
    Articles that share many references are likely discussing the same topic or
    building on the same prior work.
    """
    refs_a = {e["to"] for e in graph["edges"] if e["from"] == doi_a}
    refs_b = {e["to"] for e in graph["edges"] if e["from"] == doi_b}
    shared = refs_a & refs_b
    return [graph["nodes"][r] for r in shared if r in graph["nodes"]]


def get_co_cited_articles(graph: dict, doi: str) -> list[tuple[dict, int]]:
    """
    Other corpus articles that share the most references with doi.
    High overlap = likely related topic.
    """
    our_refs = {e["to"] for e in graph["edges"] if e["from"] == doi}
    overlap: Counter = Counter()
    for edge in graph["edges"]:
        if edge["from"] != doi and edge["to"] in our_refs:
            overlap[edge["from"]] += 1

    return [
        (graph["nodes"][d], count)
        for d, count in overlap.most_common()
        if d in graph["nodes"]
    ]


def get_foundational_for_chunks(graph: dict, dois: list[str], n: int = 5) -> list[tuple[dict, int]]:
    """
    Given a list of retrieved corpus article DOIs, find the external papers
    most cited across those articles.
    Answers: 'What is the foundational paper behind these results?'
    """
    ref_counts: Counter = Counter()
    for edge in graph["edges"]:
        if edge["from"] in dois:
            ref_counts[edge["to"]] += 1

    return [
        (graph["nodes"][ref_id], count)
        for ref_id, count in ref_counts.most_common(n)
        if ref_id in graph["nodes"] and graph["nodes"][ref_id]["type"] == "external"
    ]


# ─── Display Helpers ──────────────────────────────────────────────────────────

def _fmt_node(node: dict, count: int | None = None) -> str:
    authors = node.get("authors", [])
    first   = authors[0].split(",")[0] if authors else "?"
    et_al   = " et al." if len(authors) > 1 else ""
    year    = node.get("year", "?")
    title   = node.get("title", node.get("source_text", "?"))[:70]
    journal = node.get("journal", "")
    count_s = f"  [cited by {count} article{'s' if count != 1 else ''}]" if count else ""
    return f"{first}{et_al} ({year}) — {title}  [{journal}]{count_s}"


def print_summary(graph: dict):
    corpus = [n for n in graph["nodes"].values() if n["type"] == "corpus"]
    print(f"\n{'='*70}")
    print("CORPUS ARTICLES")
    print('='*70)
    for n in sorted(corpus, key=lambda x: x.get("year", "")):
        ref_count = sum(1 for e in graph["edges"] if e["from"] == n["id"])
        print(f"  {n['id'][:35]:35s}  {n['year']}  refs={ref_count}")

    print(f"\n{'='*70}")
    print("TOP 15 MOST-CITED EXTERNAL PAPERS (foundational across corpus)")
    print('='*70)
    for node, count in get_most_cited(graph, 15):
        print(f"  [{count:2d}x]  {_fmt_node(node)}")


# ─── Interactive Query Shell ───────────────────────────────────────────────────

def _query_shell(graph: dict):
    corpus = {n["id"]: n for n in graph["nodes"].values() if n["type"] == "corpus"}

    print("\nCorpus articles:")
    for i, (doi, node) in enumerate(sorted(corpus.items()), 1):
        print(f"  {i:2d}.  {doi:40s}  {node.get('title','')[:50]}")

    while True:
        print("\nCommands:")
        print("  refs <number>   — show references of an article")
        print("  shared <n> <n>  — shared references between two articles")
        print("  related <n>     — most topic-related articles")
        print("  top             — top cited papers across corpus")
        print("  q               — quit")
        cmd = input("\n> ").strip().lower()

        if cmd in ("q", "quit"):
            break
        elif cmd == "top":
            print()
            for node, count in get_most_cited(graph, 10):
                print(f"  [{count}x] {_fmt_node(node)}")
        elif cmd.startswith("refs "):
            try:
                idx   = int(cmd.split()[1]) - 1
                doi   = list(sorted(corpus.keys()))[idx]
                refs  = get_references(graph, doi)
                print(f"\n  References in {doi} ({len(refs)} total):")
                for r in refs[:20]:
                    print(f"    {_fmt_node(r)}")
                if len(refs) > 20:
                    print(f"    ... and {len(refs)-20} more")
            except (ValueError, IndexError):
                print("  Usage: refs <number>")
        elif cmd.startswith("shared "):
            parts = cmd.split()
            try:
                doi_a = list(sorted(corpus.keys()))[int(parts[1]) - 1]
                doi_b = list(sorted(corpus.keys()))[int(parts[2]) - 1]
                shared = get_shared_references(graph, doi_a, doi_b)
                a_title = corpus[doi_a].get("title", "")[:40]
                b_title = corpus[doi_b].get("title", "")[:40]
                print(f"\n  Shared references between:")
                print(f"    A: {a_title}")
                print(f"    B: {b_title}")
                print(f"  {len(shared)} shared reference(s):")
                for r in shared:
                    print(f"    {_fmt_node(r)}")
            except (ValueError, IndexError):
                print("  Usage: shared <number> <number>")
        elif cmd.startswith("related "):
            try:
                idx = int(cmd.split()[1]) - 1
                doi = list(sorted(corpus.keys()))[idx]
                related = get_co_cited_articles(graph, doi)
                print(f"\n  Articles most related to {doi}:")
                for node, count in related[:8]:
                    print(f"    [{count} shared refs]  {node.get('title','')[:60]}")
            except (ValueError, IndexError):
                print("  Usage: related <number>")
        else:
            print("  Unknown command.")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query",  action="store_true", help="Launch interactive query shell after building")
    parser.add_argument("--load",   action="store_true", help="Load existing graph instead of rebuilding")
    args = parser.parse_args()

    if args.load and GRAPH_PATH.exists():
        print(f"Loading graph from {GRAPH_PATH}...")
        graph = load_graph()
    else:
        print("Building citation graph from XML articles...")
        graph = build_graph()
        save_graph(graph)

    print_summary(graph)

    if args.query:
        _query_shell(graph)
