import { useState } from "react";
import type { SearchResult, JournalInfo } from "../../types";
import AccessBadge from "./AccessBadge";
import JournalPill from "./JournalPill";
import EntityTags from "./EntityTags";
import ContentRenderer from "./ContentRenderer";
import CitationContext from "./CitationContext";

const BORDER_COLORS = {
  ALLOWED:      "border-l-green-500",
  SNIPPET_ONLY: "border-l-amber-400",
  OPEN_ACCESS:  "border-l-sky-400",
};

const BG_COLORS = {
  ALLOWED:      "bg-white",
  SNIPPET_ONLY: "bg-white",
  OPEN_ACCESS:  "bg-white",
};

interface Props {
  result: SearchResult;
  journals: Record<string, JournalInfo>;
}

export default function ResultCard({ result, journals }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showFigures, setShowFigures] = useState(false);
  const { license, metadata, text } = result;
  const { decision } = license;

  const journal = journals[license.journal_code] ?? { name: license.journal_code, publisher: "", color: "#64748b" };
  const doiUrl = metadata.doi ? `https://doi.org/${metadata.doi}` : null;

  const linkedFigures = result.linked_figures ?? [];
  const hybridDbg = result.hybrid_debug;
  const rerankDbg = result.rerank_debug;
  const isChunkFigure = metadata.chunk_type === "figure" || metadata.chunk_type === "table";

  return (
    <div className={`border border-slate-100 border-l-4 ${BORDER_COLORS[decision]} ${BG_COLORS[decision]} rounded-lg p-5 hover:shadow-sm transition-shadow`}>
      {/* Meta row */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <JournalPill code={license.journal_code} color={journal.color} />
        <span className="text-xs text-slate-400">{journal.name}</span>
        {metadata.section && (
          <>
            <span className="text-slate-200">·</span>
            <span className="text-xs text-slate-400 capitalize">{metadata.section}</span>
          </>
        )}
        {/* Enrichment indicators */}
        {isChunkFigure && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-violet-50 text-violet-600 border border-violet-200">
            {metadata.chunk_type === "figure" ? "Figure" : "Table"}
          </span>
        )}
        {hybridDbg && hybridDbg.bm25_rank !== null && hybridDbg.bm25_rank <= 5 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-200"
                title={`BM25 rank: ${hybridDbg.bm25_rank}, Vector rank: ${hybridDbg.vector_rank ?? "—"}`}>
            Exact match
          </span>
        )}
        {rerankDbg && rerankDbg.intent !== "general" && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-500 border border-blue-200"
                title={`Section boost: ${rerankDbg.section_multiplier}x`}>
            {rerankDbg.intent}
          </span>
        )}
        <div className="ml-auto">
          <AccessBadge decision={decision} />
        </div>
      </div>

      {/* Title */}
      <p className="text-sm font-semibold text-slate-800 leading-snug mb-2">
        {metadata.title || "Untitled"}
      </p>

      {/* Content by decision */}
      {decision === "ALLOWED" && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 mb-2 transition-colors"
          >
            {expanded ? "Hide content ↑" : "View content ↓"}
          </button>
          {expanded && (
            <div className="mt-2 pt-4 border-t border-slate-100 space-y-1">
              {/* Section text / table / figure */}
              <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase mb-2">Content</p>
              <div className="bg-slate-50 rounded-lg px-4 py-3">
                <ContentRenderer text={text} chunkType={metadata.chunk_type} />
              </div>

              {/* Entities */}
              <EntityTags raw={metadata.entities} />

              {/* DOI */}
              {doiUrl && (
                <div className="pt-3">
                  <a href={doiUrl} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-xs text-blue-500 hover:text-blue-700 transition-colors">
                    View full article ↗
                    <span className="text-slate-300 font-mono">{metadata.doi}</span>
                  </a>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {decision === "SNIPPET_ONLY" && (
        <>
          <div className="bg-slate-50 rounded-lg px-4 py-3 mb-4">
            <ContentRenderer text={text} chunkType={metadata.chunk_type} maxChars={320} />
          </div>
          {doiUrl && (
            <a href={doiUrl} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-amber-300 text-amber-700 text-xs font-semibold hover:bg-amber-50 transition-colors">
              Get full access on {journal.publisher} ↗
            </a>
          )}
        </>
      )}

      {decision === "OPEN_ACCESS" && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 mb-2 transition-colors"
          >
            {expanded ? "Hide content ↑" : "View content ↓"}
          </button>
          {expanded && (
            <div className="mt-2 pt-4 border-t border-slate-100 space-y-1">
              <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase mb-2">Content</p>
              <div className="bg-slate-50 rounded-lg px-4 py-3">
                <ContentRenderer text={text} chunkType={metadata.chunk_type} />
              </div>

              <EntityTags raw={metadata.entities} />

              {doiUrl && (
                <div className="pt-3">
                  <a href={doiUrl} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-xs text-sky-500 hover:text-sky-700 transition-colors">
                    Read full article on {journal.publisher} ↗
                    <span className="text-slate-300 font-mono">{metadata.doi}</span>
                  </a>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Linked figures/tables */}
      {linkedFigures.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <button
            onClick={() => setShowFigures(!showFigures)}
            className="text-[10px] font-semibold tracking-wider text-violet-500 uppercase flex items-center gap-1.5 hover:text-violet-700 transition-colors"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
            {linkedFigures.length} linked {linkedFigures.length === 1 ? "figure" : "figures/tables"}
            <span className="text-violet-300">{showFigures ? "↑" : "↓"}</span>
          </button>
          {showFigures && (
            <div className="mt-2 space-y-2">
              {linkedFigures.map((fig) => (
                <div key={fig.id} className="bg-violet-50/50 border border-violet-100 rounded-lg px-4 py-3">
                  <span className="text-[10px] font-semibold text-violet-500 uppercase tracking-wider">
                    {fig.chunk_type}
                  </span>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">{fig.text.slice(0, 300)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {metadata.source && <CitationContext source={metadata.source} />}
    </div>
  );
}
