import type { UpgradeHint } from "../../types";

interface Props {
  hint: UpgradeHint;
  onSignIn: () => void;
}

export default function UpgradePrompt({ hint, onSignIn }: Props) {
  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50 px-6 py-5">
      <div className="flex items-start gap-4">

        {/* Lock icon */}
        <div className="shrink-0 w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center mt-0.5">
          <svg className="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 mb-1">
            {hint.locked_count} result{hint.locked_count !== 1 ? "s" : ""} found behind a subscription
          </p>
          <p className="text-xs text-slate-500 leading-relaxed mb-3">
            Your query matches content in{" "}
            <span className="font-medium text-slate-700">
              {hint.journal_names.join(" and ")}
            </span>
            {". "}
            Sign in with your institutional credentials or publisher subscription to access it.
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={onSignIn}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors"
            >
              Sign in for access →
            </button>
            <span className="text-[11px] text-slate-400">
              Institutional login · Publisher subscription
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}
