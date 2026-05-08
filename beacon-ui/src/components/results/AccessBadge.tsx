import type { LicenseDecision } from "../../types";

const VARIANTS = {
  ALLOWED: "bg-green-50 text-green-700 border-green-200",
  SNIPPET_ONLY: "bg-amber-50 text-amber-700 border-amber-200",
  OPEN_ACCESS: "bg-sky-50 text-sky-700 border-sky-200",
};

const LABELS = {
  ALLOWED: "Full text",
  SNIPPET_ONLY: "Snippet only",
  OPEN_ACCESS: "Open access",
};

const DOTS = {
  ALLOWED: "bg-green-500",
  SNIPPET_ONLY: "bg-amber-400",
  OPEN_ACCESS: "bg-sky-500",
};

export default function AccessBadge({ decision }: { decision: LicenseDecision["decision"] }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${VARIANTS[decision]}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${DOTS[decision]}`} />
      {LABELS[decision]}
    </span>
  );
}
