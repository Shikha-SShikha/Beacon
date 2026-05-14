import type { InstitutionSummary } from "../../types";
import BeaconLogo from "../ui/BeaconLogo";

const FULL_ACCESS = new Set(["RAG_READ_RAG_SOURCE", "OPEN_ACCESS"]);

const PUBLISHER_LABELS: Record<string, string> = {
  "Elsevier":            "Publisher A",
  "Pleiades Publishing": "Publisher B",
  "Portland Press":      "Publisher C",
};

interface Props {
  institution: InstitutionSummary;
  topK: number;
  onTopKChange: (v: number) => void;
  onSwitch: () => void;
  onCollections?: () => void;
  onAttribution?: () => void;
}

export default function Sidebar({ institution, topK, onTopKChange, onSwitch, onCollections, onAttribution }: Props) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200/60 bg-white flex flex-col h-screen sticky top-0">
      <div className="flex-1 px-6 py-7 space-y-6 overflow-hidden">

        {/* Institution */}
        <div>
          <div className="text-2xl mb-2">{institution.avatar}</div>
          <p className="text-[15px] font-semibold text-slate-800 leading-tight">{institution.name}</p>
          <p className="text-[13px] text-slate-400 mt-1">{institution.description}</p>
        </div>

        <hr className="border-slate-200/60" />

        {/* Collection */}
        {institution.licensed_journals.length > 0 ? (
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">
                Your collection
              </p>
              <span className="text-[11px] text-slate-400">
                {institution.licensed_journals.length} journals
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {institution.licensed_journals.map((j) => {
                const isFullAccess = FULL_ACCESS.has(j.rights);
                return (
                  <div
                    key={j.code}
                    title={`${j.name} · ${PUBLISHER_LABELS[j.publisher] ?? j.publisher}`}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border cursor-default transition-colors ${
                      isFullAccess
                        ? "bg-white border-slate-200 hover:border-slate-300"
                        : "bg-amber-50 border-amber-200"
                    }`}
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: j.color }}
                    />
                    <span className="text-[12px] font-semibold text-slate-600">{j.code}</span>
                    {!isFullAccess && (
                      <span className="text-[9px] font-bold text-amber-600 uppercase tracking-wide">S</span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-400 mt-2.5">Hover any journal for full name</p>
          </div>
        ) : (
          <p className="text-[13px] text-slate-400">Open access content only</p>
        )}

        <hr className="border-slate-200/60" />

        {/* Top-K slider */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">Results</p>
            <span className="text-[13px] font-semibold text-slate-600">{topK}</span>
          </div>
          <input
            type="range" min={3} max={10} value={topK}
            onChange={(e) => onTopKChange(Number(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>

      </div>

      {/* Footer */}
      <div className="px-6 py-5 border-t border-slate-200/60 space-y-3">
        {onCollections && (
          <button
            onClick={onCollections}
            className="block w-full text-left text-[13px] text-slate-500 hover:text-slate-700 font-medium transition-colors py-2 hover:bg-slate-50 px-2 rounded"
          >
            Browse Collections
          </button>
        )}
        {onAttribution && (
          <button
            onClick={onAttribution}
            className="block w-full text-left text-[13px] text-slate-500 hover:text-slate-700 font-medium transition-colors py-2 hover:bg-slate-50 px-2 rounded"
          >
            Publisher Attribution
          </button>
        )}
        <button
          onClick={onSwitch}
          className="block w-full text-left text-[13px] text-blue-600 hover:text-blue-700 font-medium transition-colors py-2 hover:bg-blue-50 px-2 rounded"
        >
          Switch institution
        </button>
        <div className="opacity-40">
          <BeaconLogo size="sm" />
        </div>
      </div>
    </aside>
  );
}
