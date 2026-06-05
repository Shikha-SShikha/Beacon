import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { fetchAttributionSummary, fetchAttributionFeed, simulateBlockedRequest } from "../api/client";
import type { AttributionSummary, FeedEvent } from "../types";
import BeaconLogo from "../components/ui/BeaconLogo";

interface Props {
  onSwitch: () => void;
}

const LICENSE_LABEL: Record<string, string> = {
  RAG_READ_RAG_SOURCE: "Full text · RAG read · source display",
  RAG:                 "Snippet · RAG only",
  SNIPPET_ONLY:        "Snippet only",
  ALLOWED:             "Allowed",
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function SectionPill({ label }: { label: string }) {
  const IMRAD = new Set(["Results", "Methods", "Discussion", "Introduction",
    "Conclusion", "Abstract", "Figure", "Table"]);
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border ${
      IMRAD.has(label)
        ? "bg-slate-100 text-slate-600 border-slate-200 uppercase tracking-wide"
        : "bg-white text-slate-500 border-slate-200 italic"
    }`}>
      {label}
    </span>
  );
}

// ── Served event card ──────────────────────────────────────────────────────

function ServedCard({ event }: { event: FeedEvent }) {
  const [showRaw, setShowRaw] = useState(false);

  const raw = JSON.stringify({
    event_id:    event.event_id,
    event_type:  "served",
    timestamp:   event.timestamp,
    query:       event.query,
    agent:       event.agent_label,
    sources: event.sources.map(s => ({
      article:           s.title,
      journal:           s.journal_code,
      publisher:         s.publisher_label,
      doi:               s.doi,
      sections_used:     s.sections_used,
      license:           s.license_decision,
      entities_enriched: s.entity_count,
    })),
  }, null, 2);

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold text-slate-500 bg-slate-100 border border-slate-200">
                <svg className="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Served
              </span>
              <span className="text-[11px] text-slate-400">{formatTime(event.timestamp)}</span>
            </div>
            <p className="text-[14px] font-semibold text-slate-800 leading-snug">{event.query}</p>
            <p className="text-[12px] text-slate-400 mt-1">{event.agent_label}</p>
          </div>
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="shrink-0 text-[11px] text-slate-400 hover:text-slate-600 transition-colors mt-0.5 whitespace-nowrap"
          >
            {showRaw ? "Hide raw ▲" : "View raw ▼"}
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {event.sources.map((src, i) => (
            <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-slate-700 line-clamp-1">{src.title}</p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-[11px] text-slate-400 font-medium">{src.journal_code}</span>
                    {src.doi && (
                      <span className="text-[11px] text-slate-400 font-mono truncate max-w-[200px]">· {src.doi}</span>
                    )}
                  </div>
                </div>
                <span className="shrink-0 text-[10px] font-medium text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded">
                  License verified ✓
                </span>
              </div>

              {src.sections_used.length > 0 && (
                <div className="mt-2.5">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-1.5">
                    Sections surfaced
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {src.sections_used.map((s, j) => <SectionPill key={j} label={s} />)}
                  </div>
                </div>
              )}

              <div className="mt-2 flex items-center gap-4">
                <span className="text-[11px] text-slate-400">
                  <span className="font-medium text-slate-500">Terms:</span>{" "}
                  {LICENSE_LABEL[src.license_decision] ?? src.license_decision}
                </span>
                {src.entity_count > 0 && (
                  <span className="text-[11px] text-slate-400">
                    <span className="font-medium text-slate-500">Entities:</span> {src.entity_count} linked
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {showRaw && (
        <div className="border-t border-slate-100 bg-slate-950 px-5 py-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Raw event · {event.event_id}
          </p>
          <pre className="text-[11px] text-slate-300 leading-relaxed overflow-x-auto font-mono">{raw}</pre>
        </div>
      )}
    </div>
  );
}

// ── Blocked event card ─────────────────────────────────────────────────────

function BlockedCard({ event }: { event: FeedEvent }) {
  const [showRaw, setShowRaw] = useState(false);

  const raw = JSON.stringify({
    event_id:          event.event_id,
    event_type:        "blocked",
    timestamp:         event.timestamp,
    query:             event.query,
    agent:             event.agent_label,
    attempted: event.attempted.map(a => ({
      journal:   a.journal_code,
      publisher: a.publisher_label,
      articles:  a.article_count,
    })),
    articles_attempted: event.articles_attempted,
    articles_served:    0,
    block_reason:       event.block_reason,
  }, null, 2);

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/40 overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold text-amber-700 bg-amber-100 border border-amber-200">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
                Access blocked
              </span>
              <span className="text-[11px] text-slate-400">{formatTime(event.timestamp)}</span>
            </div>
            <p className="text-[14px] font-semibold text-slate-800 leading-snug">{event.query}</p>
            <p className="text-[12px] text-slate-500 mt-1">{event.agent_label}</p>
          </div>
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="shrink-0 text-[11px] text-slate-400 hover:text-slate-600 transition-colors mt-0.5 whitespace-nowrap"
          >
            {showRaw ? "Hide raw ▲" : "View raw ▼"}
          </button>
        </div>

        {/* What they tried to reach */}
        <div className="mt-4 rounded-lg border border-amber-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Content attempted
            </p>
            <span className="text-[12px] font-bold text-amber-700">
              {event.articles_attempted} articles · 0 served
            </span>
          </div>
          <div className="space-y-1.5">
            {event.attempted.map((a, i) => (
              <div key={i} className="flex items-center justify-between text-[12px]">
                <span className="font-medium text-slate-600">{a.journal_code}</span>
                <span className="text-slate-400">
                  {a.article_count} {a.article_count === 1 ? "article" : "articles"} · {a.publisher_label}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-amber-100 flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <span className="text-[11px] text-amber-700 font-medium">{event.block_reason}</span>
          </div>
        </div>

        <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
          The agent's query intent is captured even though no content was served.
        </p>
      </div>

      {showRaw && (
        <div className="border-t border-amber-200 bg-slate-950 px-5 py-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Raw event · {event.event_id}
          </p>
          <pre className="text-[11px] text-slate-300 leading-relaxed overflow-x-auto font-mono">{raw}</pre>
        </div>
      )}
    </div>
  );
}

// ── How it works panel ─────────────────────────────────────────────────────

function HowItWorksPanel() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-6 py-5">
      <p className="text-[13px] font-semibold text-slate-700 mb-5">How attribution is captured</p>
      <div className="space-y-5">
        {[
          {
            n: "01", title: "Query received",
            body: "The /ask endpoint receives the query and institution ID. License terms are loaded immediately — every retrieval is governed, not just the API boundary.",
          },
          {
            n: "02", title: "Retrieval + license check per chunk",
            body: "Enriched chunks are retrieved via hybrid search. Each chunk is individually license-checked — decision is RAG_READ_RAG_SOURCE, SNIPPET_ONLY, or NO_ACCESS.",
          },
          {
            n: "03", title: "Two outcomes, both logged",
            body: "If content is served: a 'served' event is written with article, sections, and license terms. If all content is blocked: a 'blocked' event is written — the agent's query intent is captured even though they received nothing.",
          },
          {
            n: "04", title: "Publisher feed updated",
            body: "Both event types appear here, filtered to your journals. The query is always visible — even a blocked agent reveals what they were looking for.",
          },
        ].map(s => (
          <div key={s.n} className="flex gap-4">
            <span className="shrink-0 w-7 h-7 rounded-full bg-slate-100 text-slate-500 text-[11px] font-bold flex items-center justify-center">
              {s.n}
            </span>
            <div>
              <p className="text-[13px] font-semibold text-slate-700">{s.title}</p>
              <p className="text-[12px] text-slate-500 leading-relaxed mt-0.5">{s.body}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-lg bg-slate-950 px-4 py-3">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Blocked event schema</p>
        <pre className="text-[11px] text-slate-300 leading-relaxed font-mono">{`{
  "event_type": "blocked",
  "query": "How does GPX4 resistance develop?",
  "agent": "Commercial AI agent",
  "attempted": [
    { "journal": "REDOX", "publisher": "Elsevier", "articles": 2 }
  ],
  "articles_served": 0,
  "block_reason": "No active license for this agent"
}`}</pre>
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
        <p className="text-[11px] font-semibold text-slate-600 mb-1">
          What this enables that a login wall cannot
        </p>
        <ul className="text-[11px] text-slate-500 space-y-1 list-disc list-inside leading-relaxed">
          <li>Query intent captured even when access is denied — the agent reveals what it sought</li>
          <li>Journal-level visibility into which content is being targeted by unlicensed agents</li>
          <li>Governance lives in the content layer, not just at the HTTP boundary</li>
          <li>Both served and blocked in one chronological feed — full picture of demand</li>
        </ul>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function AttributionPage({ onSwitch }: Props) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<AttributionSummary | null>(null);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, f] = await Promise.all([
        fetchAttributionSummary(),
        fetchAttributionFeed(),
      ]);
      setSummary(s);
      setFeed(f);
    } catch {
      // empty state handles it
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const totalCitations = summary?.publishers.reduce((sum, p) => sum + p.article_citations, 0) ?? 0;
  const totalInstitutions = summary?.publishers.reduce((sum, p) => sum + p.institution_count, 0) ?? 0;

  const topSections = (() => {
    if (!summary) return [];
    const sectionMap: Record<string, number> = {};
    summary.publishers.forEach(p =>
      p.top_sections.forEach(s => {
        sectionMap[s.section] = (sectionMap[s.section] ?? 0) + s.count;
      })
    );
    return Object.entries(sectionMap)
      .map(([section, count]) => ({ section, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  })();

  return (
    <div className="flex min-h-screen bg-slate-50">

      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-slate-200/60 bg-white flex flex-col h-screen sticky top-0">
        <div className="flex-1 px-6 py-7 space-y-6 overflow-y-auto">
          <div>
            <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase mb-1">View</p>
            <p className="text-[15px] font-semibold text-slate-800">Publisher Attribution</p>
            <p className="text-[12px] text-slate-400 mt-1 leading-relaxed">
              Live feed of served and blocked access events, by publisher
            </p>
          </div>

          <hr className="border-slate-200/60" />

          {summary && (
            <div className="space-y-2">
              <div className="flex justify-between text-[12px]">
                <span className="text-slate-500">Queries served</span>
                <span className="font-semibold text-slate-700">{summary.total_served}</span>
              </div>
              <div className="flex justify-between text-[12px]">
                <span className="text-amber-600">Access blocked</span>
                <span className="font-semibold text-amber-700">{summary.total_blocked}</span>
              </div>
            </div>
          )}

        </div>

        <div className="px-6 py-5 border-t border-slate-200/60 space-y-3">
          <button
            onClick={() => navigate("/search")}
            className="block w-full text-left text-[13px] text-slate-500 hover:text-slate-700 font-medium transition-colors py-2 px-2 rounded hover:bg-slate-50"
          >
            ← Back to Search
          </button>
          <button
            onClick={onSwitch}
            className="block w-full text-left text-[13px] text-slate-400 hover:text-slate-600 transition-colors py-1 px-2 rounded"
          >
            Switch institution
          </button>
          <div className="opacity-40"><BeaconLogo size="sm" /></div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">

        <div className="px-10 pt-8 pb-5 border-b border-slate-200/60 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <BeaconLogo size="sm" />
                <span className="text-slate-200">/</span>
                <span className="text-[13px] font-medium text-slate-400">Attribution</span>
              </div>
              <p className="text-[13px] text-slate-400">
                Every access event — served and blocked — with query intent always visible
              </p>
            </div>
            <button
              onClick={() => setShowHowItWorks(!showHowItWorks)}
              className={`px-4 py-2 rounded-lg border text-[13px] font-medium transition-colors ${
                showHowItWorks
                  ? "bg-slate-800 text-white border-slate-800"
                  : "border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {showHowItWorks ? "Hide" : "How it works"}
            </button>
          </div>
        </div>

        <div className="px-10 py-8 space-y-8">
          {showHowItWorks && <HowItWorksPanel />}

          {/* Stats */}
          {summary && (
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Queries served",    value: summary.total_served,   color: "text-slate-800" },
                { label: "Article citations", value: totalCitations,          color: "text-slate-800" },
                { label: "Access blocked",    value: summary.total_blocked,   color: summary.total_blocked > 0 ? "text-amber-600" : "text-slate-800" },
                { label: "Institutions",      value: totalInstitutions,       color: "text-slate-800" },
              ].map(stat => (
                <div key={stat.label} className="rounded-xl border border-slate-200 bg-white px-5 py-4">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    {stat.label}
                  </p>
                  <p className={`text-[26px] font-bold leading-none ${stat.color}`}>{stat.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Section distribution */}
          {topSections.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white px-6 py-5">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-4">
                Sections surfaced
              </p>
              <div className="space-y-2.5">
                {topSections.map(s => {
                  const max = topSections[0].count;
                  const pct = Math.round((s.count / max) * 100);
                  return (
                    <div key={s.section} className="flex items-center gap-3">
                      <span className="text-[12px] text-slate-600 w-52 truncate shrink-0">{s.section}</span>
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-slate-400 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-[11px] text-slate-400 w-5 text-right shrink-0">{s.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Feed */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Event feed
              </p>
              <div className="flex items-center gap-3">
                {feed.length > 0 && (
                  <span className="text-[11px] text-slate-400">Refreshes every 5s</span>
                )}
                <button
                  disabled={simulating || feed.length === 0}
                  onClick={async () => {
                    const q = feed.find(e => e.event_type === "served")?.query
                      ?? "How does ferroptosis regulate cancer cell death?";
                    setSimulating(true);
                    await simulateBlockedRequest(q);
                    await refresh();
                    setSimulating(false);
                  }}
                  className="px-3 py-1.5 rounded-lg border border-amber-200 bg-amber-50 text-[12px] font-medium text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Fires the same query as a Commercial AI agent (no license) to show a blocked event"
                >
                  {simulating ? "Simulating…" : "Simulate blocked request"}
                </button>
              </div>
            </div>

            {loading && (
              <div className="space-y-3">
                {[1, 2].map(i => (
                  <div key={i} className="rounded-xl border border-slate-200 bg-white h-32 animate-pulse" />
                ))}
              </div>
            )}

            {!loading && feed.length === 0 && (
              <div className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center">
                <p className="text-[14px] font-semibold text-slate-600 mb-2">No events yet</p>
                <p className="text-[13px] text-slate-400 max-w-sm mx-auto">
                  Run queries in Beacon Search — try once as a licensed institution, then switch to Guest to generate a blocked event
                </p>
                <button
                  onClick={() => navigate("/search")}
                  className="mt-5 px-5 py-2.5 rounded-lg border border-slate-200 text-[13px] font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  Go to Search →
                </button>
              </div>
            )}

            {!loading && feed.length > 0 && (
              <div className="space-y-4">
                {feed.map(ev =>
                  ev.event_type === "served"
                    ? <ServedCard key={ev.event_id} event={ev} />
                    : <BlockedCard key={ev.event_id} event={ev} />
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
