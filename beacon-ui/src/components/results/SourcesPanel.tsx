import { useState, useEffect, useRef } from "react";
import type { CitedSource, JournalInfo } from "../../types";

interface Props {
  sources: CitedSource[];
  journals: Record<string, JournalInfo>;
  open: boolean;
  onClose: () => void;
  highlightId: number | null;
}

const SECTION_LABELS: Record<string, { label: string; color: string }> = {
  results:      { label: "Results",      color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  methods:      { label: "Methods",      color: "text-sky-600 bg-sky-50 border-sky-200" },
  discussion:   { label: "Discussion",   color: "text-amber-600 bg-amber-50 border-amber-200" },
  introduction: { label: "Introduction", color: "text-slate-500 bg-slate-50 border-slate-200" },
  conclusion:   { label: "Conclusion",   color: "text-indigo-600 bg-indigo-50 border-indigo-200" },
  abstract:     { label: "Abstract",     color: "text-slate-500 bg-slate-50 border-slate-200" },
  figure:       { label: "Figure",       color: "text-violet-600 bg-violet-50 border-violet-200" },
  table:        { label: "Table",        color: "text-violet-600 bg-violet-50 border-violet-200" },
  other:        { label: "Other",        color: "text-slate-400 bg-slate-50 border-slate-200" },
};

function SectionBadge({ section }: { section: string }) {
  const s = SECTION_LABELS[section] ?? SECTION_LABELS.other;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border ${s.color}`}>
      {s.label}
    </span>
  );
}

function SectionSnippet({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref}>
      <p
        onClick={() => setOpen(!open)}
        className={`text-[13px] text-slate-600 leading-relaxed cursor-pointer hover:text-slate-800 transition-colors ${open ? "" : "line-clamp-3"}`}
      >
        {text}
      </p>
    </div>
  );
}

function SourceCard({ source, journals, highlighted }: {
  source: CitedSource;
  journals: Record<string, JournalInfo>;
  highlighted: boolean;
}) {
  const [expanded, setExpanded] = useState(highlighted);
  const ref = useRef<HTMLDivElement>(null);
  const journal = journals[source.journal_code];

  useEffect(() => {
    if (highlighted) {
      setExpanded(true);
      ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlighted]);

  const doiUrl = source.doi ? `https://doi.org/${source.doi}` : null;

  return (
    <div
      ref={ref}
      className={`rounded-xl border transition-all ${
        highlighted
          ? "border-blue-300 bg-blue-50/30 shadow-sm"
          : "border-slate-200 bg-white"
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-4 py-3.5 flex items-start gap-3"
      >
        <span className="shrink-0 flex items-center justify-center w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-[13px] font-bold">
          {source.citation_id}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold text-slate-800 leading-snug line-clamp-2">
            {source.title || source.source}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {journal && (
              <span className="text-[11px] font-medium text-slate-400">{journal.name}</span>
            )}
            {!journal && source.journal_code && (
              <span className="text-[11px] font-medium text-slate-400">{source.journal_code}</span>
            )}
            {source.year && (
              <>
                <span className="text-slate-200">·</span>
                <span className="text-[11px] text-slate-400">{source.year}</span>
              </>
            )}
            {source.license_decision === "SNIPPET_ONLY" && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-600 border border-amber-200">
                Snippet only
              </span>
            )}
          </div>
        </div>
        <span className="shrink-0 text-slate-300 text-[13px] mt-1">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-slate-100 space-y-2.5">
          {source.license_decision === "SNIPPET_ONLY" ? (
            <div className="mt-3">
              <p className="text-[13px] text-slate-500 mb-3">
                Your institution has snippet-only access to this journal. Full text is available on the publisher site.
              </p>
              {doiUrl && (
                <a
                  href={doiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[13px] text-amber-600 hover:text-amber-700 font-semibold transition-colors border border-amber-300 px-3 py-1.5 rounded-lg hover:bg-amber-50"
                >
                  Get full access on {source.publisher || "publisher"} ↗
                </a>
              )}
            </div>
          ) : (
            <>
              <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mt-3 mb-2">
                Relevant sections
              </p>
              {source.sections.map((sec, i) => (
                <div key={i} className="flex gap-2.5">
                  <div className="shrink-0 pt-0.5">
                    <SectionBadge section={sec.section || sec.chunk_type} />
                  </div>
                  <SectionSnippet text={sec.text} />
                </div>
              ))}
              {doiUrl && (
                <a
                  href={doiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[13px] text-blue-500 hover:text-blue-700 font-medium mt-3 transition-colors"
                >
                  View full article ↗
                </a>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function SourcesPanel({ sources, journals, open, onClose, highlightId }: Props) {
  if (!open) return null;

  return (
    <div className="w-[420px] shrink-0 border-l border-slate-200/60 bg-white flex flex-col h-full overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <svg className="w-4.5 h-4.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          <span className="text-[13px] font-semibold text-slate-600">
            Sources ({sources.length})
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition-colors p-1"
        >
          <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {sources.map((src) => (
          <SourceCard
            key={src.citation_id}
            source={src}
            journals={journals}
            highlighted={highlightId === src.citation_id}
          />
        ))}
      </div>
    </div>
  );
}
