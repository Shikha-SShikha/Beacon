"""
Phase 4 - HyDE (Hypothetical Document Embeddings) query expansion.

Instead of embedding the raw query, ask gpt-4o-mini to generate a
hypothetical answer paragraph, then embed *that*. The hypothetical
answer uses corpus-like vocabulary, bridging the terminology gap
between how users ask questions and how scientific articles are written.

Example:
  Query: "parasite immune evasion"
  HyDE: "This results section describes how T. annulata modulates host
         immune responses through subversion of bovine leukocyte signalling..."
  → embedding is now much closer to actual corpus chunks

No pipeline or DB changes. Pure query-time transformation.
"""

from .clients import get_openai

HYDE_SYSTEM_PROMPT = (
    "You are a scientific article retrieval assistant. Given a user's search query, "
    "write a single paragraph (100-150 words) that could plausibly appear in a "
    "scientific article answering that query. Use technical vocabulary, specific "
    "terminology, and the style of a peer-reviewed journal article. "
    "Do NOT answer the question - write text that would appear in a relevant article. "
    "Do NOT include citations, figure references, or hedging language."
)

HYDE_MODEL = "gpt-4o-mini"


def generate_hypothetical_document(query: str) -> str:
    """Generate a hypothetical document passage for the given query."""
    client = get_openai()
    response = client.chat.completions.create(
        model=HYDE_MODEL,
        messages=[
            {"role": "system", "content": HYDE_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        max_tokens=250,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def expand_query_hyde(query: str) -> str:
    """Return a HyDE-expanded text: hypothetical document + original query.

    Appending the original query preserves exact terms (important for
    biomedical abbreviations like ALK, PAI-1) while the hypothetical
    paragraph adds synonym-rich context.
    """
    hypothetical = generate_hypothetical_document(query)
    return f"{hypothetical}\n\n{query}"
