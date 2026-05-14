import { useMemo } from "react";
import type { AskResponse, HighlightEntity } from "../../types";

interface Props {
  response: AskResponse;
  onCitationClick: (citationId: number) => void;
}

// Two display groups — biological/molecular vs methodological/conceptual
const BIO_TYPES = new Set(["GENE", "PROTEIN", "RNA", "DISEASE", "CHEMICAL", "DRUG", "COMPOUND", "CELL_LINE", "ORGANISM"]);

const ENTITY_LABELS: Record<string, string> = {
  GENE: "gene", PROTEIN: "protein", DISEASE: "disease",
  CHEMICAL: "chem", DRUG: "drug", COMPOUND: "compound",
  RNA: "rna", CELL_LINE: "cell line", ORGANISM: "organism",
  METHOD: "method", TECHNOLOGY: "tech", SOFTWARE: "software",
  CONCEPT: "concept", ENTITY: "entity",
};

// Only show inline type label for the most informative types
const SHOW_LABEL = new Set(["GENE", "PROTEIN", "DISEASE", "DRUG", "CHEMICAL", "RNA"]);

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
  const escaped = sorted.map(e => e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const combined = new RegExp(`(\\[\\d+\\]|${escaped.join("|")})`, "gi");

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
