import { useState } from "react";
import type { FoundationalPaper } from "../../types";
import { fetchFoundational } from "../../api/client";

interface Props {
  sources: string[];
}

export default function FoundationalPanel({ sources }: Props) {
  const [open, setOpen] = useState(false);
  const [papers, setPapers] = useState<FoundationalPaper[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  if (sources.length === 0) return null;

  async function handleToggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (loaded) return;
    setLoading(true);
    try {
      const result = await fetchFoundational(sources);
      setPapers(result.foundational);
    } catch {
      setPapers([]);
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }

  return (
    <div className="mt-6 pt-4 border-t border-slate-100">
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors"
      >
        <span className="flex items-center justify-center w-4 h-4 rounded bg-blue-50 text-blue-400 text-[10px] font-bold">↗</span>
        {open ? "Hide foundational papers ▴" : "Foundational papers behind these results ▾"}
      </button>

      {open && (
        <div className="mt-3">
          {loading && (
            <p className="text-xs text-slate-400 animate-pulse">Analyzing citation graph…</p>
          )}

          {loaded && !loading && papers.length === 0 && (
            <p className="text-xs text-slate-400">No shared foundational papers found across these results.</p>
          )}

          <ol className="space-y-3">
            {papers.map((p, i) => {
              const firstAuthor = p.authors[0]?.split(",")[0]?.trim() ?? "";
              const etAl = p.authors.length > 1 ? " et al." : "";
              return (
                <li key={i} className="flex items-start gap-3">
                  <span className="flex-shrink-0 text-[10px] text-blue-300 font-mono w-4 text-right mt-0.5">{i + 1}</span>
                  <div>
                    <p className="text-xs text-slate-700 leading-snug">{p.title}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {firstAuthor}{etAl}
                      {p.year && ` · ${p.year}`}
                      {p.journal && ` · ${p.journal}`}
                      {p.cited_by_count !== undefined && p.cited_by_count > 1 && (
                        <span className="ml-2 text-blue-400">cited across {p.cited_by_count} result{p.cited_by_count !== 1 ? "s" : ""}</span>
                      )}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
