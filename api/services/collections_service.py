"""
collections_service.py — Collections management

Groups articles by research domain and journal for browsing.
Integrates with chunk metadata to provide article statistics.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Optional

from .attribution_service import DOMAIN_MAPPING, get_domain_for_journal


CHUNKS_DIR = Path(__file__).parent.parent.parent / "chunks"


class ArticleMetadata:
    """Metadata for a single article."""

    def __init__(
        self,
        article_id: str,
        journal_code: str,
        domain: str,
        doi: str = "",
        chunks: int = 0,
        entities: int = 0,
    ):
        self.article_id = article_id
        self.journal_code = journal_code
        self.domain = domain
        self.doi = doi
        self.chunks = chunks
        self.entities = entities

    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "journal_code": self.journal_code,
            "domain": self.domain,
            "doi": self.doi,
            "chunks": self.chunks,
            "entities": self.entities,
        }


class JournalCollection:
    """A collection of articles from a single journal."""

    def __init__(self, journal_code: str, journal_name: str, color: str):
        self.journal_code = journal_code
        self.journal_name = journal_name
        self.color = color
        self.articles: list[ArticleMetadata] = []

    def add_article(self, article: ArticleMetadata) -> None:
        self.articles.append(article)

    @property
    def article_count(self) -> int:
        return len(self.articles)

    @property
    def total_chunks(self) -> int:
        return sum(a.chunks for a in self.articles)

    @property
    def total_entities(self) -> int:
        return sum(a.entities for a in self.articles)

    def to_dict(self) -> dict:
        return {
            "journal_code": self.journal_code,
            "journal_name": self.journal_name,
            "color": self.color,
            "article_count": self.article_count,
            "total_chunks": self.total_chunks,
            "total_entities": self.total_entities,
            "articles": [a.to_dict() for a in self.articles],
        }


class DomainCollection:
    """A collection of articles grouped by research domain."""

    def __init__(self, domain: str):
        self.domain = domain
        self.journals: dict[str, JournalCollection] = {}

    def add_article(
        self,
        article: ArticleMetadata,
        journal_name: str,
        journal_color: str,
    ) -> None:
        if article.journal_code not in self.journals:
            self.journals[article.journal_code] = JournalCollection(
                article.journal_code, journal_name, journal_color
            )
        self.journals[article.journal_code].add_article(article)

    @property
    def journal_count(self) -> int:
        return len(self.journals)

    @property
    def article_count(self) -> int:
        return sum(j.article_count for j in self.journals.values())

    @property
    def total_chunks(self) -> int:
        return sum(j.total_chunks for j in self.journals.values())

    @property
    def total_entities(self) -> int:
        return sum(j.total_entities for j in self.journals.values())

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "journal_count": self.journal_count,
            "article_count": self.article_count,
            "total_chunks": self.total_chunks,
            "total_entities": self.total_entities,
            "journals": [j.to_dict() for j in sorted(
                self.journals.values(),
                key=lambda x: x.journal_name,
            )],
        }


def _load_article_metadata(article_id: str) -> Optional[ArticleMetadata]:
    """Load metadata for a single article from its chunk file."""
    # Try common naming patterns
    candidates = [
        f"{article_id}_chunks.json",
        f"{article_id}.json",
    ]

    for filename in candidates:
        chunk_file = CHUNKS_DIR / filename
        if not chunk_file.exists():
            continue

        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)

            source_file = chunk_data.get("source_file", "")
            doi = chunk_data.get("article_doi", "")
            chunks = chunk_data.get("total_chunks", 0)
            entities = chunk_data.get("total_entities", 0)

            # Extract journal code from article ID
            journal_code = article_id.split("_")[0].split("-")[0]
            domain = get_domain_for_journal(journal_code)

            return ArticleMetadata(
                article_id=article_id,
                journal_code=journal_code,
                domain=domain,
                doi=doi,
                chunks=chunks,
                entities=entities,
            )
        except (json.JSONDecodeError, IOError):
            continue

    return None


def get_all_articles() -> dict[str, ArticleMetadata]:
    """Load all available articles from chunk metadata."""
    articles = {}

    if not CHUNKS_DIR.exists():
        return articles

    for chunk_file in CHUNKS_DIR.glob("*_chunks.json"):
        article_id = chunk_file.stem.replace("_chunks", "")

        metadata = _load_article_metadata(article_id)
        if metadata:
            articles[article_id] = metadata

    return articles


def get_collections(
    institution_id: str,
    include_open_access_only: bool = False,
) -> dict[str, DomainCollection]:
    """
    Get articles grouped by domain and journal for an institution.

    Args:
        institution_id: e.g., "uni_edinburgh"
        include_open_access_only: if True, only include open access articles

    Returns:
        dict[domain_name, DomainCollection]
    """
    from governance.license_service import load_config, check_license

    config = load_config()

    if institution_id not in config["institutions"]:
        return {}

    collections: dict[str, DomainCollection] = {}
    articles = get_all_articles()

    for article_id, metadata in articles.items():
        # Check license for this institution
        fake_metadata = {"source": article_id}
        decision = check_license(institution_id, fake_metadata)

        if decision["decision"] == "NO_ACCESS":
            continue

        if (
            include_open_access_only
            and decision["decision"] != "OPEN_ACCESS"
        ):
            continue

        # Add to appropriate domain collection
        domain = metadata.domain
        if domain not in collections:
            collections[domain] = DomainCollection(domain)

        # Get journal info
        journal_code = metadata.journal_code
        journal_info = config["journals"].get(journal_code, {})
        journal_name = journal_info.get("name", journal_code)
        journal_color = journal_info.get("color", "#999999")

        collections[domain].add_article(
            metadata, journal_name, journal_color
        )

    return collections


def get_collections_summary(
    institution_id: str,
) -> dict:
    """
    Get a summary of all collections for an institution.

    Returns:
        {
            "institution_id": "uni_edinburgh",
            "total_domains": 3,
            "total_journals": 5,
            "total_articles": 18,
            "collections": [
                {
                    "domain": "Biomedical",
                    "journal_count": 2,
                    "article_count": 11,
                    "total_chunks": 381,
                    "total_entities": 1246,
                    ...
                }
            ]
        }
    """
    collections = get_collections(institution_id)

    sorted_collections = sorted(
        collections.values(),
        key=lambda x: x.domain,
    )

    return {
        "institution_id": institution_id,
        "total_domains": len(collections),
        "total_journals": sum(c.journal_count for c in collections.values()),
        "total_articles": sum(c.article_count for c in collections.values()),
        "total_chunks": sum(c.total_chunks for c in collections.values()),
        "total_entities": sum(c.total_entities for c in collections.values()),
        "collections": [c.to_dict() for c in sorted_collections],
    }
