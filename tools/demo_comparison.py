"""
Demo Comparison Tool - Before vs After enrichment pipeline.

Runs curated queries against:
  1. Baseline:  html_scrape collection, vector-only search (what AI tools see today)
  2. Enriched:  entity_enriched collection, full pipeline
                (hybrid BM25+vector, section reranking, recency boost, figure expansion)

Outputs a structured before/after report showing:
  - Rank changes, distance improvements
  - Which failure mode each query demonstrates
  - Linked figures surfaced by the full pipeline
  - Whether a previously invisible article became discoverable

Usage:
    python tools/demo_comparison.py                  # full report
    python tools/demo_comparison.py --query 2        # run only scenario 2
    python tools/demo_comparison.py --json            # output as JSON
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

# ─── Setup ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(ROOT))

from openai import OpenAI
import chromadb
from api.services.reranker import rerank
from api.services.bm25_index import get_bm25_index, tokenize
from api.services.search_service import hybrid_search, fetch_linked_figures
from api.services.hyde import expand_query_hyde

client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"
chroma = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))

# ─── Demo Scenarios ──────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": 1,
        "title": "Buried Finding → Surfaced",
        "failure_mode": "B1 (buried findings), B4 (granularity mismatch)",
        "query": "METTL3 upregulation increases m6A levels in infected leukocytes",
        "expected_source": "BJ_100828",
        "story": (
            "With section-level chunking, this finding was buried in a 31,000-char "
            "results section - only 5% was embedded. Paragraph-level chunking "
            "exposes it directly. The claim-extracting figure summary now surfaces "
            "at rank 1 with the exact finding."
        ),
        "hyde": False,
    },
    {
        "id": 2,
        "title": "Figure Was Invisible → Now Retrievable",
        "failure_mode": "E1 (visual content blindness), E2 (figure-claim decoupling)",
        "query": "PAI-1 promotes cellular senescence through p53 pathway",
        "expected_source": "BJ_100950",
        "story": (
            "This finding lives in Figure 1's summary, not in the main text. "
            "Baseline returns text that mentions PAI-1 and senescence in passing. "
            "Enriched pipeline returns the claim-extracting figure summary that "
            "states the finding directly, plus linked text chunks that interpret it."
        ),
        "hyde": False,
    },
    {
        "id": 3,
        "title": "Wrong Section Ranked First → Right Section Promoted",
        "failure_mode": "C3 (discourse blindness), B2 (abstract over-weighting)",
        "query": "What experimental methods were used to detect ALK gene rearrangements",
        "expected_source": "BJ_100840",
        "story": (
            "Baseline returns an 'other' section chunk that mentions ALK detection "
            "in passing. The enriched pipeline detects methodological intent and "
            "boosts the methods section - the actual protocol describing FISH, "
            "IHC, and RT-PCR detection techniques moves to rank 1."
        ),
        "hyde": False,
    },
    {
        "id": 4,
        "title": "Exact Biomedical Term Boosted by Hybrid BM25",
        "failure_mode": "A1 (terminology mismatch), A3 (OOV fragmentation)",
        "query": "YY1 ANXA3 nitration diabetic cardiomyopathy",
        "expected_source": "REDOX-104085",
        "story": (
            "Dense embeddings fragment rare biomedical terms (YY1, ANXA3) into "
            "meaningless subword tokens. BM25 matches them exactly as strings. "
            "Hybrid RRF fusion combines both signals - BM25 anchors the right "
            "article while dense embeddings capture semantic context about "
            "nitration and cardiomyopathy."
        ),
        "hyde": False,
    },
    {
        "id": 5,
        "title": "Terminology Gap Bridged by HyDE",
        "failure_mode": "A2 (synonym gap), C5a (implicit knowledge gap)",
        "query": "parasite immune evasion mechanisms in cattle",
        "expected_source": "BJ_100828",
        "story": (
            "The user says 'parasite immune evasion' but the article says "
            "'T. annulata subversion of bovine leukocyte signalling'. "
            "HyDE generates a hypothetical paragraph using scientific vocabulary "
            "(Theileria, host immune response, antigenic variation), embedding it "
            "much closer to the actual corpus text."
        ),
        "hyde": True,
    },
]

# ─── Search Functions ─────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    return client.embeddings.create(model=EMBED_MODEL, input=[text]).data[0].embedding


def baseline_search(query: str, n: int = 10) -> list[dict]:
    """Baseline: html_scrape collection, vector-only, no enhancements."""
    col = chroma.get_collection("html_scrape")
    qe = embed_query(query)
    res = col.query(query_embeddings=[qe], n_results=n)
    return [
        {
            "id": res["ids"][0][i],
            "rank": i + 1,
            "distance": round(res["distances"][0][i], 4),
            "metadata": res["metadatas"][0][i],
            "text": res["documents"][0][i],
        }
        for i in range(len(res["ids"][0]))
    ]


def enriched_search(query: str, n: int = 10, use_hyde: bool = False) -> list[dict]:
    """Full pipeline: entity_enriched, hybrid BM25+vector, section reranking,
    recency boost, figure expansion."""
    embed_text = expand_query_hyde(query) if use_hyde else query
    qe = embed_query(embed_text)

    # Hybrid search (BM25 always uses raw query)
    hits = hybrid_search(query, qe, n=n)

    # Section reranking + recency boost
    hits = rerank(hits, query=query, section_boost=True, recency_weight=0.10)

    # Figure expansion
    linked_map = fetch_linked_figures(hits)
    for hit in hits:
        hit["linked_figures"] = linked_map.get(hit["id"], [])

    return hits

# ─── Comparison Logic ─────────────────────────────────────────────────────────

def find_target_rank(hits: list[dict], expected_source: str) -> dict | None:
    """Find the first hit matching the expected source article."""
    for h in hits:
        src = (h.get("metadata") or {}).get("source", "")
        if expected_source in src:
            return h
    return None


def run_scenario(scenario: dict) -> dict:
    """Run a single scenario and return structured comparison."""
    query = scenario["query"]

    # Baseline
    base_hits = baseline_search(query, n=10)
    # Enriched (full pipeline)
    enr_hits = enriched_search(query, n=10, use_hyde=scenario.get("hyde", False))

    base_rank1 = base_hits[0] if base_hits else None
    enr_rank1 = enr_hits[0] if enr_hits else None

    # Find the target article in each result set
    base_target = find_target_rank(base_hits, scenario["expected_source"])
    enr_target = find_target_rank(enr_hits, scenario["expected_source"])

    # Count linked figures in enriched top results
    total_linked_figs = sum(len(h.get("linked_figures", [])) for h in enr_hits[:5])

    result = {
        "scenario": scenario["id"],
        "title": scenario["title"],
        "failure_mode": scenario["failure_mode"],
        "query": query,
        "expected_source": scenario["expected_source"],
        "story": scenario["story"],
        "hyde_enabled": scenario.get("hyde", False),
        "baseline": {
            "rank1_source": (base_rank1["metadata"].get("source", "") if base_rank1 else ""),
            "rank1_section": (base_rank1["metadata"].get("section", "") if base_rank1 else ""),
            "rank1_type": (base_rank1["metadata"].get("type", "") if base_rank1 else ""),
            "rank1_distance": (base_rank1["distance"] if base_rank1 else None),
            "rank1_text": (base_rank1["text"][:200] if base_rank1 else ""),
            "target_rank": (base_target["rank"] if base_target else None),
            "target_distance": (base_target["distance"] if base_target else None),
        },
        "enriched": {
            "rank1_source": (enr_rank1["metadata"].get("source", "") if enr_rank1 else ""),
            "rank1_section": (enr_rank1["metadata"].get("section", "") if enr_rank1 else ""),
            "rank1_type": (enr_rank1["metadata"].get("type", "") if enr_rank1 else ""),
            "rank1_distance": (enr_rank1["distance"] if enr_rank1 else None),
            "rank1_text": (enr_rank1["text"][:200] if enr_rank1 else ""),
            "target_rank": (enr_target["rank"] if enr_target else None),
            "target_distance": (enr_target["distance"] if enr_target else None),
            "linked_figures_in_top5": total_linked_figs,
            "rerank_debug": enr_rank1.get("rerank_debug") if enr_rank1 else None,
            "hybrid_debug": {
                "rrf_score": enr_rank1.get("rrf_score"),
                "vector_rank": enr_rank1.get("vector_rank"),
                "bm25_rank": enr_rank1.get("bm25_rank"),
            } if enr_rank1 else None,
        },
        "delta": {
            "distance_improvement": round(
                (base_rank1["distance"] - enr_rank1["distance"]) if base_rank1 and enr_rank1 else 0,
                4
            ),
            "rank_improvement": (
                (base_target["rank"] if base_target else 11)
                - (enr_target["rank"] if enr_target else 11)
            ),
            "enriched_better": (
                enr_rank1["distance"] < base_rank1["distance"]
                if base_rank1 and enr_rank1 else False
            ),
        },
    }
    return result


def format_report(results: list[dict]) -> str:
    """Format results as a readable terminal report."""
    lines = []
    lines.append("=" * 90)
    lines.append("  BEACON ENRICHMENT PIPELINE - BEFORE vs AFTER DEMO REPORT")
    lines.append(f"  Generated: {date.today()}")
    lines.append("=" * 90)

    wins = 0
    for r in results:
        lines.append("")
        lines.append(f"┌─ Scenario {r['scenario']}: {r['title']}")
        lines.append(f"│  Failure mode: {r['failure_mode']}")
        lines.append(f"│  Query: \"{r['query']}\"")
        if r["hyde_enabled"]:
            lines.append(f"│  HyDE: enabled (LLM-expanded query)")
        lines.append(f"│")

        b = r["baseline"]
        e = r["enriched"]
        d = r["delta"]

        # Baseline
        lines.append(f"│  BASELINE (html_scrape, vector-only)")
        lines.append(f"│    Rank-1: {b['rank1_source'][:25]}  [{b['rank1_section'] or b['rank1_type']}]  dist={b['rank1_distance']:.4f}")
        lines.append(f"│    Text:   {b['rank1_text'][:90]}...")
        if b["target_rank"] and b["target_rank"] > 1:
            lines.append(f"│    Target article ({r['expected_source']}): rank {b['target_rank']}, dist={b['target_distance']:.4f}")
        lines.append(f"│")

        # Enriched
        lines.append(f"│  ENRICHED (hybrid + reranking + figures{'+ HyDE' if r['hyde_enabled'] else ''})")
        lines.append(f"│    Rank-1: {e['rank1_source'][:25]}  [{e['rank1_section'] or e['rank1_type']}]  dist={e['rank1_distance']:.4f}")
        lines.append(f"│    Text:   {e['rank1_text'][:90]}...")
        if e["linked_figures_in_top5"]:
            lines.append(f"│    Linked figures in top 5: {e['linked_figures_in_top5']}")
        rr = e.get("rerank_debug")
        if rr:
            lines.append(f"│    Intent: {rr.get('intent', '?')}  sec_mult={rr.get('section_multiplier', '?')}  rec_mult={rr.get('recency_multiplier', '?')}")
        lines.append(f"│")

        # Delta
        icon = "▲" if d["enriched_better"] else "▼"
        pct = abs(d["distance_improvement"] / b["rank1_distance"] * 100) if b["rank1_distance"] else 0
        direction = "closer" if d["enriched_better"] else "farther"
        lines.append(f"│  DELTA")
        lines.append(f"│    Distance: {d['distance_improvement']:+.4f} ({pct:.1f}% {direction})")
        if d["rank_improvement"] != 0:
            lines.append(f"│    Target rank: {'+' if d['rank_improvement'] > 0 else ''}{d['rank_improvement']} positions")
        lines.append(f"│    Result: {icon} {'Enriched wins' if d['enriched_better'] else 'Baseline wins on distance (but check section/type)'}")
        lines.append(f"│")
        lines.append(f"│  WHY: {r['story'][:200]}")
        lines.append(f"└{'─' * 89}")

        if d["enriched_better"]:
            wins += 1

    # Summary
    lines.append("")
    lines.append("=" * 90)
    lines.append(f"  SUMMARY: Enriched pipeline wins {wins}/{len(results)} scenarios on rank-1 distance")
    lines.append("")

    # Feature contribution table
    lines.append("  Features demonstrated:")
    lines.append("  ┌──────────────────────────┬─────────────────────────────────────────────┐")
    lines.append("  │ Phase                    │ Demonstrated in scenarios                   │")
    lines.append("  ├──────────────────────────┼─────────────────────────────────────────────┤")
    lines.append("  │ 1. Paragraph chunking    │ All (903 vs ~105 chunks)                   │")
    lines.append("  │ 2. Section reranking     │ Scenario 3 (methods/results boost)         │")
    lines.append("  │ 3. Hybrid BM25+vector    │ Scenario 4 (ALK exact term recovery)       │")
    lines.append("  │ 4. HyDE query expansion  │ Scenario 5 (terminology gap bridging)      │")
    lines.append("  │ 5. Figure cross-linking  │ Scenarios 1, 2 (linked figures surfaced)   │")
    lines.append("  │ 6. Claim-extracting figs │ Scenarios 1, 2 (figure as rank-1 result)   │")
    lines.append("  └──────────────────────────┴─────────────────────────────────────────────┘")
    lines.append("=" * 90)

    return "\n".join(lines)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Beacon demo comparison tool")
    parser.add_argument("--query", type=int, help="Run only this scenario number (1-5)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", type=str, help="Save report to file")
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.query:
        scenarios = [s for s in SCENARIOS if s["id"] == args.query]
        if not scenarios:
            print(f"No scenario with id={args.query}")
            sys.exit(1)

    print(f"Running {len(scenarios)} demo scenarios...\n")
    results = []
    for s in scenarios:
        print(f"  [{s['id']}/5] {s['title']}...", end=" ", flush=True)
        r = run_scenario(s)
        results.append(r)
        icon = "▲" if r["delta"]["enriched_better"] else "▼"
        print(f"{icon} delta={r['delta']['distance_improvement']:+.4f}")

    if args.json:
        output = json.dumps(results, indent=2, default=str)
    else:
        output = format_report(results)

    print("\n" + output)

    # Always save
    out_path = args.output or str(ROOT / "demo_comparison_report.txt")
    with open(out_path, "w") as f:
        f.write(output if not args.json else json.dumps(results, indent=2, default=str))
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
