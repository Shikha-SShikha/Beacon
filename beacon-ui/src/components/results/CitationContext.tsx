import { useState } from "react";
import type { CitationContextData, CorpusArticle, FoundationalPaper } from "../../types";
import { fetchCitationContext } from "../../api/client";

interface Props {
  source: string;
}

export default function CitationContext({ source }: Props) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<CitationContextData | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleToggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (data) return;
    setLoading(true);
    try {
      const result = await fetchCitationContext(source);
      setData(result);
    } catch {
      setData({ related_corpus: [], by_same_author: [], foundational: [] });
    } finally {
      setLoading(false);
    }
  }

  const hasContent = data && (
    data.related_corpus.length > 0 ||
    data.by_same_author.length > 0 ||
    data.foundational.length > 0
  );

  return (
    <div className="mt-3 pt-3 border-t border-slate-100">
      <button
        onClick={handleToggle}
        className="text-[11px] text-slate-400 hover:text-slate-600 font-medium flex items-center gap-1 transition-colors"
      >
        <span className="text-slate-300">{open ? "▴" : "▾"}</span>
        {open ? "Hide context" : "Explore context"}
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {loading && (
            <p className="text-xs text-slate-400 animate-pulse">Loading citation context…</p>
          )}

          {data && !hasContent && (
            <p className="text-xs text-slate-400">No citation context available for this article.</p>
          )}

          {data && hasContent && (
            <>
              {data.related_corpus.length > 0 && (
                <Section label="Related in collection">
                  {data.related_corpus.map((a) => (
                    <ArticleRow
                      key={a.doi}
                      article={a}
                      note={`${a.shared_refs} shared ref${a.shared_refs !== 1 ? "s" : ""}`}
                      dotColor="bg-violet-300"
                    />
                  ))}
                </Section>
              )}

              {data.by_same_author.length > 0 && (
                <Section label="By same author">
                  {data.by_same_author.slice(0, 3).map((a) => (
                    <ArticleRow
                      key={a.doi}
                      article={a}
                      note={a.shared_authors?.map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(", ")}
                      dotColor="bg-blue-300"
                    />
                  ))}
                </Section>
              )}

              {data.foundational.length > 0 && (
                <Section label="Key references">
                  {data.foundational.map((p, i) => (
                    <FoundationalRow key={i} paper={p} />
                  ))}
                </Section>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase mb-2">{label}</p>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function ArticleRow({ article, note, dotColor }: { article: CorpusArticle; note?: string; dotColor: string }) {
  const firstAuthor = article.authors[0]?.split(",")[0]?.trim() ?? "";
  const etAl = article.authors.length > 1 ? " et al." : "";
  return (
    <div className="flex items-start gap-2">
      <span className={`flex-shrink-0 w-1.5 h-1.5 rounded-full ${dotColor} mt-1.5`} />
      <div>
        <p className="text-xs text-slate-700 leading-snug">{article.title || article.source}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">
          {firstAuthor}{etAl}
          {article.year && ` · ${article.year}`}
          {note && <span className="ml-2 text-slate-300">· {note}</span>}
        </p>
      </div>
    </div>
  );
}

function FoundationalRow({ paper }: { paper: FoundationalPaper }) {
  const firstAuthor = paper.authors[0]?.split(",")[0]?.trim() ?? "";
  const etAl = paper.authors.length > 1 ? " et al." : "";
  return (
    <div className="flex items-start gap-2">
      <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5" />
      <div>
        <p className="text-xs text-slate-600 leading-snug">{paper.title}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">
          {firstAuthor}{etAl}
          {paper.year && ` · ${paper.year}`}
          {paper.journal && ` · ${paper.journal}`}
          {paper.cited_by_corpus !== undefined && paper.cited_by_corpus > 1 && (
            <span className="ml-2 text-blue-400">cited in {paper.cited_by_corpus} corpus articles</span>
          )}
        </p>
      </div>
    </div>
  );
}
