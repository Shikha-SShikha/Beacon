import { useState, useEffect, useRef } from "react";
import type { CitedSource, JournalInfo } from "../../types";

interface Props {
  sources: CitedSource[];
  journals: Record<string, JournalInfo>;
  open: boolean;
  onClose: () => void;
  highlightId: number | null;
}

const SECTION_META: Record<string, { label: string; cls: string }> = {
  results:      { label: "Results",      cls: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  methods:      { label: "Methods",      cls: "bg-sky-100 text-sky-700 border-sky-200" },
  discussion:   { label: "Discussion",   cls: "bg-amber-100 text-amber-700 border-amber-200" },
  introduction: { label: "Introduction", cls: "bg-slate-100 text-slate-500 border-slate-200" },
  conclusion:   { label: "Conclusion",   cls: "bg-indigo-100 text-indigo-700 border-indigo-200" },
  abstract:     { label: "Abstract",     cls: "bg-slate-100 text-slate-500 border-slate-200" },
  figure:       { label: "Figure",       cls: "bg-violet-100 text-violet-700 border-violet-200" },
  table:        { label: "Table",        cls: "bg-violet-100 text-violet-700 border-violet-200" },
};

const FALLBACK_CLS = "bg-slate-100 text-slate-400 border-slate-200";

function SectionBadge({
  section, sectionTitle, subsectionTitle,
}: {
  section: string;
  sectionTitle?: string;
  subsectionTitle?: string;
}) {
  const key = section?.toLowerCase();
  const meta = SECTION_META[key];

  if (meta) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border uppercase tracking-wide ${meta.cls}`}>
        {meta.label}
      </span>
    );
  }

  // "other" — show subsection/section heading if available, else nothing
  const displayTitle = subsectionTitle || sectionTitle;
  if (!displayTitle) return null;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border ${FALLBACK_CLS}`}>
      {displayTitle}
    </span>
  );
}

function isMarkdownTable(text: string): boolean {
  return /^\|.+\|/m.test(text) && /^\|[\s:|-]+\|/m.test(text);
}

function MarkdownTableView({ text }: { text: string }) {
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  const tableStart = lines.findIndex(l => l.startsWith("|"));
  const beforeLines = tableStart > 0 ? lines.slice(0, tableStart) : [];
  const tableLines = lines.slice(tableStart).filter(l => l.startsWith("|"));

  const isSeparator = (l: string) => /^\|[\s:|-]+\|$/.test(l);
  const parseRow = (l: string) =>
    l.split("|").slice(1, -1).map(c => c.trim());

  const [header, ...rest] = tableLines.filter(l => !isSeparator(l));
  const headers = header ? parseRow(header) : [];
  const rows = rest.map(parseRow);

  return (
    <div>
      {beforeLines.map((l, i) => (
        <p key={i} className="text-[13px] text-slate-600 mb-2">{l}</p>
      ))}
      <div className="overflow-x-auto rounded border border-slate-200 mt-1">
        <table className="text-[12px] w-full border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {headers.map((h, i) => (
                <th key={i} className="px-3 py-2 text-left font-semibold text-slate-600 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                {row.map((cell, j) => (
                  <td key={j} className="px-3 py-2 text-slate-700 border-b border-slate-100">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function stripEntityPrefix(text: string): string {
  // Remove leading [TYPE: value | optional_id] blocks added for embedding
  return text.replace(/^(\[[A-Z_]+:[^\]]+\]\s*)+/, "").trim();
}

function SectionSnippet({ section, text }: { section: string; text: string }) {
  const displayText = stripEntityPrefix(text);
  const [expanded, setExpanded] = useState(false);
  const isTable = section?.toLowerCase() === "table" || isMarkdownTable(text);

  if (isTable && isMarkdownTable(text)) {
    return <MarkdownTableView text={displayText} />;
  }

  if (isTable) {
    // Table section but content is a prose description
    return (
      <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
        <p
          onClick={() => setExpanded(!expanded)}
          className={`text-[12px] text-slate-600 leading-relaxed cursor-pointer hover:text-slate-800 transition-colors ${expanded ? "" : "line-clamp-3"}`}
        >
          {displayText}
        </p>
      </div>
    );
  }

  return (
    <p
      onClick={() => setExpanded(!expanded)}
      className={`text-[13px] text-slate-600 leading-relaxed cursor-pointer hover:text-slate-800 transition-colors ${expanded ? "" : "line-clamp-3"}`}
    >
      {displayText}
    </p>
  );
}

function SourceCard({ source, journals, highlighted, expanded, onToggle }: {
  source: CitedSource;
  journals: Record<string, JournalInfo>;
  highlighted: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const journal = journals[source.journal_code];

  useEffect(() => {
    if (highlighted) {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlighted]);

  const doiUrl = source.doi ? `https://doi.org/${source.doi}` : null;

  return (
    <div
      ref={ref}
      className={`rounded-xl border transition-all ${
        highlighted
          ? "border-blue-300 bg-blue-50/20 shadow-sm"
          : "border-slate-200 bg-white"
      }`}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3.5 flex items-start gap-3"
      >
        <span className="shrink-0 flex items-center justify-center w-7 h-7 rounded-full bg-slate-100 text-slate-600 text-[13px] font-semibold">
          {source.citation_id}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold text-slate-800 leading-snug line-clamp-2">
            {source.title || source.source}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {(journal?.name || source.journal_code) && (
              <span className="text-[11px] text-slate-400">
                {journal?.name || source.journal_code}
              </span>
            )}
            {source.year && (
              <>
                <span className="text-slate-200">·</span>
                <span className="text-[11px] text-slate-400">{source.year}</span>
              </>
            )}
            {source.license_decision === "SNIPPET_ONLY" && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
                Snippet only
              </span>
            )}
            {!!source.entity_count && (
              <>
                <span className="text-slate-200">·</span>
                <span className="text-[11px] text-slate-400">
                  {source.entity_count} entities
                </span>
              </>
            )}
            {!!source.relation_count && (
              <span className="text-[11px] text-slate-400">
                · {source.relation_count} relations
              </span>
            )}
          </div>
        </div>
        <span className="shrink-0 text-slate-300 text-[11px] mt-1.5">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-slate-100 space-y-2.5">
          {source.license_decision === "SNIPPET_ONLY" ? (
            <div className="mt-3">
              <p className="text-[13px] text-slate-500 mb-3">
                Your institution has snippet-only access. Full text is available on the publisher site.
              </p>
              {doiUrl && (
                <a
                  href={doiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[13px] text-slate-600 hover:text-slate-800 font-medium transition-colors border border-slate-300 px-3 py-1.5 rounded-lg hover:bg-slate-50"
                >
                  View on publisher site ↗
                </a>
              )}
            </div>
          ) : (
            <>
              <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mt-3 mb-2">
                Relevant sections
              </p>
              {source.sections.map((sec, i) => (
                <div key={i} className="space-y-1.5 pt-2.5 first:pt-0 border-t border-slate-100 first:border-0">
                  <SectionBadge
                    section={sec.section || sec.chunk_type}
                    sectionTitle={sec.section_title}
                    subsectionTitle={sec.subsection_title}
                  />
                  <SectionSnippet section={sec.section || sec.chunk_type} text={sec.text} />
                </div>
              ))}
              {doiUrl && (
                <a
                  href={doiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[13px] text-slate-500 hover:text-slate-700 font-medium mt-3 transition-colors"
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
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    if (highlightId != null) setExpandedId(highlightId);
  }, [highlightId]);

  // Collapse all when sources change (new query)
  useEffect(() => {
    setExpandedId(null);
  }, [sources]);

  if (!open) return null;

  return (
    <div className="w-[420px] shrink-0 border-l border-slate-200/60 bg-white flex flex-col h-full overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
            expanded={expandedId === src.citation_id}
            onToggle={() => setExpandedId(expandedId === src.citation_id ? null : src.citation_id)}
          />
        ))}
      </div>
    </div>
  );
}
