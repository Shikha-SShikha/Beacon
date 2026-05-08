"""
Phase 3 - BM25 sparse index over ChromaDB documents.

Builds an in-memory BM25Okapi index from the entity_enriched collection.
The index is a singleton - built once on first search, then reused.

BM25 handles exact biomedical terms (ALK, PAI-1, METTL3) that dense
embeddings struggle with due to OOV token fragmentation.
"""

import re
import json
from rank_bm25 import BM25Okapi
from .clients import get_chroma

_bm25_index: "BM25Index | None" = None


class BM25Index:
    """Wraps rank_bm25 with document ID tracking."""

    def __init__(self, doc_ids: list[str], tokenized_docs: list[list[str]],
                 metadatas: list[dict], documents: list[str]):
        self.doc_ids = doc_ids
        self.metadatas = metadatas
        self.documents = documents
        self.bm25 = BM25Okapi(tokenized_docs) if tokenized_docs else None

    def search(self, query: str, n: int = 20) -> list[dict]:
        if not self.bm25:
            return []
        tokens = tokenize(query)
        scores = self.bm25.get_scores(tokens)

        # Get top-n indices sorted by score descending
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]

        results = []
        for rank, idx in enumerate(ranked_indices, 1):
            if scores[idx] <= 0:
                break  # no point returning zero-score results
            results.append({
                "id": self.doc_ids[idx],
                "bm25_score": float(scores[idx]),
                "bm25_rank": rank,
                "metadata": self.metadatas[idx],
                "text": self.documents[idx],
            })
        return results


def tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer. Lowercased, keeps hyphens
    and slashes within tokens (important for biomedical terms like PAI-1)."""
    # Split on whitespace, strip outer punctuation but keep internal hyphens/slashes
    tokens = re.findall(r'[a-zA-Z0-9][\w\-/]*[a-zA-Z0-9]|[a-zA-Z0-9]', text.lower())
    return tokens


def get_bm25_index() -> BM25Index:
    """Return the singleton BM25 index, building it on first call."""
    global _bm25_index
    if _bm25_index is not None:
        return _bm25_index

    _bm25_index = _build_index()
    return _bm25_index


def rebuild_bm25_index() -> BM25Index:
    """Force rebuild of the BM25 index (e.g. after collection update)."""
    global _bm25_index
    _bm25_index = _build_index()
    return _bm25_index


def _build_index() -> BM25Index:
    """Load all documents from ChromaDB and build a BM25 index."""
    chroma = get_chroma()
    try:
        collection = chroma.get_collection("entity_enriched")
    except Exception as e:
        print(f"Error getting collection 'entity_enriched': {e}")
        # Return an empty index instead of crashing, or re-raise with better info
        return BM25Index([], [], [], [])

    # ChromaDB .get() returns all documents
    all_docs = collection.get(include=["documents", "metadatas"])

    doc_ids = all_docs["ids"]
    documents = all_docs["documents"]
    metadatas = all_docs["metadatas"]

    print(f"BM25 build: Found {len(doc_ids)} documents in collection.")

    if not doc_ids:
        # Avoid ZeroDivisionError in rank_bm25
        return BM25Index([], [], [], [])

    tokenized = [tokenize(doc) for doc in documents]

    return BM25Index(doc_ids, tokenized, metadatas, documents)
