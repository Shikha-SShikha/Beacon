import os
from pathlib import Path
from openai import OpenAI
import chromadb

_env = Path(__file__).parent.parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

CHROMA_PATH = Path(__file__).parent.parent.parent / "chroma_db"
EMBED_MODEL = "text-embedding-3-small"

_openai_client = None
_chroma_client = None


def get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


def get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        print(f"ChromaDB: Initializing PersistentClient at {CHROMA_PATH}")
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _chroma_client
