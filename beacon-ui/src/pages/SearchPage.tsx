import { useState, useEffect, useRef, useCallback } from "react";
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

const EXAMPLES = [
  "What is the statistical significance of m6A elevation in T. annulata infected macrophages?",
  "Which m6A writer and eraser genes are differentially regulated in Theileria infection?",
  "How were RNA samples prepared and m6A levels measured?",
  "PAI-1 role in leukemia cell proliferation",
  "YY1 expression changes in cardiac tissue",
];

interface Props {
  institutionId: string;
  onSwitch: () => void;
}

export default function SearchPage({ institutionId, onSwitch }: Props) {
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

  // Baseline drawer state
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [baselineLoading, setBaselineLoading] = useState(false);
  const [baselineResponse, setBaselineResponse] = useState<AskResponse | null>(null);
  const [baselineQuery, setBaselineQuery] = useState<string>("");

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
      setHistory((prev) => [{ query: trimmed, response }, ...prev]);
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
    if (q === baselineQuery && baselineResponse !== null) return;
    setBaselineLoading(true);
    setBaselineQuery(q);
    try {
      const res = await postBaselineAsk(q, institutionId, 8);
      setBaselineResponse(res);
    } catch {
      setBaselineResponse(null);
    } finally {
      setBaselineLoading(false);
    }
  }, [baselineQuery, baselineResponse, institutionId]);

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

          {/* Examples */}
          <div className="mt-4">
            <p className="text-[11px] text-slate-400 uppercase tracking-wider font-medium mb-2">Try an example</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => handleExample(ex)}
                  disabled={loading}
                  className="text-[13px] px-3.5 py-1.5 rounded-full border border-slate-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 disabled:opacity-40 transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
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
                <div key={i}>
                  {/* Query */}
                  <div className="mb-6">
                    <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase mb-1.5">Question</p>
                    <p className="text-lg font-semibold text-slate-800">{exchange.query}</p>
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

                  {/* Baseline comparison trigger */}
                  <div className="mt-4">
                    <button
                      onClick={() => handleBaselineOpen(exchange.query)}
                      className="inline-flex items-center gap-2 text-[13px] text-slate-400 hover:text-amber-600 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                      How would current AI search answer this?
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

      {/* Baseline comparison drawer */}
      <BaselineDrawer
        response={baselineResponse}
        loading={baselineLoading}
        open={baselineOpen}
        onClose={() => setBaselineOpen(false)}
      />
    </div>
  );
}
