import type { Entity } from "../../types";

const TYPE_COLORS: Record<string, { badge: string; dot: string }> = {
  GENE:        { badge: "bg-violet-50 text-violet-700 border-violet-200",  dot: "bg-violet-400" },
  PROTEIN:     { badge: "bg-violet-50 text-violet-700 border-violet-200",  dot: "bg-violet-400" },
  DISEASE:     { badge: "bg-rose-50 text-rose-700 border-rose-200",        dot: "bg-rose-400"   },
  CHEMICAL:    { badge: "bg-teal-50 text-teal-700 border-teal-200",        dot: "bg-teal-400"   },
  DRUG:        { badge: "bg-teal-50 text-teal-700 border-teal-200",        dot: "bg-teal-400"   },
  CELL_LINE:   { badge: "bg-orange-50 text-orange-700 border-orange-200",  dot: "bg-orange-400" },
  ORGANISM:    { badge: "bg-lime-50 text-lime-700 border-lime-200",        dot: "bg-lime-500"   },
  METHOD:      { badge: "bg-slate-100 text-slate-600 border-slate-200",    dot: "bg-slate-400"  },
  TECHNOLOGY:  { badge: "bg-slate-100 text-slate-600 border-slate-200",    dot: "bg-slate-400"  },
  CONCEPT:     { badge: "bg-blue-50 text-blue-600 border-blue-200",        dot: "bg-blue-400"   },
};

const DEFAULT_COLORS = { badge: "bg-slate-100 text-slate-600 border-slate-200", dot: "bg-slate-400" };

function formatId(e: Entity): string | null {
  if (!e.id) return null;
  if (e.ontology) return `${e.ontology} · ${e.id}`;
  return e.id;
}

export default function EntityTags({ raw }: { raw: string }) {
  let entities: Entity[] = [];
  try {
    entities = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!entities.length) return null;

  // Group by type for the summary row
  const typeCounts = entities.reduce<Record<string, number>>((acc, e) => {
    acc[e.type] = (acc[e.type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mt-4 pt-4 border-t border-slate-100">

      {/* Header with type summary */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
          Named Entities
        </p>
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {Object.entries(typeCounts).map(([type, count]) => {
            const colors = TYPE_COLORS[type] ?? DEFAULT_COLORS;
            return (
              <span
                key={type}
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${colors.badge}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
                {type} {count > 1 && <span className="opacity-60">×{count}</span>}
              </span>
            );
          })}
        </div>
      </div>

      {/* Entity rows */}
      <div className="rounded-lg border border-slate-100 divide-y divide-slate-50 overflow-hidden">
        {entities.slice(0, 14).map((e, i) => {
          const colors = TYPE_COLORS[e.type] ?? DEFAULT_COLORS;
          const idStr = formatId(e);
          return (
            <div
              key={i}
              className="grid items-center gap-3 px-3 py-2 bg-white hover:bg-slate-50 transition-colors"
              style={{ gridTemplateColumns: "7rem 1fr auto" }}
            >
              {/* Type badge */}
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold w-fit ${colors.badge}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
                {e.type}
              </span>

              {/* Entity text */}
              <span className="text-xs text-slate-800 font-medium leading-snug">
                {e.text}
              </span>

              {/* Ontology ID */}
              {idStr ? (
                <span className="text-[10px] text-slate-400 font-mono leading-snug text-right whitespace-nowrap">
                  {idStr}
                </span>
              ) : (
                <span />
              )}
            </div>
          );
        })}
        {entities.length > 14 && (
          <div className="px-3 py-2 bg-slate-50 text-[10px] text-slate-400 text-center">
            +{entities.length - 14} more entities
          </div>
        )}
      </div>
    </div>
  );
}
