import { useEffect, useRef } from "react";
import type { AskResponse } from "../../types";

interface Props {
  response: AskResponse | null;
  loading: boolean;
  open: boolean;
  onClose: () => void;
}

export default function BaselineDrawer({ response, loading, open, onClose }: Props) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClick);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/20 z-40 transition-opacity duration-300 ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />

      <div
        ref={drawerRef}
        className={`fixed bottom-0 left-0 right-0 z-50 transform transition-transform duration-300 ease-out ${
          open ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="bg-white rounded-t-2xl shadow-2xl border-t border-slate-200 max-h-[70vh] flex flex-col">

          {/* Header */}
          <div className="px-8 pt-4 pb-3 border-b border-slate-100 shrink-0">
            <div className="w-10 h-1 rounded-full bg-slate-200 mx-auto mb-4" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[15px] font-semibold text-slate-700">
                  Standard AI search
                </p>
                <p className="text-[13px] text-slate-400 mt-0.5">
                  Plain vector search · no enrichment · same LLM, same prompt
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-slate-600 transition-colors p-1"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-8 py-6">
            {loading && (
              <div className="flex items-center justify-center py-12 text-slate-400 text-[15px] gap-3">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Synthesizing baseline answer...
              </div>
            )}

            {!loading && !response && (
              <div className="text-center py-12 text-slate-400 text-[15px]">
                No results found
              </div>
            )}

            {!loading && response && (
              <div className="space-y-6">
                {/* Synthesized answer */}
                <div>
                  <p className="text-[15px] text-slate-700 leading-[1.75]">
                    {response.answer}
                  </p>
                </div>

                {/* Sources */}
                {response.sources.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      Sources retrieved ({response.sources.length})
                    </p>
                    <div className="space-y-2">
                      {response.sources.map((src) => (
                        <div
                          key={src.citation_id}
                          className="flex gap-3 p-3.5 rounded-xl border border-slate-100 bg-slate-50/50"
                        >
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-slate-200 text-slate-500 text-[12px] font-bold shrink-0 mt-0.5">
                            {src.citation_id}
                          </span>
                          <div className="min-w-0">
                            <p className="text-[13px] font-medium text-slate-600 truncate">
                              {src.title || src.journal_code}
                            </p>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                              {src.journal_code}{src.year ? ` · ${src.year}` : ""}
                              {" · "}{src.sections.length} chunk{src.sections.length !== 1 ? "s" : ""}
                            </p>
                            {src.sections[0] && (
                              <p className="text-[12px] text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">
                                {src.sections[0].text.slice(0, 200)}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* What's missing callout */}
                <div className="p-5 rounded-xl bg-amber-50/50 border border-amber-200/50">
                  <p className="text-[13px] font-semibold text-amber-700 mb-2">What the retrieval layer is missing</p>
                  <ul className="text-[13px] text-amber-600 space-y-1.5 list-disc list-inside">
                    <li>Figures and tables retrieved as [IMAGE] placeholders — visual evidence never reaches the LLM</li>

                    <li>No section awareness — abstract chunks dominate even when methods or results are more relevant</li>
                    <li>No cross-linking between text claims and the figures that support them</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
