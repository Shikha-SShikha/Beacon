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
    <div className="border-b border-slate-100 bg-white">
      <div className="flex divide-x divide-slate-100">
        <StatCell
          label="✦ Beacon (your system)"
          value={`${bSources} sources`}
          sub={`${bEntities} entities in retrieved chunks`}
          highlight
        />
        <div className="flex-1 px-4 py-3 text-center bg-slate-50/40 border-r border-slate-100">
          <p className="text-[10px] font-bold uppercase tracking-wider mb-1 text-slate-400">Sections retrieved</p>
          {bSections.length > 0 ? (
            <div className="flex flex-wrap gap-1 justify-center">
              {bSections.map(s => (
                <span key={s} className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${SECTION_COLORS[s?.toLowerCase()] ?? SECTION_COLORS.other}`}>
                  {s}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-slate-400">—</p>
          )}
        </div>
        <StatCell
          label="Standard RAG"
          value={`${rSources} sources`}
          sub="no entity extraction"
          dim
        />
      </div>
      <div className="flex divide-x divide-slate-100 border-t border-slate-100">
        <div className="flex-1 px-4 py-2 text-center bg-blue-50/60">
          <p className="text-[10px] text-blue-600">
            BM25 + vector hybrid · entity-linked · section-weighted · figure-aware
          </p>
        </div>
        <div className="flex-[2] px-4 py-2 text-center bg-slate-50/40">
          <p className="text-[10px] text-slate-400">
            Vector-only · HTML text · no entity recognition · no section weighting
          </p>
        </div>
      </div>
    </div>
  );
}

function ColumnHeader({
  icon, label, sublabel, accent,
}: { icon: string; label: string; sublabel: string; accent: string }) {
  return (
    <div className={`px-5 py-4 border-b ${accent} shrink-0`}>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="text-lg">{icon}</span>
        <p className="text-[14px] font-bold text-slate-800">{label}</p>
      </div>
      <p className="text-[11px] text-slate-400">{sublabel}</p>
    </div>
  );
}

function RagColumn({ response, loading }: { response: AskResponse | null; loading: boolean }) {
  const isBlocked = !!response && response.sources.length === 0 &&
    response.answer.startsWith("No accessible results");

  return (
    <div className="flex-1 flex flex-col min-w-0 border-r border-slate-100">
      <ColumnHeader
        icon="🤖"
        label="Standard AI RAG"
        sublabel="Plain HTML text · vector search · no enrichment"
        accent="border-slate-100"
      />
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {loading && <SkeletonLines />}
        {!loading && !response && <p className="text-[13px] text-slate-400 py-8 text-center">Run a search to compare</p>}

        {!loading && response && isBlocked && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-4 space-y-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
              <p className="text-[13px] font-semibold text-amber-800">Access blocked</p>
            </div>
            <p className="text-[12px] text-amber-700 leading-relaxed">
              No licensed content was served for this agent. The html-scraped collection
              passed the same license check — every retrieval path is governed, not just the enriched pipeline.
            </p>
          </div>
        )}

        {!loading && response && !isBlocked && (
          <>
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-1">
              <p className="text-[11px] font-semibold text-amber-700">What this retrieval cannot see</p>
              <ul className="text-[11px] text-amber-600 space-y-0.5 list-disc list-inside">
                <li>Figures and tables reduced to placeholders — visual evidence lost</li>
                <li>No section weighting — abstract text dominates over Results/Methods</li>
                <li>No entity linking — GPX4, METTL3 treated as plain strings, not ontology nodes</li>
                <li>No semantic relations — co-occurrence ≠ causal understanding</li>
                <li>Vector-only search — exact biological terms may rank below paraphrases</li>
              </ul>
            </div>

            <p className="text-[13px] text-slate-600 leading-relaxed">{response.answer}</p>

            {response.sources.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Sources ({response.sources.length})
                </p>
                <div className="space-y-2">
                  {response.sources.map((src) => {
                    const sections = src.sections.map(s => s.section || "other");
                    const hasImageOrTable = src.sections.some(
                      s => s.text.startsWith("[IMAGE]") || s.text.startsWith("[TABLE]")
                    );
                    return (
                      <div key={src.citation_id} className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                        <p className="text-[12px] font-semibold text-slate-700 line-clamp-1">{src.title || src.source}</p>
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          <span className="text-[10px] text-slate-400">{src.journal_code || "—"}</span>
                          {[...new Set(sections)].map(s => <SectionPill key={s} section={s} />)}
                          {hasImageOrTable && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-50 text-red-500 font-semibold border border-red-100">
                              ⚠ figures/tables as text
                            </span>
                          )}
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
            )}
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

  const beaconBlocked = !!ragResponse && ragResponse.sources.length === 0 &&
    ragResponse.answer.startsWith("No accessible results");

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
        <div className="bg-white rounded-t-2xl shadow-2xl border-t border-slate-200 h-[72vh] flex flex-col">

          {/* Drawer handle + top bar */}
          <div className="px-6 pt-3 pb-0 shrink-0">
            <div className="w-10 h-1 rounded-full bg-slate-200 mx-auto mb-3" />
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-[15px] font-bold text-slate-800">
                  {beaconBlocked ? "What this agent can still access" : "How other searches handle this query"}
                </p>
                <p className="text-[12px] text-slate-400 mt-0.5">
                  {beaconBlocked
                    ? "Licensed content blocked · general training knowledge cannot be restricted"
                    : "Same LLM — only the retrieval and knowledge access differs"}
                </p>
              </div>
              <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

          </div>

          {/* Retrieval quality comparison */}
          <ComparisonBanner beaconResponse={beaconResponse} ragResponse={ragResponse} />

          <div className="flex-1 flex overflow-hidden">
            <RagColumn response={ragResponse} loading={ragLoading} />
          </div>
        </div>
      </div>
    </>
  );
}
