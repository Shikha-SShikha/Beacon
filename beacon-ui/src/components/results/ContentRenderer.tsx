/**
 * Parses enriched chunk text and renders it appropriately.
 *
 * Chunk text format (from entity_enriched ChromaDB collection):
 *   [ENTITY: text | id] [ENTITY: text] ...   ← entity prefix (stripped here; shown via EntityTags)
 *
 *   Table N: <AI summary paragraph>           ← for table chunks
 *   Caption: <original caption>
 *   | col | col | ...                         ← markdown table rows
 *   | --- | --- | ...
 *   | val | val | ...
 *
 *   Fig N: <AI summary paragraph>             ← for figure chunks
 *   Caption: <original caption>
 *
 *   <plain paragraph text>                    ← for text chunks
 */

interface TableData {
  headers: string[];
  rows: string[][];
}

interface Parsed {
  kind: "text" | "table" | "figure";
  label: string | null;      // "Table 1", "Figure 2", etc.
  summary: string;
  caption: string | null;
  tableData: TableData | null;
}

// ─── Parser ──────────────────────────────────────────────────────────────────

function stripEntityPrefix(raw: string): string {
  // Entity prefix is one or more lines of [TYPE: text | id] tokens.
  // It always comes before the first blank line.
  const parts = raw.split(/\n\n+/);
  if (parts.length <= 1) return raw.trim();
  // If the first paragraph is all entity tags, skip it.
  const isEntityLine = /^(\[[\w_]+:\s*.+?\]\s*)+$/.test(parts[0].replace(/\n/g, " ").trim());
  return isEntityLine ? parts.slice(1).join("\n\n").trim() : raw.trim();
}

function parseMarkdownTable(text: string): TableData | null {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("|"));

  if (lines.length < 3) return null;

  const parseRow = (line: string): string[] =>
    line.split("|").slice(1, -1).map((c) => c.trim());

  // Find the separator row (contains only dashes/colons/spaces)
  const sepIdx = lines.findIndex((l) => /^\|[\s\-:|]+\|$/.test(l));
  if (sepIdx < 1) return null;

  const headers = parseRow(lines[sepIdx - 1]);
  const rows = lines
    .slice(sepIdx + 1)
    .map(parseRow)
    .filter((r) => r.some((c) => c.length > 0));

  return { headers, rows };
}

function parse(raw: string, chunkType: string): Parsed {
  const text = stripEntityPrefix(raw);

  // Detect label — "Table 1:", "Fig. 2:", "Figure 3:"
  const labelMatch = text.match(/^((?:Table|Fig(?:ure)?\.?)\s*\d+):\s*/i);
  const label = labelMatch ? labelMatch[1] : null;
  const afterLabel = labelMatch ? text.slice(labelMatch[0].length) : text;

  // Split caption
  const captionMatch = afterLabel.match(/\n\nCaption:\s*([\s\S]*?)(?:\n\n|$)/);
  const caption = captionMatch ? captionMatch[1].trim() : null;

  // Everything before the caption (or before the table) is the summary
  const summaryEnd = captionMatch ? captionMatch.index! : afterLabel.search(/\n\n\|/);
  const summary = summaryEnd > 0
    ? afterLabel.slice(0, summaryEnd).trim()
    : afterLabel.split("\n\n")[0].trim();

  // Extract markdown table
  const tableData = parseMarkdownTable(afterLabel);

  // Infer kind
  const kind =
    chunkType === "table" || tableData !== null
      ? "table"
      : chunkType === "figure" || /^Fig/i.test(label ?? "")
      ? "figure"
      : "text";

  return { kind, label, summary, caption, tableData };
}

// ─── Renderers ───────────────────────────────────────────────────────────────

interface Props {
  text: string;
  chunkType: string;
  maxChars?: number;
}

export default function ContentRenderer({ text, chunkType, maxChars = 900 }: Props) {
  const parsed = parse(text, chunkType);

  if (parsed.kind === "table") {
    return <TableContent parsed={parsed} />;
  }
  if (parsed.kind === "figure") {
    return <FigureContent parsed={parsed} />;
  }
  // Plain text
  const body = parsed.summary || text.slice(0, maxChars);
  return (
    <p className="text-sm text-slate-700 leading-relaxed">
      {body.slice(0, maxChars)}{body.length > maxChars ? "…" : ""}
    </p>
  );
}

// ─── Table ───────────────────────────────────────────────────────────────────

function TableContent({ parsed }: { parsed: Parsed }) {
  return (
    <div className="space-y-3">
      {/* Label + summary */}
      <div className="flex items-start gap-2">
        {parsed.label && (
          <span className="shrink-0 mt-0.5 text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200 uppercase tracking-wide">
            {parsed.label}
          </span>
        )}
        {parsed.summary && (
          <p className="text-xs text-slate-600 leading-relaxed">{parsed.summary}</p>
        )}
      </div>

      {/* Caption */}
      {parsed.caption && (
        <p className="text-[11px] text-slate-400 italic leading-snug border-l-2 border-slate-200 pl-3">
          {parsed.caption}
        </p>
      )}

      {/* Table */}
      {parsed.tableData && (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-slate-700 text-white">
                {parsed.tableData.headers.map((h, i) => (
                  <th
                    key={i}
                    className="px-3 py-2 text-left font-semibold whitespace-nowrap border-r border-slate-600 last:border-r-0"
                  >
                    {h || "—"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parsed.tableData.rows.map((row, ri) => (
                <tr
                  key={ri}
                  className={ri % 2 === 0 ? "bg-white" : "bg-slate-50"}
                >
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="px-3 py-2 text-slate-700 border-r border-t border-slate-100 last:border-r-0 leading-snug"
                    >
                      {cell || <span className="text-slate-300">—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Figure ──────────────────────────────────────────────────────────────────

function FigureContent({ parsed }: { parsed: Parsed }) {
  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2">
        {parsed.label && (
          <span className="shrink-0 mt-0.5 text-[10px] font-semibold px-2 py-0.5 rounded bg-violet-50 text-violet-600 border border-violet-200 uppercase tracking-wide">
            {parsed.label}
          </span>
        )}
        {parsed.summary && (
          <p className="text-xs text-slate-600 leading-relaxed">{parsed.summary}</p>
        )}
      </div>
      {parsed.caption && (
        <p className="text-[11px] text-slate-400 italic leading-snug border-l-2 border-slate-200 pl-3">
          {parsed.caption}
        </p>
      )}
    </div>
  );
}
