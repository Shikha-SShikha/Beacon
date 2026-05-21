import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Spinner from "../components/ui/Spinner";
import ErrorBanner from "../components/ui/ErrorBanner";

interface Article {
  article_id: string;
  journal_code: string;
  domain: string;
  doi: string;
  chunks: number;
  entities: number;
}

interface Journal {
  journal_code: string;
  journal_name: string;
  color: string;
  article_count: number;
  total_chunks: number;
  total_entities: number;
  articles: Article[];
}

interface Domain {
  domain: string;
  journal_count: number;
  article_count: number;
  total_chunks: number;
  total_entities: number;
  journals: Journal[];
}

interface CollectionsSummary {
  institution_id: string;
  total_domains: number;
  total_journals: number;
  total_articles: number;
  total_chunks: number;
  total_entities: number;
  collections: Domain[];
}

export default function CollectionsPage({
  institutionId,
}: {
  institutionId: string;
  onSwitch?: () => void;
}) {
  const navigate = useNavigate();
  const [collections, setCollections] = useState<CollectionsSummary | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(
    new Set()
  );
  const [expandedJournals, setExpandedJournals] = useState<Set<string>>(
    new Set()
  );

  useEffect(() => {
    const fetchCollections = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(
          `/collections/${institutionId}`
        );
        if (!response.ok) {
          throw new Error("Failed to load collections");
        }
        const data: CollectionsSummary = await response.json();
        setCollections(data);
        // Expand first domain by default
        if (data.collections.length > 0) {
          setExpandedDomains(new Set([data.collections[0].domain]));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchCollections();
  }, [institutionId]);

  const toggleDomain = (domain: string) => {
    const newExpanded = new Set(expandedDomains);
    if (newExpanded.has(domain)) {
      newExpanded.delete(domain);
    } else {
      newExpanded.add(domain);
    }
    setExpandedDomains(newExpanded);
  };

  const toggleJournal = (journalCode: string) => {
    const newExpanded = new Set(expandedJournals);
    if (newExpanded.has(journalCode)) {
      newExpanded.delete(journalCode);
    } else {
      newExpanded.add(journalCode);
    }
    setExpandedJournals(newExpanded);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error || !collections) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <ErrorBanner message={error || "Failed to load collections"} onDismiss={() => setError(null)} />
        <button
          onClick={() => navigate("/search")}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Back to Search
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Article Collections
              </h1>
              <p className="mt-2 text-gray-600">
                Browse articles organized by research domain
              </p>
            </div>
            <button
              onClick={() => navigate("/search")}
              className="px-4 py-2 text-blue-600 hover:text-blue-700 font-medium"
            >
              ← Back to Search
            </button>
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-blue-600">
              {collections.total_domains}
            </div>
            <div className="text-sm text-gray-600 mt-2">Research Domains</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-purple-600">
              {collections.total_journals}
            </div>
            <div className="text-sm text-gray-600 mt-2">Journals</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-green-600">
              {collections.total_articles}
            </div>
            <div className="text-sm text-gray-600 mt-2">Articles</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-orange-600">
              {collections.total_chunks}
            </div>
            <div className="text-sm text-gray-600 mt-2">Chunks</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-red-600">
              {collections.total_entities}
            </div>
            <div className="text-sm text-gray-600 mt-2">Entities</div>
          </div>
        </div>

        {/* Collections */}
        <div className="space-y-4">
          {collections.collections.map((domain) => (
            <div key={domain.domain} className="bg-white rounded-lg shadow">
              {/* Domain Header */}
              <button
                onClick={() => toggleDomain(domain.domain)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <span
                    className={`transform transition-transform ${
                      expandedDomains.has(domain.domain) ? "rotate-90" : ""
                    }`}
                  >
                    ▶
                  </span>
                  <div className="text-left">
                    <h2 className="text-xl font-semibold text-gray-900">
                      {domain.domain}
                    </h2>
                    <p className="text-sm text-gray-600 mt-1">
                      {domain.journal_count} journals · {domain.article_count}{" "}
                      articles · {domain.total_chunks} chunks ·{" "}
                      {domain.total_entities} entities
                    </p>
                  </div>
                </div>
              </button>

              {/* Domain Content */}
              {expandedDomains.has(domain.domain) && (
                <div className="border-t border-gray-200 px-6 py-4 space-y-4">
                  {domain.journals.map((journal) => (
                    <div key={journal.journal_code}>
                      {/* Journal Header */}
                      <button
                        onClick={() => toggleJournal(journal.journal_code)}
                        className="w-full flex items-center justify-between hover:bg-gray-50 py-2 px-3 rounded transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`transform transition-transform ${
                              expandedJournals.has(journal.journal_code)
                                ? "rotate-90"
                                : ""
                            }`}
                          >
                            ▶
                          </span>
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: journal.color }}
                          />
                          <div className="text-left">
                            <h3 className="font-medium text-gray-900">
                              {journal.journal_name}
                            </h3>
                            <p className="text-xs text-gray-600">
                              {journal.article_count} articles ·{" "}
                              {journal.total_chunks} chunks ·{" "}
                              {journal.total_entities} entities
                            </p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-1 rounded">
                          {journal.journal_code}
                        </span>
                      </button>

                      {/* Articles List */}
                      {expandedJournals.has(journal.journal_code) && (
                        <div className="pl-12 py-2 space-y-2">
                          {journal.articles.map((article) => (
                            <div
                              key={article.article_id}
                              className="p-3 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer transition-colors"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <p className="font-mono text-sm font-semibold text-gray-900">
                                    {article.article_id}
                                  </p>
                                  {article.doi && (
                                    <p className="text-xs text-gray-600 mt-1 break-words">
                                      DOI: {article.doi}
                                    </p>
                                  )}
                                  <p className="text-xs text-gray-500 mt-1">
                                    {article.chunks} chunks · {article.entities}{" "}
                                    entities
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
