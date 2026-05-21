import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { fetchInstitution, fetchJournals, postAsk, postBaselineAsk } from "../api/client";
import type { InstitutionSummary, JournalInfo, AskExchange, AskResponse } from "../types";
import Sidebar from "../components/layout/Sidebar";
import BeaconLogo from "../components/ui/BeaconLogo";
import AnswerView from "../components/results/AnswerView";
import SourcesPanel from "../components/results/SourcesPanel";
import BaselineDrawer from "../components/results/BaselineDrawer";
import Spinner from "../components/ui/Spinner";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";

const DEMO_TOPICS = [
  {
    topic: "Ferroptosis & Cancer",
    color: "text-slate-700 bg-white border-slate-200",
    dot: "bg-slate-400",
    queries: [
      { level: "Broad",    label: "How does ferroptosis regulate cancer cell death?" },
      { level: "Focused",  label: "What role does GPX4 play in ferroptosis resistance across gastric and colorectal cancers?" },
      { level: "Pinpoint", label: "How does ALOX15-mediated lipoxygenase activity sensitize tumor cells to ferroptosis induction?" },
    ],
  },
  {
    topic: "m6A RNA Modification",
    color: "text-slate-700 bg-white border-slate-200",
    dot: "bg-slate-400",
    queries: [
      { level: "Broad",    label: "What is the role of m6A modification in disease progression?" },
      { level: "Focused",  label: "How does METTL3-mediated m6A activate the NLRP3 inflammasome in macrophages?" },
      { level: "Pinpoint", label: "What protein residue enables m6A recognition in Plasmodium reader proteins?" },
    ],
  },
];

const LEVEL_STYLE: Record<string, string> = {
  Broad:    "bg-slate-100 text-slate-500",
  Focused:  "bg-slate-100 text-slate-600",
  Pinpoint: "bg-slate-800 text-white",
};

interface Props {
  institutionId: string;
  onSwitch: () => void;
}

export default function SearchPage({ institutionId, onSwitch }: Props) {
  const navigate = useNavigate();
  const [institution, setInstitution] = useState<InstitutionSummary | null>(null);
  const [journals, setJournals] = useState<Record<string, JournalInfo>>({});
  const [history, setHistory] = useState<AskExchange[]>([]);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sources panel state
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [activeExchange, setActiveExchange] = useState<number>(0);
  const [highlightCitation, setHighlightCitation] = useState<number | null>(null);


  // Comparison drawer state (Standard RAG only)
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [ragLoading, setRagLoading] = useState(false);
  const [ragResponse, setRagResponse] = useState<AskResponse | null>(null);
  const [comparisonQuery, setComparisonQuery] = useState<string>("");

  const inputRef = useRef<HTMLInputElement>(null);
  const resultsTopRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchInstitution(institutionId).then(setInstitution).catch(() => {});
    fetchJournals().then(setJournals).catch(() => {});
  }, [institutionId]);

  async function handleSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setError(null);
    setLoading(true);
    setSourcesOpen(false);
    try {
      const response = await postAsk(trimmed, institutionId, topK);
      setHistory((prev) => [{ id: Date.now(), query: trimmed, response }, ...prev]);
      setActiveExchange(0);
      setQuery("");
      setTimeout(() => resultsTopRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e: any) {
      setError(e.message ?? "Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleExample(ex: string) {
    setQuery(ex);
    handleSearch(ex);
  }

  function handleCitationClick(exchangeIdx: number, citationId: number) {
    setActiveExchange(exchangeIdx);
    setHighlightCitation(citationId);
    setSourcesOpen(true);
    setTimeout(() => setHighlightCitation(null), 2000);
  }


  const handleBaselineOpen = useCallback(async (q: string) => {
    setBaselineOpen(true);
    if (q === comparisonQuery && ragResponse !== null) return;
    setComparisonQuery(q);
    setRagLoading(true);
    setRagResponse(null);
    postBaselineAsk(q, institutionId, 8)
      .then(setRagResponse)
      .catch(() => setRagResponse(null))
      .finally(() => setRagLoading(false));
  }, [comparisonQuery, ragResponse, institutionId]);

  const collectionLabel = institution?.licensed_journals
    .map((j) => j.code)
    .join(", ") || "your collection";

  const currentSources = history[activeExchange]?.response.sources ?? [];

  return (
    <div className="flex min-h-screen bg-slate-50">

      {/* Left sidebar */}
      {institution && (
        <Sidebar
          institution={institution}
          topK={topK}
          onTopKChange={setTopK}
          onSwitch={onSwitch}
          onCollections={() => navigate("/collections")}
          onAttribution={() => navigate("/attribution")}
        />
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <div className="px-10 pt-8 pb-5 border-b border-slate-200/60 bg-white">
          <div className="flex items-center gap-2.5 mb-1">
            <BeaconLogo size="sm" />
            <span className="text-slate-200">/</span>
            <span className="text-[13px] font-medium text-slate-400">Ask</span>
          </div>
          <p className="text-[13px] text-slate-400">
            AI-powered answers from your licensed collection: <span className="font-medium text-slate-500">{collectionLabel}</span>
          </p>
        </div>

        {/* Search bar */}
        <div className="px-10 py-6 border-b border-slate-200/60 bg-white">
          {error && (
            <div className="mb-4">
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          <div className="flex gap-3">
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch(query)}
              placeholder="Ask a question across your collection..."
              className="flex-1 px-4 py-3 rounded-xl border border-slate-200 text-[15px] text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
            />
            <button
              onClick={() => handleSearch(query)}
              disabled={loading || !query.trim()}
              className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-[15px] font-semibold flex items-center gap-2 transition-all shadow-sm shadow-blue-600/20 min-w-[100px] justify-center"
            >
              {loading ? <Spinner className="w-4 h-4" /> : "Ask"}
            </button>
          </div>

          {/* Demo query arcs */}
          <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
            {DEMO_TOPICS.map((topic) => (
              <div key={topic.topic} className={`rounded-xl border p-3.5 ${topic.color}`}>
                <div className="flex items-center gap-1.5 mb-2.5">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${topic.dot}`} />
                  <p className="text-[11px] font-bold uppercase tracking-wider">{topic.topic}</p>
                </div>
                <div className="space-y-1.5">
                  {topic.queries.map((q) => (
                    <button
                      key={q.label}
                      onClick={() => handleExample(q.label)}
                      disabled={loading}
                      className="w-full text-left flex items-start gap-2 px-3 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/50 hover:border-slate-200 disabled:opacity-40 transition-all group"
                    >
                      <span className={`shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded mt-0.5 ${LEVEL_STYLE[q.level]}`}>
                        {q.level}
                      </span>
                      <span className="text-[12px] text-slate-700 group-hover:text-slate-900 leading-snug">
                        {q.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Content area — answer + sources panel side by side */}
        <div className="flex-1 flex overflow-hidden">

          {/* Answer area */}
          <div className="flex-1 overflow-y-auto px-10 py-8">
            <div ref={resultsTopRef} />

            {history.length === 0 && !loading && <EmptyState />}

            {loading && (
              <div className="flex items-center gap-3 py-16 justify-center text-slate-400">
                <Spinner className="w-5 h-5" />
                <span className="text-[15px]">Searching and synthesizing...</span>
              </div>
            )}

            <div className="space-y-12">
              {history.map((exchange, i) => (
                <div key={exchange.id}>
                  {/* Query */}
                  <div className="mb-6">
                    <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase mb-1.5">Question</p>
                    <p className="text-lg font-semibold text-slate-800">{exchange.query}</p>
                  </div>

                  {/* Enrichment summary badge */}
                  <div className="mb-4">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-500 text-[12px]">
                      <span>Enriched search:</span>
                      <span className="text-slate-400">Entities linked · Relations extracted · Section-aware retrieval</span>
                    </div>
                  </div>

                  {/* Answer */}
                  <div className="mb-5">
                    <AnswerView
                      response={exchange.response}
                      onCitationClick={(cid) => handleCitationClick(i, cid)}
                    />
                  </div>

                  {/* Sources summary bar */}
                  <div className="flex items-center gap-3 mt-5 flex-wrap">
                    <button
                      onClick={() => {
                        setActiveExchange(i);
                        setSourcesOpen(!sourcesOpen || activeExchange !== i);
                        setHighlightCitation(null);
                      }}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-slate-200 text-[13px] text-slate-500 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.332 0-3.332.477-4.5 1.253" />
                      </svg>
                      {exchange.response.sources.length} sources
                    </button>
                    {/* Inline source pills */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {exchange.response.sources.map((src) => (
                        <button
                          key={src.citation_id}
                          onClick={() => handleCitationClick(i, src.citation_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white border border-slate-200 text-slate-500 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition-colors"
                        >
                          <span className="font-bold">[{src.citation_id}]</span>
                          <span className="truncate max-w-[120px]">{src.journal_code || src.year || ""}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Standard RAG comparison trigger */}
                  <div className="mt-4">
                    <button
                      onClick={() => handleBaselineOpen(exchange.query)}
                      className="inline-flex items-center gap-2 text-[13px] text-slate-400 hover:text-blue-600 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                      Compare with standard RAG
                    </button>
                  </div>

                  {i < history.length - 1 && <hr className="mt-10 border-slate-200/60" />}
                </div>
              ))}
            </div>
          </div>

          {/* Sources side panel */}
          <SourcesPanel
            sources={currentSources}
            journals={journals}
            open={sourcesOpen}
            onClose={() => setSourcesOpen(false)}
            highlightId={highlightCitation}
          />
        </div>
      </main>

      {/* Comparison drawer — Standard RAG only */}
      <BaselineDrawer
        ragResponse={ragResponse}
        ragLoading={ragLoading}
        open={baselineOpen}
        onClose={() => setBaselineOpen(false)}
        beaconResponse={history[activeExchange]?.response ?? null}
      />
    </div>
  );
}
