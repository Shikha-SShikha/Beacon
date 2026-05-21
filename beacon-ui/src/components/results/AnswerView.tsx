import { useMemo } from "react";
import type { AskResponse, HighlightEntity } from "../../types";

interface Props {
  response: AskResponse;
  onCitationClick: (citationId: number) => void;
}

// Types too noisy, misclassified, or wrong domain — skip entirely
const SKIP_TYPES = new Set([
  // Generic / structural
  "ENTITY", "OTHER", "REFERENCE", "ENTITY_TYPE",
  // Metadata
  "AUTHOR", "JOURNAL", "ARTICLE", "YEAR", "TIME",
  // Geography / org
  "COUNTRY", "LOCATION", "ORGANIZATION", "PROFESSIONAL_BODY", "INDUSTRY",
  // Soft concepts
  "CONCEPT", "PROCESS", "METRIC", "PARAMETER", "FRAMEWORK",
  "GUIDELINE", "LIFESTYLE", "PARADOX", "CONTROL_TYPE", "STUDY",
  // High-noise typed buckets (data shows these are heavily misclassified)
  "METHOD",       // 380 entries: Python, NaCl, '2018', 'review' — unreliable
  "TECHNOLOGY",   // 340 entries: lab reagents (PBS, FBS) mixed with EV/energy domain
  "TOOL",         // project-mgmt tools (XP, SAFe, SCRUM)
  "THEORY",       // Taoism, Barker — wrong domain
  "DEVICE",       // only 'Qubit' — not worth it
  "SOFTWARE",     // only SPSS — not worth it
]);

// Minimum text length per type to block short/ambiguous matches
const MIN_LENGTH: Record<string, number> = {
  GENE:            3,   // filter single letters ('V', 'm', 'A')
  PROTEIN:         3,   // filter single chars
  CELL_LINE:       3,   // filter 'V', 'AA', 'RH'
  ORGANISM:        6,   // skip 'rat', 'mice', 'human', 'WHO' — require full species names
  ANATOMY:         4,
  ELEMENT:         4,
  VIRUS:           3,
  BIOLOGICAL_PROCESS: 5,
  SIGNALING_PATHWAY:  5,
  ENZYME:          3,
};
const DEFAULT_MIN_LENGTH = 3;

// Blue group: biological / molecular
const BIO_TYPES = new Set([
  "GENE", "PROTEIN", "RNA", "DISEASE", "CHEMICAL", "DRUG", "COMPOUND",
  "CELL_LINE", "ORGANISM", "ANATOMY", "BIOLOGICAL_PROCESS", "ENZYME",
  "SIGNALING_PATHWAY", "VIRUS", "ELEMENT",
]);

const ENTITY_LABELS: Record<string, string> = {
  GENE: "gene", PROTEIN: "protein", DISEASE: "disease",
  CHEMICAL: "chem", DRUG: "drug", COMPOUND: "compound",
  RNA: "rna", CELL_LINE: "cell line", ORGANISM: "organism",
  ANATOMY: "anatomy", BIOLOGICAL_PROCESS: "process", ENZYME: "enzyme",
  SIGNALING_PATHWAY: "pathway", VIRUS: "virus", ELEMENT: "element",
  METHOD: "method", TECHNOLOGY: "tech", SOFTWARE: "software",
  TECHNIQUE: "technique", TOOL: "tool", TRIAL: "trial",
};

// Show inline label for specific informative types
const SHOW_LABEL = new Set([
  "GENE", "PROTEIN", "DISEASE", "DRUG", "CHEMICAL", "RNA",
  "ENZYME", "BIOLOGICAL_PROCESS", "SIGNALING_PATHWAY", "VIRUS", "CELL_LINE",
]);

// Build a word-boundary-aware pattern for a single entity string
function buildEntityPattern(entity: string): string {
  const escaped = entity.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // \b only covers ASCII word chars — use lookahead/lookbehind for non-ASCII boundaries
  const startBound = /^[a-zA-Z0-9]/.test(entity) ? "\\b" : "(?<![a-zA-Z0-9])";
  const endBound   = /[a-zA-Z0-9]$/.test(entity)  ? "\\b" : "(?![a-zA-Z0-9])";
  return `${startBound}${escaped}${endBound}`;
}

function EntityChip({ entity, text }: { entity: HighlightEntity; text: string }) {
  const isBio = BIO_TYPES.has(entity.type);
  const label = ENTITY_LABELS[entity.type] ?? entity.type.toLowerCase();
  const showLabel = SHOW_LABEL.has(entity.type);

  return (
    <span
      className={`inline-flex items-baseline gap-0.5 px-1 py-0.5 rounded text-[13px] font-medium cursor-help ${
        isBio
          ? "bg-blue-50 text-blue-800"
          : "bg-slate-100 text-slate-700"
      }`}
      title={`${label}${entity.id ? ` · ${entity.id}` : ""}${entity.ontology ? ` (${entity.ontology})` : ""}`}
    >
      {text}
      {showLabel && (
        <span className="text-[9px] font-normal opacity-50 ml-0.5">
          {label}
        </span>
      )}
    </span>
  );
}

type TextPart =
  | { kind: "text"; content: string }
  | { kind: "citation"; id: number }
  | { kind: "entity"; entity: HighlightEntity; matched: string };

function buildParts(answer: string, entityMap: Map<string, HighlightEntity>): TextPart[] {
  if (entityMap.size === 0) {
    return answer.split(/(\[\d+\])/g).map(seg => {
      const m = seg.match(/^\[(\d+)\]$/);
      return m ? { kind: "citation", id: parseInt(m[1], 10) } : { kind: "text", content: seg };
    });
  }

  const sorted = [...entityMap.keys()].sort((a, b) => b.length - a.length);
  const patterns = sorted.map(buildEntityPattern);
  const combined = new RegExp(`(\\[\\d+\\]|${patterns.join("|")})`, "gi");

  const parts: TextPart[] = [];
  let last = 0;

  for (const match of answer.matchAll(combined)) {
    if (match.index! > last) {
      parts.push({ kind: "text", content: answer.slice(last, match.index) });
    }
    const raw = match[0];
    const citMatch = raw.match(/^\[(\d+)\]$/);
    if (citMatch) {
      parts.push({ kind: "citation", id: parseInt(citMatch[1], 10) });
    } else {
      const entity = entityMap.get(raw.toLowerCase());
      if (entity) {
        parts.push({ kind: "entity", entity, matched: raw });
      } else {
        parts.push({ kind: "text", content: raw });
      }
    }
    last = match.index! + raw.length;
  }
  if (last < answer.length) {
    parts.push({ kind: "text", content: answer.slice(last) });
  }
  return parts;
}

export default function AnswerView({ response, onCitationClick }: Props) {
  const entityMap = useMemo(() => {
    const map = new Map<string, HighlightEntity>();
    for (const source of response.sources) {
      for (const ent of source.entities ?? []) {
        if (SKIP_TYPES.has(ent.type)) continue;
        const minLen = MIN_LENGTH[ent.type] ?? DEFAULT_MIN_LENGTH;
        if (ent.text.length < minLen) continue;
        const key = ent.text.toLowerCase();
        if (!map.has(key) || (ent.id && !map.get(key)!.id)) {
          map.set(key, ent);
        }
      }
    }
    return map;
  }, [response.sources]);

  const parts = useMemo(
    () => buildParts(response.answer, entityMap),
    [response.answer, entityMap]
  );

  const entityCount = entityMap.size;

  return (
    <div className="max-w-none">
      {entityCount > 0 && (
        <p className="text-[11px] text-slate-400 mb-3">
          {entityCount} linked entities — hover any highlighted term for ontology detail
        </p>
      )}

      <div className="text-[15px] text-slate-700 leading-[1.75] whitespace-pre-line">
        {parts.map((part, i) => {
          if (part.kind === "citation") {
            return (
              <button
                key={i}
                onClick={() => onCitationClick(part.id)}
                className="inline-flex items-center justify-center min-w-[1.25rem] h-[1.25rem] px-1 mx-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-600 hover:bg-blue-100 hover:text-blue-700 transition-colors cursor-pointer align-super leading-none"
                title={`View source ${part.id}`}
              >
                {part.id}
              </button>
            );
          }
          if (part.kind === "entity") {
            return <EntityChip key={i} entity={part.entity} text={part.matched} />;
          }
          return <span key={i}>{part.content}</span>;
        })}
      </div>
    </div>
  );
}
