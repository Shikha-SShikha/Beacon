# Post-Ingestion Troubleshooting & Fixes

This document tracks the technical challenges encountered after ingesting the new article batch and the corresponding fixes applied to the Beacon pipeline.

## 1. ZeroDivisionError (BM25 Index)
**Problem:** The `rank-bm25` library crashes if passed an empty list of documents because it attempts to calculate `avgdl = total_length / document_count`. This occurred when the `entity_enriched` collection was empty or when namespace issues caused 0 chunks to be extracted.

**File:** `api/services/bm25_index.py`

### 🔴 BEFORE (Failing)
```python
class BM25Index:
    def __init__(self, doc_ids, tokenized_docs, metadatas, documents):
        self.doc_ids = doc_ids
        self.metadatas = metadatas
        self.documents = documents
        # This line crashes if tokenized_docs is empty []
        self.bm25 = BM25Okapi(tokenized_docs)

def _build_index() -> BM25Index:
    chroma = get_chroma()
    collection = chroma.get_collection("entity_enriched")
    all_docs = collection.get(include=["documents", "metadatas"])

    doc_ids = all_docs["ids"]
    documents = all_docs["documents"]
    metadatas = all_docs["metadatas"]

    tokenized = [tokenize(doc) for doc in documents]
    # No check here: if doc_ids is empty, it passes [] to BM25Index
    return BM25Index(doc_ids, tokenized, metadatas, documents)
```

### 🟢 AFTER (Fixed)
```python
class BM25Index:
    def __init__(self, doc_ids, tokenized_docs, metadatas, documents):
        self.doc_ids = doc_ids
        self.metadatas = metadatas
        self.documents = documents
        # Check if we have documents before initializing
        self.bm25 = BM25Okapi(tokenized_docs) if tokenized_docs else None

    def search(self, query: str, n: int = 20):
        # Return empty list if index doesn't exist
        if not self.bm25:
            return []
        # ... rest of search logic ...

def _build_index() -> BM25Index:
    chroma = get_chroma()
    # ... collection logic ...
    all_docs = collection.get(include=["documents", "metadatas"])
    doc_ids = all_docs["ids"]

    print(f"BM25 build: Found {len(doc_ids)} documents in collection.")

    if not doc_ids:
        # Prevent passing empty lists to the class
        return BM25Index([], [], [], [])

    tokenized = [tokenize(doc) for doc in documents]
    return BM25Index(doc_ids, tokenized, metadatas, documents)
```

---

## 2. ModuleNotFoundError (Uvicorn Command)
**Problem:** The startup command used `app.main:app`, but the project directory is named `api/`.

### 🔴 BEFORE (Failing)
```bash
python3 -m uvicorn app.main:app --reload
# Result: ModuleNotFoundError: No module named 'app'
```

### 🟢 AFTER (Fixed)
```bash
python3 -m uvicorn api.main:app --reload
# Result: Successfully finds the api/ directory and starts the server.
```

---

## 3. Missing Path Visibility (Clients Utility)
**Problem:** Hard to verify if ChromaDB is pointing to the correct persistent directory during debugging.

**File:** `api/services/clients.py`

### 🔴 BEFORE
```python
def get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _chroma_client
```

### 🟢 AFTER
```python
def get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        # Added logging to confirm the absolute path during startup
        print(f"ChromaDB: Initializing PersistentClient at {CHROMA_PATH}")
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _chroma_client
```

---

## 4. Source Crowding (Search Diversification)
**Problem:** A single highly relevant article with many small chunks would "crowd out" other relevant papers in the Top-K results, leading to RAG answers synthesized from only one source.

**File:** `api/services/search_service.py`

### 🟢 SOLUTION (Diversification Logic)
```python
# Apply a soft penalty based on how many chunks from the same source are already in the list
source_counts = {}
for hit in fused:
    source = hit["metadata"].get("source", "unknown")
    count = source_counts.get(source, 0)
    # Penalty: Multiply score by 0.8 for each existing chunk from this source
    # This pushes subsequent chunks from the same paper further down
    hit["div_score"] = hit["rrf_score"] * (0.8 ** count)
    source_counts[source] = count + 1

fused.sort(key=lambda h: h["div_score"], reverse=True)
```

---

## 5. XML Namespace Ingestion Error
**Problem:** New XML articles used default namespaces (`xmlns`), causing `lxml`'s standard `.find()` to miss tags like `item-info` and `body`, resulting in missing DOIs and 0 extracted text chunks.

**File:** `pipeline.py`

### 🟢 SOLUTION
Implemented a namespace-agnostic helper `find_local()` that matches tags based on their local name, ignoring the namespace prefix/URL. This ensures compatibility with both standard and namespaced Elsevier XML structures.
