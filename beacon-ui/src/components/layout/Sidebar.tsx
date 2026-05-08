import type { InstitutionSummary } from "../../types";
import BeaconLogo from "../ui/BeaconLogo";

const RIGHTS_LABEL: Record<string, { label: string; className: string }> = {
  RAG_READ_RAG_SOURCE: { label: "Full text", className: "bg-green-50 text-green-700 border-green-200" },
  RAG:                 { label: "Snippet",   className: "bg-amber-50 text-amber-700 border-amber-200" },
};

interface Props {
  institution: InstitutionSummary;
  topK: number;
  onTopKChange: (v: number) => void;
  onSwitch: () => void;
}

export default function Sidebar({ institution, topK, onTopKChange, onSwitch }: Props) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200/60 bg-white flex flex-col min-h-screen">
      <div className="flex-1 px-6 py-7 space-y-6 overflow-y-auto">

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
            <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase mb-3">
              Your collection
            </p>
            <div className="space-y-3">
              {institution.licensed_journals.map((j) => {
                const rights = RIGHTS_LABEL[j.rights];
                return (
                  <div key={j.code} className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span
                        className="mt-1 w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: j.color }}
                      />
                      <div className="min-w-0">
                        <p className="text-[13px] font-semibold text-slate-700 truncate">{j.code}</p>
                        <p className="text-[11px] text-slate-400 truncate">{j.name}</p>
                      </div>
                    </div>
                    {rights && (
                      <span className={`shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full border ${rights.className}`}>
                        {rights.label}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
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
        <button
          onClick={onSwitch}
          className="text-[13px] text-blue-600 hover:text-blue-700 font-medium transition-colors"
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
