import { useEffect, useRef } from "react";
import type { AskResponse } from "../../types";

interface Props {
  ragResponse: AskResponse | null;
  ragLoading: boolean;
  open: boolean;
  onClose: () => void;
  beaconResponse?: AskResponse | null;
}

function SkeletonLines() {
  return (
    <div className="space-y-2.5 py-4 px-1">
      {[92, 100, 84, 100, 76, 88, 60].map((w, i) => (
        <div
          key={i}
          className="h-2.5 bg-slate-100 rounded-full animate-pulse"
          style={{ width: `${w}%`, animationDelay: `${i * 60}ms` }}
        />
      ))}
    </div>
  );
}

const SECTION_COLORS: Record<string, string> = {
  results:      "bg-emerald-100 text-emerald-700",
  methods:      "bg-sky-100 text-sky-700",
  discussion:   "bg-amber-100 text-amber-700",
  introduction: "bg-slate-100 text-slate-500",
  conclusion:   "bg-indigo-100 text-indigo-700",
  abstract:     "bg-slate-100 text-slate-500",
  figure:       "bg-violet-100 text-violet-700",
  table:        "bg-violet-100 text-violet-700",
  other:        "bg-slate-100 text-slate-400",
};

function SectionPill({ section }: { section: string }) {
  const cls = SECTION_COLORS[section?.toLowerCase()] ?? SECTION_COLORS.other;
  return (
    <span className={`inline-block text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${cls}`}>
      {section || "other"}
    </span>
  );
}

function StatCell({
  label, value, sub, highlight, dim,
}: {
  label: string; value: string; sub?: string; highlight?: boolean; dim?: boolean;
}) {
  return (
    <div className={`flex-1 px-4 py-3 text-center border-r last:border-r-0 border-slate-100 ${highlight ? "bg-blue-50/60" : dim ? "bg-slate-50/40" : ""}`}>
      <p className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${highlight ? "text-blue-500" : "text-slate-400"}`}>{label}</p>
      <p className={`text-[13px] font-semibold ${highlight ? "text-blue-700" : dim ? "text-slate-400" : "text-slate-600"}`}>{value}</p>
      {sub && <p className={`text-[10px] mt-0.5 ${highlight ? "text-blue-500" : "text-slate-400"}`}>{sub}</p>}
    </div>
  );
}

function ComparisonBanner({
  beaconResponse, ragResponse,
}: {
  beaconResponse?: AskResponse | null;
  ragResponse: AskResponse | null;
}) {
  if (!beaconResponse && !ragResponse) return null;

  const bSources = beaconResponse?.sources.length ?? 0;
  const bEntities = beaconResponse?.sources.reduce((s, src) => s + (src.entity_count ?? 0), 0) ?? 0;
  const bSections = [
    ...new Set(
      beaconResponse?.sources
        .flatMap(s => s.sections.map(sec => sec.section || sec.chunk_type))
        .filter(Boolean) ?? []
    ),
  ].filter(s => s !== "other");

  const rSources = ragResponse?.sources.length ?? 0;

  return (
    <div className="border-b border-slate-100 bg-white shrink-0">
      <div className="flex divide-x divide-slate-100">
        <StatCell
          label="✦ Beacon"
          value={`${bSources} sources · ${bEntities} entities`}
          sub={bSections.length > 0 ? `sections: ${bSections.join(", ")}` : undefined}
          highlight
        />
        <StatCell
          label="Standard RAG"
          value={`${rSources} sources`}
          sub="no entity extraction · vector only"
          dim
        />
      </div>
    </div>
  );
}

function SourceList({ sources, accent }: { sources: AskResponse["sources"]; accent: string }) {
  if (sources.length === 0) return null;
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
        Sources ({sources.length})
      </p>
      <div className="space-y-2">
        {sources.map((src) => {
          const sections = [...new Set(src.sections.map(s => s.section || "other"))];
          return (
            <div key={src.citation_id} className={`p-3 rounded-lg border ${accent}`}>
              <p className="text-[12px] font-semibold text-slate-700 line-clamp-1">{src.title || src.source}</p>
              <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                <span className="text-[10px] text-slate-400">{src.journal_code || "—"}</span>
                {sections.map(s => <SectionPill key={s} section={s} />)}
              </div>
              {src.sections[0] && (
                <p className="text-[11px] text-slate-500 mt-1.5 line-clamp-2">
                  {src.sections[0].text.slice(0, 160)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BeaconColumn({ response }: { response: AskResponse | null }) {
  return (
    <div className="flex-1 flex flex-col min-w-0 border-r border-slate-200">
      <div className="px-5 py-3 border-b border-blue-100 bg-blue-50/40 shrink-0">
        <p className="text-[13px] font-bold text-blue-800">✦ Beacon — Enriched RAG</p>
        <p className="text-[10px] text-blue-500 mt-0.5">BM25 + vector · entity-linked · section-weighted · figure-aware</p>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {!response && <p className="text-[13px] text-slate-400 py-8 text-center">No response</p>}
        {response && (
          <>
            <p className="text-[13px] text-slate-700 leading-relaxed">{response.answer}</p>
            <SourceList sources={response.sources} accent="bg-blue-50/40 border-blue-100" />
          </>
        )}
      </div>
    </div>
  );
}

function RagColumn({ response, loading }: { response: AskResponse | null; loading: boolean }) {
  const isBlocked = !!response && response.sources.length === 0 &&
    response.answer.startsWith("No accessible results");

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/40 shrink-0">
        <p className="text-[13px] font-bold text-slate-600">Standard AI RAG</p>
        <p className="text-[10px] text-slate-400 mt-0.5">Vector-only · plain text · no entity linking · no section weighting</p>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {loading && <SkeletonLines />}
        {!loading && !response && (
          <p className="text-[13px] text-slate-400 py-8 text-center">Run a search to compare</p>
        )}
        {!loading && response && isBlocked && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-4 space-y-1">
            <p className="text-[13px] font-semibold text-amber-800">Access blocked</p>
            <p className="text-[12px] text-amber-700 leading-relaxed">
              No licensed content accessible for this institution — the same license check applies to all retrieval paths.
            </p>
          </div>
        )}
        {!loading && response && !isBlocked && (
          <>
            <p className="text-[13px] text-slate-600 leading-relaxed">{response.answer}</p>
            <SourceList sources={response.sources} accent="bg-slate-50 border-slate-100" />
          </>
        )}
      </div>
    </div>
  );
}

export default function BaselineDrawer({
  ragResponse, ragLoading, open, onClose, beaconResponse,
}: Props) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) onClose();
    }
    const timer = setTimeout(() => document.addEventListener("mousedown", handleClick), 100);
    return () => { clearTimeout(timer); document.removeEventListener("mousedown", handleClick); };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`fixed inset-0 bg-black/20 z-40 transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`} />

      <div
        ref={drawerRef}
        className={`fixed bottom-0 left-0 right-0 z-50 transform transition-transform duration-300 ease-out ${open ? "translate-y-0" : "translate-y-full"}`}
      >
        <div className="bg-white rounded-t-2xl shadow-2xl border-t border-slate-200 h-[75vh] flex flex-col">

          {/* Drawer handle + top bar */}
          <div className="px-6 pt-3 pb-3 shrink-0 border-b border-slate-100">
            <div className="w-10 h-1 rounded-full bg-slate-200 mx-auto mb-3" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[15px] font-bold text-slate-800">Answer comparison</p>
                <p className="text-[12px] text-slate-400 mt-0.5">Same query · same LLM · same licensed corpus — only retrieval differs</p>
              </div>
              <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Stats banner */}
          <ComparisonBanner beaconResponse={beaconResponse} ragResponse={ragResponse} />

          {/* Side-by-side answer columns */}
          <div className="flex-1 flex overflow-hidden">
            <BeaconColumn response={beaconResponse ?? null} />
            <RagColumn response={ragResponse} loading={ragLoading} />
          </div>
        </div>
      </div>
    </>
  );
}
