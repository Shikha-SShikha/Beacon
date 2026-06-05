import { useState } from "react";
import BeaconLogo from "../components/ui/BeaconLogo";

// ── Types ─────────────────────────────────────────────────────────────────

type FlagType =
  | "wrong-category"
  | "no-database-match"
  | "database-mismatch"
  | "inconsistent"
  | "unusual-placement"
  | "needs-second-look";

type ReviewStatus = "pending" | "approved" | "changed" | "removed";

interface FlaggedEntity {
  id: string;
  articleId: string;
  text: string;
  assignedType: string;
  suggestedType?: string;
  flag: FlagType;
  section: string;
  occurrences: number;
  context: string;
  flagDetail: string;
  status: ReviewStatus;
  // After rule-based checks, entity is sent to LLM.
  // "cleared" = LLM approved it → auto-approved, never reaches human review.
  // "confirmed" = LLM agreed it's wrong → goes to human review queue.
  llmVerdict?: "confirmed" | "cleared";
  llmReason?: string;
}

// Each check maps to one or more flag types that represent its failure mode
interface CheckDef {
  id: string;
  step: string;
  name: string;
  description: string;
  whatItCatches: string;
  failureMode: string;
  flags: FlagType[];
  autoReject?: boolean; // true = entities removed, not sent for review
}

// ── Check definitions ─────────────────────────────────────────────────────

const CHECKS: CheckDef[] = [
  {
    id: "noise",
    step: "01",
    name: "Noise filter",
    description: "Remove words that are not real scientific terms",
    whatItCatches: "Single letters, reagent supplier names (BioRad, Invitrogen), and everyday words like 'cells', 'genes', or 'data' that appear in every paper but don't mean anything specific",
    failureMode: "The word is too short, too common, or a brand name — not a meaningful scientific term worth tagging",
    flags: [],
    autoReject: true,
  },
  {
    id: "category",
    step: "02",
    name: "Category check",
    description: "Make sure each term is filed under the right type",
    whatItCatches: "Terms put in the wrong box — for example, ferroptosis (a cell death process) filed under Disease, or an instrument filed under Cell Line",
    failureMode: "The category assigned doesn't match what scientific reference databases say this term actually is",
    flags: ["wrong-category"],
  },
  {
    id: "database",
    step: "03",
    name: "Database match",
    description: "Confirm the term exists in a scientific reference database and the match makes sense",
    whatItCatches: "Terms that can't be found in any database at all, or where the database entry found describes something completely different from what was tagged",
    failureMode: "No match found, or the closest match is clearly a different thing — suggesting the term may have been tagged in error",
    flags: ["no-database-match", "database-mismatch"],
  },
  {
    id: "consistency",
    step: "04",
    name: "Consistency check",
    description: "Check that the same term is labelled the same way throughout the whole article",
    whatItCatches: "The same word given two different labels in different parts of the paper — for example, GPX4 called a Gene in the introduction but a Protein in the results",
    failureMode: "The same word has two different labels within the same article, which means one of them is wrong",
    flags: ["inconsistent"],
  },
  {
    id: "placement",
    step: "05",
    name: "Placement check",
    description: "Flag terms that appear in an unusual section of the paper",
    whatItCatches: "A drug name appearing only in the introduction with no clinical discussion, or a disease term isolated entirely within a methods section",
    failureMode: "This type of term almost never appears in this section — its presence here is unexpected and worth a second look",
    flags: ["unusual-placement"],
  },
  {
    id: "ai-review",
    step: "06",
    name: "AI second opinion",
    description: "A second independent AI reads each flagged term in context and checks whether it agrees",
    whatItCatches: "Subtle mistakes the rule-based checks above can miss — like a biological process mislabelled as a chemical, or an abbreviation that means different things in different contexts",
    failureMode: "The second AI reviewer disagrees with how the term was originally labelled, even after reading the surrounding sentence",
    flags: ["needs-second-look"],
  },
];

// ── Mock data ─────────────────────────────────────────────────────────────

interface NoiseEntry { term: string; reason: string; }

const ARTICLES = [
  {
    id: "BJ_100828", title: "Epitranscriptomic hallmarks at the host-parasite interface in Theileria annulata",
    journal: "BJ", total: 89, approved: 74, flagged: 3, removed: 12,
    noiseRemoved: [
      { term: "V",          reason: "Single letter — not an entity" },
      { term: "RNA",        reason: "Generic biological term" },
      { term: "cells",      reason: "Too generic" },
      { term: "data",       reason: "Too generic" },
      { term: "BioRad",     reason: "Lab equipment brand — not a scientific entity" },
      { term: "Life Technologies", reason: "Reagent supplier name" },
      { term: "et al.",     reason: "Citation artefact" },
      { term: "Fig",        reason: "Figure reference, not an entity" },
      { term: "Table",      reason: "Table reference, not an entity" },
      { term: "A",          reason: "Single letter — not an entity" },
      { term: "protein",    reason: "Too generic — not a named protein" },
      { term: "h",          reason: "Unit abbreviation" },
    ] as NoiseEntry[],
  },
  {
    id: "S2468294225000504", title: "Ferroptosis as a therapeutic target in cancer: mechanisms and drug resistance",
    journal: "CTARC", total: 67, approved: 57, flagged: 2, removed: 8,
    noiseRemoved: [
      { term: "cancer cells",  reason: "Too generic — not a named entity" },
      { term: "mRNA",          reason: "Generic molecular term" },
      { term: "Sigma-Aldrich", reason: "Reagent supplier name" },
      { term: "in vitro",      reason: "Experimental descriptor, not an entity" },
      { term: "genes",         reason: "Too generic" },
      { term: "Fig. 2",        reason: "Figure reference" },
      { term: "i.e.",          reason: "Punctuation artefact" },
      { term: "μM",            reason: "Unit — not an entity" },
    ] as NoiseEntry[],
  },
  {
    id: "REDOX-104085", title: "Redox regulation of ferroptosis and lipid peroxidation in tumour cells",
    journal: "REDOX", total: 54, approved: 47, flagged: 2, removed: 5,
    noiseRemoved: [
      { term: "cells",       reason: "Too generic" },
      { term: "pathway",     reason: "Generic descriptor" },
      { term: "Abcam",       reason: "Antibody supplier name" },
      { term: "nM",          reason: "Unit — not an entity" },
      { term: "Western",     reason: "Incomplete term — 'Western blot' was captured separately" },
    ] as NoiseEntry[],
  },
  {
    id: "S3050538025000432", title: "GPX4 inhibition and ferroptosis sensitisation in gastric cancer therapy",
    journal: "CTARC", total: 72, approved: 63, flagged: 1, removed: 8,
    noiseRemoved: [
      { term: "tumor",       reason: "Too generic — no specific cancer named" },
      { term: "H",           reason: "Single letter — not an entity" },
      { term: "Invitrogen",  reason: "Reagent supplier name" },
      { term: "Fig. 3A",     reason: "Figure reference" },
      { term: "assay",       reason: "Generic method descriptor" },
      { term: "pellet",      reason: "Lab procedure descriptor" },
      { term: "media",       reason: "Too generic" },
      { term: "μL",          reason: "Unit — not an entity" },
    ] as NoiseEntry[],
  },
];


const MOCK_FLAGGED: FlaggedEntity[] = [
  // BJ_100828 — 4 rule-based flags → LLM clears 1 → 3 reach human
  { id:"e1",  articleId:"BJ_100828",         text:"apoptosis",             assignedType:"DISEASE",       suggestedType:"BIOLOGICAL_PROCESS", flag:"wrong-category",    section:"Introduction",               occurrences:3,  context:"…evasion from apoptotic mechanisms, and increased dissemination…",                            flagDetail:"Resolved to MeSH D017209 — classified under Biological Processes, not Diseases.",                                               llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e2",  articleId:"BJ_100828",         text:"METTL3",                assignedType:"GENE / PROTEIN",                                      flag:"inconsistent",      section:"Introduction · Methods",     occurrences:7,  context:"…METTL3 is the catalytic core, while METTL14 provides structural support…",                   flagDetail:"Tagged as PROTEIN in chunks 4 & 5, but as GENE in chunks 7 & 9. Same article, two different categories.",                       llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e3",  articleId:"BJ_100828",         text:"PureLink RNA Mini Kit", assignedType:"DRUG",                                                flag:"database-mismatch", section:"Methods",                    occurrences:1,  context:"…RNA was extracted using the PureLink RNA Mini Kit (Life Technologies)…",                     flagDetail:"Resolved to CHEBI:18273 — that entry is 'adenine'. The kit name and database label have near-zero similarity.",                 llmVerdict:"cleared",  llmReason:"This is a commercial extraction kit. Database mismatch is expected as kits are not indexed in ChEBI. Tagging as METHOD is acceptable.",  status:"approved" },
  { id:"e4",  articleId:"BJ_100828",         text:"Nucleofector",          assignedType:"CELL_LINE",     suggestedType:"EQUIPMENT",            flag:"wrong-category",    section:"Methods",                    occurrences:2,  context:"…macrophages underwent electroporation using the Nucleofector system…",                        flagDetail:"No cell line named Nucleofector in Cellosaurus. It is an electroporation device.",                                               llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  // S2468294225000504 — 3 rule-based flags → LLM clears 1 → 2 reach human
  { id:"e5",  articleId:"S2468294225000504", text:"ferroptosis",           assignedType:"DISEASE",       suggestedType:"BIOLOGICAL_PROCESS",   flag:"wrong-category",    section:"Introduction · Results",     occurrences:9,  context:"…ferroptosis is an iron-dependent form of regulated cell death driven by lipid peroxidation…", flagDetail:"Resolved to MeSH D000078129 — classified under 'Cell Death' (biological process), not a disease.",                             llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e6",  articleId:"S2468294225000504", text:"lipid peroxidation",    assignedType:"CHEMICAL",      suggestedType:"BIOLOGICAL_PROCESS",   flag:"wrong-category",    section:"Introduction · Results · Discussion", occurrences:6, context:"…accumulation of lipid peroxidation products leads to membrane rupture and cell death…",      flagDetail:"This is an oxidative process, not a compound. No chemical database matches — biological process ontologies do.",                llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e7",  articleId:"S2468294225000504", text:"RSL3",                  assignedType:"DRUG",                                                flag:"unusual-placement", section:"Introduction",               occurrences:1,  context:"…RSL3, a GPX4 inhibitor, is widely used to induce ferroptosis in research models…",           flagDetail:"DRUG entities almost never appear in Introduction sections without a clinical context.",                                         llmVerdict:"cleared",  llmReason:"RSL3 is a standard research tool routinely introduced in background sections. Its placement here is standard scientific writing, not an error.", status:"approved" },
  // REDOX-104085 — 2 rule-based flags → LLM confirms both → 2 reach human
  { id:"e8",  articleId:"REDOX-104085",      text:"m6A RNA methylation",   assignedType:"CHEMICAL",      suggestedType:"BIOLOGICAL_PROCESS",   flag:"needs-second-look", section:"Results",                    occurrences:4,  context:"…m6A RNA methylation regulates translation efficiency under hypoxic conditions…",             flagDetail:"'This refers to a modification process, not a compound. Suggested category: Biological Process.'",                              llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e9",  articleId:"REDOX-104085",      text:"T. annulata infections",assignedType:"DISEASE",                                             flag:"no-database-match", section:"Introduction",               occurrences:2,  context:"…the role of m6A modifications in T. annulata infections remains unexplored…",                flagDetail:"Neither MeSH nor Disease Ontology returned a match for 'T. annulata infections'.",                                               llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  // S3050538025000432 — 2 rule-based flags → LLM clears 1 → 1 reaches human
  { id:"e10", articleId:"S3050538025000432", text:"GPX4",                  assignedType:"GENE / PROTEIN",                                      flag:"inconsistent",      section:"Introduction · Results · Discussion", occurrences:11, context:"…GPX4 is the primary defence enzyme against lipid peroxidation-induced ferroptosis…",     flagDetail:"Tagged as GENE in introduction and discussion, but PROTEIN in results. Three instances conflict.",                               llmVerdict:"confirmed",                                                                                                                         status:"pending" },
  { id:"e11", articleId:"S3050538025000432", text:"Liproxstatin-1",        assignedType:"DRUG",          suggestedType:"CHEMICAL",             flag:"wrong-category",    section:"Methods · Results",          occurrences:3,  context:"…cells were treated with Liproxstatin-1 to inhibit ferroptosis-induced lipid peroxidation…",  flagDetail:"Resolved to CHEBI:138488 — ChEBI classifies this as a chemical inhibitor. No clinical approval on record.",                    llmVerdict:"cleared",  llmReason:"In research literature Liproxstatin-1 is consistently described as a drug/inhibitor. The DRUG category is an acceptable research-use label.", status:"approved" },
];

// ── Sub-components ─────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ReviewStatus }) {
  const styles: Record<ReviewStatus, string> = {
    pending:  "text-slate-400  bg-slate-50  border-slate-200",
    approved: "text-emerald-700 bg-emerald-50 border-emerald-200",
    changed:  "text-blue-700   bg-blue-50   border-blue-200",
    removed:  "text-red-600    bg-red-50    border-red-200",
  };
  const labels: Record<ReviewStatus, string> = {
    pending:"Pending", approved:"Approved", changed:"Type changed", removed:"Removed",
  };
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${styles[status]}`}>{labels[status]}</span>;
}

// ── Check scorecard row ───────────────────────────────────────────────────

function CheckRow({
  check, passed, failed, autoRemovedCount, isSelected, onClick,
}: {
  check: CheckDef;
  passed: number;
  failed: number;
  autoRemovedCount?: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isNoise = check.autoReject;
  const total = isNoise ? (autoRemovedCount ?? 0) : passed + failed;
  const pct = total > 0 ? Math.round((passed / total) * 100) : 100;

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border px-4 py-3 transition-all flex items-center gap-4 cursor-pointer ${
        isSelected
          ? "border-slate-800 bg-white shadow-sm"
          : isNoise
          ? "border-slate-200 bg-slate-50 hover:border-slate-300"
          : failed > 0
          ? "border-amber-200 bg-white hover:border-amber-300"
          : "border-emerald-100 bg-white hover:border-emerald-200"
      }`}
    >
      <span className={`shrink-0 text-[10px] font-bold w-6 h-6 rounded-full flex items-center justify-center border ${
        isNoise ? "bg-slate-100 border-slate-200 text-slate-400"
        : failed > 0 ? "bg-amber-100 border-amber-200 text-amber-700"
        : "bg-emerald-100 border-emerald-200 text-emerald-700"
      }`}>{check.step}</span>

      <span className="text-[13px] font-semibold text-slate-800 flex-1">{check.name}</span>

      {!isNoise && (
        <div className="w-28 shrink-0">
          <div className="flex rounded-full overflow-hidden h-1 bg-slate-100">
            <div className="bg-emerald-400 h-full transition-all" style={{ width: `${pct}%` }} />
            {failed > 0 && <div className="bg-amber-400 h-full transition-all" style={{ width: `${100 - pct}%` }} />}
          </div>
        </div>
      )}

      <div className="shrink-0 text-right w-24">
        {isNoise ? (
          <span className="text-[11px] text-slate-400">{autoRemovedCount} removed</span>
        ) : failed > 0 ? (
          <span className="text-[11px] font-semibold text-amber-600">{failed} failed · <span className="text-slate-400 font-normal">{passed} passed</span></span>
        ) : (
          <span className="text-[11px] font-semibold text-emerald-600">all passed ✓</span>
        )}
      </div>
    </div>
  );
}


// ── Main page ──────────────────────────────────────────────────────────────

export default function EvalsPage() {
  const [activeArticleId, setActiveArticleId] = useState(ARTICLES[0].id);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);

  const article = ARTICLES.find(a => a.id === activeArticleId)!;
  const articleEntities = MOCK_FLAGGED.filter(e => e.articleId === activeArticleId);


  return (
    <div className="min-h-screen bg-slate-50">

      {/* Top nav */}
      <header className="bg-white border-b border-slate-200/60 px-10 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <BeaconLogo size="sm" />
          <span className="text-slate-200">/</span>
          <span className="text-[14px] font-semibold text-slate-700">Entity Evals</span>
          <span className="text-[11px] text-slate-400 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded font-medium ml-1">Concept</span>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-10 py-8 space-y-8">

        {/* Article selector — dropdown */}
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
          <div className="flex items-center gap-4">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider shrink-0">Article</label>
            <select
              value={activeArticleId}
              onChange={e => { setActiveArticleId(e.target.value); setSelectedCheckId(null); }}
              className="flex-1 text-[13px] font-medium text-slate-700 border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-slate-300"
            >
              {ARTICLES.map(a => {
                const toReview = MOCK_FLAGGED.filter(e => e.articleId === a.id && e.llmVerdict === "confirmed").length;
                return (
                  <option key={a.id} value={a.id}>
                    [{a.journal}] {a.title}{toReview > 0 ? ` — ${toReview} for review` : ""}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Progress bar for selected article */}
          <div className="mt-3">
            <div className="flex rounded-full overflow-hidden h-1.5 bg-slate-100">
              <div className="bg-emerald-400 h-full transition-all" style={{ width: `${Math.round((article.approved / article.total) * 100)}%` }} />
              <div className="bg-amber-400  h-full transition-all" style={{ width: `${Math.round((article.flagged  / article.total) * 100)}%` }} />
              <div className="bg-slate-200  h-full transition-all" style={{ width: `${Math.round((article.removed  / article.total) * 100)}%` }} />
            </div>
            <div className="flex gap-4 mt-1.5 text-[10px]">
              <span className="text-emerald-600">{article.approved} approved</span>
              <span className="text-amber-600">{article.flagged} to review</span>
              <span className="text-slate-400">{article.removed} auto-removed</span>
              <span className="text-slate-300">·</span>
              <span className="text-slate-400">{article.total} total entities</span>
            </div>
          </div>
        </div>

        {/* ── Checks — accordion ── */}
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-3">Checks</p>

          <div className="flex flex-col gap-1.5">
            {CHECKS.map(check => {
              const eligible = article.total - article.removed;
              let passedCount = 0, failedCount = 0;
              if (check.autoReject) {
                // handled in detail panel
              } else if (check.id === "ai-review") {
                failedCount = articleEntities.filter(e => e.llmVerdict === "confirmed").length;
                passedCount = articleEntities.filter(e => e.llmVerdict === "cleared").length;
              } else {
                failedCount = articleEntities.filter(e => check.flags.includes(e.flag)).length;
                passedCount = eligible - failedCount;
              }

              const isOpen = selectedCheckId === check.id;

              // Entities for this check's table
              const checkEntities = (() => {
                if (check.id === "ai-review") return articleEntities.filter(e => e.llmVerdict === "cleared");
                if (check.autoReject) return [];
                return articleEntities.filter(e => check.flags.includes(e.flag));
              })();

              const flagLabels: Record<FlagType, string> = {
                "wrong-category":"Wrong category","no-database-match":"Couldn't verify",
                "database-mismatch":"Database doesn't match","inconsistent":"Tagged differently",
                "unusual-placement":"Unusual placement","needs-second-look":"Needs second look",
              };

              return (
                <div key={check.id}>
                  <CheckRow
                    check={check}
                    passed={passedCount}
                    failed={failedCount}
                    autoRemovedCount={check.autoReject ? article.removed : undefined}
                    isSelected={isOpen}
                    onClick={() => setSelectedCheckId(isOpen ? null : check.id)}
                  />

                  {isOpen && (
                    <div className="ml-9 mt-1 rounded-b-lg border border-t-0 border-slate-200 bg-white px-5 py-4 space-y-4">

                      {/* What it catches + failure mode */}
                      <div className="grid grid-cols-2 gap-6">
                        <div>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">What this check catches</p>
                          <p className="text-[12px] text-slate-600 leading-relaxed">{check.whatItCatches}</p>
                        </div>
                        <div>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Failure mode</p>
                          <p className="text-[12px] text-slate-600 leading-relaxed">{check.failureMode}</p>
                        </div>
                      </div>

                      {/* Noise: list of removed terms */}
                      {check.autoReject && (
                        <>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Removed from this article</p>
                          <div className="grid grid-cols-3 gap-1.5">
                            {article.noiseRemoved.map((n, i) => (
                              <div key={i} className="flex items-start gap-2 rounded-md bg-slate-50 border border-slate-100 px-3 py-2">
                                <span className="text-[12px] font-semibold text-slate-700 shrink-0">{n.term}</span>
                                <span className="text-[11px] text-slate-400 leading-snug">{n.reason}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}

                      {/* AI-review: cleared entities with reasons */}
                      {check.id === "ai-review" && checkEntities.length > 0 && (
                        <>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Cleared by AI — auto-approved, not sent to human</p>
                          <div className="rounded-lg border border-slate-100 overflow-hidden">
                            <table className="w-full">
                              <thead><tr className="border-b border-slate-100 bg-slate-50">
                                {["Entity","Flagged by","Reason"].map(h => <th key={h} className="text-left px-4 py-2.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{h}</th>)}
                              </tr></thead>
                              <tbody className="divide-y divide-slate-100">
                                {checkEntities.map(e => (
                                  <tr key={e.id}>
                                    <td className="px-4 py-3"><span className="text-[12px] font-semibold text-slate-700">{e.text}</span></td>
                                    <td className="px-4 py-3"><span className="text-[11px] text-slate-500">{flagLabels[e.flag]}</span></td>
                                    <td className="px-4 py-3"><span className="text-[11px] text-slate-500 italic">{e.llmReason}</span></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                      {check.id === "ai-review" && checkEntities.length === 0 && (
                        <p className="text-[12px] text-amber-600">All flagged entities confirmed for human review — none cleared.</p>
                      )}

                      {/* Rule-based checks: entity list with LLM verdict */}
                      {!check.autoReject && check.id !== "ai-review" && checkEntities.length > 0 && (
                        <>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Entities flagged by this check</p>
                          <div className="rounded-lg border border-slate-100 overflow-hidden">
                            <table className="w-full">
                              <thead><tr className="border-b border-slate-100 bg-slate-50">
                                {["Entity","Assigned type","Section","AI verdict"].map(h => <th key={h} className="text-left px-4 py-2.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{h}</th>)}
                              </tr></thead>
                              <tbody className="divide-y divide-slate-100">
                                {checkEntities.map(e => (
                                  <tr key={e.id} className={e.llmVerdict === "cleared" ? "opacity-50" : ""}>
                                    <td className="px-4 py-3">
                                      <span className="text-[12px] font-semibold text-slate-800">{e.text}</span>
                                      <span className="ml-1.5 text-[10px] text-slate-400">{e.occurrences}×</span>
                                    </td>
                                    <td className="px-4 py-3"><span className="text-[11px] text-slate-600 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">{e.assignedType}</span></td>
                                    <td className="px-4 py-3"><span className="text-[11px] text-slate-500">{e.section}</span></td>
                                    <td className="px-4 py-3">
                                      {e.llmVerdict === "confirmed"
                                        ? <span className="text-[11px] font-semibold text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">Confirmed → human</span>
                                        : <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">Cleared ✓</span>
                                      }
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                      {!check.autoReject && check.id !== "ai-review" && checkEntities.length === 0 && (
                        <p className="text-[12px] text-emerald-600">All entities passed this check ✓</p>
                      )}

                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Human review queue (always visible at bottom) ── */}
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Human review queue</p>
          <p className="text-[11px] text-slate-400 mb-3">Only entities confirmed by AI review reach this queue</p>
          {(() => {
            const queue = articleEntities.filter(e => e.llmVerdict === "confirmed");
            if (queue.length === 0) return <p className="text-[12px] text-emerald-600">No entities require human review ✓</p>;
            return (
              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                <table className="w-full">
                  <thead><tr className="border-b border-slate-100 bg-slate-50">
                    {["Entity","Assigned type","Flagged by","Section","Status"].map(h => <th key={h} className="text-left px-5 py-3 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{h}</th>)}
                  </tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {queue.map(e => {
                      const flagColors: Record<FlagType, string> = {
                        "wrong-category":    "text-red-700 bg-red-50 border-red-200",
                        "no-database-match": "text-amber-700 bg-amber-50 border-amber-200",
                        "database-mismatch": "text-orange-700 bg-orange-50 border-orange-200",
                        "inconsistent":      "text-purple-700 bg-purple-50 border-purple-200",
                        "unusual-placement": "text-slate-600 bg-slate-50 border-slate-200",
                        "needs-second-look": "text-blue-700 bg-blue-50 border-blue-200",
                      };
                      const flagLabels: Record<FlagType, string> = {
                        "wrong-category":"Wrong category","no-database-match":"Couldn't verify",
                        "database-mismatch":"Database doesn't match","inconsistent":"Tagged differently",
                        "unusual-placement":"Unusual placement","needs-second-look":"Needs second look",
                      };
                      return (
                        <tr key={e.id}>
                          <td className="px-5 py-3.5"><span className="text-[13px] font-semibold text-slate-800">{e.text}</span><span className="ml-2 text-[10px] text-slate-400">{e.occurrences}×</span></td>
                          <td className="px-5 py-3.5"><span className="text-[11px] text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">{e.assignedType}</span></td>
                          <td className="px-5 py-3.5"><span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${flagColors[e.flag]}`}>{flagLabels[e.flag]}</span></td>
                          <td className="px-5 py-3.5"><span className="text-[11px] text-slate-500">{e.section}</span></td>
                          <td className="px-5 py-3.5"><StatusBadge status={e.status} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>


      </div>
    </div>
  );
}
