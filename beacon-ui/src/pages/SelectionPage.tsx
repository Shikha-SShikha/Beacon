import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { fetchInstitutions } from "../api/client";
import type { InstitutionSummary } from "../types";
import Spinner from "../components/ui/Spinner";

type AuthMode = "beacon" | "publisher";

const PUBLISHERS = [
  "Portland Press",
  "Elsevier",
  "Pleiades Publishing",
  "Wiley",
  "Springer Nature",
  "Other",
];

const INSTITUTION_MAP: [string, string][] = [
  ["edinburgh", "uni_edinburgh"],
  ["berlin", "tu_berlin"],
  ["technische", "tu_berlin"],
  ["global policy", "global_policy"],
];

function resolveInstitution(input: string): string {
  const lower = input.toLowerCase().trim();
  return INSTITUTION_MAP.find(([key]) => lower.includes(key))?.[1] ?? "guest";
}

interface Props {
  onSelect: (id: string) => void;
}

export default function SelectionPage({ onSelect }: Props) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("beacon");

  const [institutions, setInstitutions] = useState<InstitutionSummary[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [loadingInst, setLoadingInst] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [publisher, setPublisher] = useState<string>("");
  const [institution, setInstitution] = useState<string>("");
  const [userId, setUserId] = useState<string>("");

  useEffect(() => {
    fetchInstitutions()
      .then((data) => {
        setInstitutions(data);
        if (data.length) setSelected(data[0].id);
      })
      .catch(() => setFetchError("Could not load institutions."))
      .finally(() => setLoadingInst(false));
  }, []);

  function handleBeaconContinue() {
    if (!selected) return;
    onSelect(selected);
    navigate("/search");
  }

  function handlePublisherSignIn() {
    if (!publisher || !institution || !userId.trim()) return;
    const instId = resolveInstitution(institution);
    onSelect(instId);
    navigate("/search");
  }

  const publisherReady = publisher && institution && userId.trim();

  return (
    <div className="min-h-screen flex">

      {/* ─── Left brand panel ─────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[45%] relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900">
        {/* Subtle animated glow */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-blue-500/20 blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-indigo-500/15 blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Logo */}
          <img
            src="/beacon-logo.svg"
            alt="Beacon"
            className="h-20 object-left object-contain self-start select-none"
            style={{ filter: "brightness(0) invert(1)" }}
          />

          {/* Value proposition */}
          <div className="max-w-lg">
            <h1 className="font-display text-5xl text-white leading-[1.15] mb-5">
              Your articles, enriched<br />for the AI era.
            </h1>
            <p className="text-[18px] text-blue-100/70 leading-relaxed mb-14">
              Beacon transforms your content so when an AI searches, it actually finds what matters.
            </p>

            {/* Enrichment capabilities */}
            <div className="space-y-3.5">
              {[
                "Paragraph-level chunking",
                "Figure & table intelligence",
                "Hybrid retrieval",
                "Section-aware reranking",
                "Evidence-traced answers",
              ].map((label) => (
                <p key={label} className="text-[16px] font-medium text-white/75">{label}</p>
              ))}
            </div>
          </div>

          {/* Footer */}
          <p className="text-[11px] text-blue-200/30">
            AI Content Enrichment Gateway
          </p>
        </div>
      </div>

      {/* ─── Right form panel ─────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center bg-slate-50 px-6">
        <div className="w-full max-w-[400px]">

          {/* Mobile logo — only visible on small screens */}
          <div className="lg:hidden flex justify-start mb-10">
            <img
              src="/beacon-logo.svg"
              alt="Beacon"
              className="h-10 object-contain select-none"
            />
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl shadow-sm shadow-slate-200/50 border border-slate-200/60 overflow-hidden">

            {/* Mode tabs */}
            <div className="flex border-b border-slate-100">
              <ModeTab
                active={mode === "beacon"}
                onClick={() => setMode("beacon")}
                label="Beacon"
              />
              <ModeTab
                active={mode === "publisher"}
                onClick={() => setMode("publisher")}
                label="Publisher"
              />
            </div>

            {/* Form body */}
            <div className="px-8 py-8">
              {mode === "beacon" ? (
                <BeaconForm
                  institutions={institutions}
                  selected={selected}
                  onSelect={setSelected}
                  onContinue={handleBeaconContinue}
                  loading={loadingInst}
                  error={fetchError}
                />
              ) : (
                <PublisherForm
                  publisher={publisher}
                  institution={institution}
                  userId={userId}
                  onPublisher={setPublisher}
                  onInstitution={setInstitution}
                  onUserId={setUserId}
                  onSignIn={handlePublisherSignIn}
                  ready={!!publisherReady}
                  institutions={institutions}
                />
              )}
            </div>
          </div>

          {/* Footer text */}
          <p className="mt-6 text-[11px] text-slate-400 text-center leading-relaxed">
            Subscription rights are validated at sign-in.<br />
            By continuing, you agree to the <span className="text-slate-500 underline underline-offset-2 cursor-pointer">terms of service</span>.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Mode tab ─────────────────────────────────────────────────────────────────

function ModeTab({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 py-3 text-xs font-semibold tracking-wide transition-all relative ${
        active
          ? "text-slate-900"
          : "text-slate-400 hover:text-slate-600"
      }`}
    >
      {label}
      {active && (
        <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-blue-600" />
      )}
    </button>
  );
}

// ─── Beacon form ──────────────────────────────────────────────────────────────

interface BeaconFormProps {
  institutions: InstitutionSummary[];
  selected: string;
  onSelect: (id: string) => void;
  onContinue: () => void;
  loading: boolean;
  error: string | null;
}

function BeaconForm({ institutions, selected, onSelect, onContinue, loading, error }: BeaconFormProps) {
  const selectedInst = institutions.find((i) => i.id === selected);

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900 mb-1 tracking-tight">Welcome back</h1>
      <p className="text-sm text-slate-400 mb-8">
        Select your institution to get started.
      </p>

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner className="w-5 h-5" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-500 py-4">{error}</p>
      ) : (
        <>
          <label className="block text-xs font-medium text-slate-500 mb-2">
            Institution
          </label>

          {/* Institution cards */}
          <div className="space-y-2 mb-6">
            {institutions.map((inst) => (
              <button
                key={inst.id}
                onClick={() => onSelect(inst.id)}
                className={`w-full text-left px-4 py-3 rounded-xl border transition-all duration-200 flex items-center gap-3 ${
                  selected === inst.id
                    ? "border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/20 scale-[1.02] shadow-md shadow-blue-500/10"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-white hover:scale-[1.03] hover:shadow-lg hover:shadow-slate-200/50 hover:-translate-y-0.5"
                }`}
              >
                <span className="text-xl">{inst.avatar}</span>
                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-medium ${selected === inst.id ? "text-blue-900" : "text-slate-700"}`}>
                    {inst.name}
                  </p>
                  <p className="text-[11px] text-slate-400 truncate">{inst.description}</p>
                </div>
                {selected === inst.id && (
                  <svg className="w-5 h-5 text-blue-600 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>

          {/* Selected institution journals preview */}
          {selectedInst && selectedInst.licensed_journals.length > 0 && (
            <div className="mb-6 px-4 py-3 rounded-lg bg-slate-50 border border-slate-100">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Your collection</p>
              <div className="flex flex-wrap gap-1.5">
                {selectedInst.licensed_journals.map((j) => (
                  <span
                    key={j.code}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border"
                    style={{
                      backgroundColor: `${j.color}10`,
                      borderColor: `${j.color}30`,
                      color: j.color,
                    }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: j.color }} />
                    {j.code}
                  </span>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={onContinue}
            disabled={!selected}
            className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-sm font-semibold transition-all shadow-sm shadow-blue-600/20 hover:shadow-md hover:shadow-blue-600/25"
          >
            Continue
          </button>
        </>
      )}
    </div>
  );
}

// ─── Publisher form ───────────────────────────────────────────────────────────

interface PublisherFormProps {
  publisher: string;
  institution: string;
  userId: string;
  onPublisher: (v: string) => void;
  onInstitution: (v: string) => void;
  onUserId: (v: string) => void;
  onSignIn: () => void;
  ready: boolean;
  institutions: InstitutionSummary[];
}

function PublisherForm({
  publisher, institution, userId,
  onPublisher, onInstitution, onUserId,
  onSignIn, ready, institutions,
}: PublisherFormProps) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900 mb-1 tracking-tight">Publisher sign-in</h1>
      <p className="text-sm text-slate-400 mb-8">
        Access content through your publisher subscription.
      </p>

      <div className="space-y-5">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-2">
            Publisher
          </label>
          <select
            value={publisher}
            onChange={(e) => onPublisher(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          >
            <option value="">Select publisher...</option>
            {PUBLISHERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-2">
            Institution
          </label>
          <input
            list="institution-suggestions"
            value={institution}
            onChange={(e) => onInstitution(e.target.value)}
            placeholder="e.g. University of Edinburgh"
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
          <datalist id="institution-suggestions">
            {institutions.map((inst) => (
              <option key={inst.id} value={inst.name} />
            ))}
          </datalist>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-2">
            Subscriber ID
          </label>
          <input
            type="text"
            value={userId}
            onChange={(e) => onUserId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ready && onSignIn()}
            placeholder="Your publisher account ID"
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
      </div>

      <button
        onClick={onSignIn}
        disabled={!ready}
        className="mt-6 w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-sm font-semibold transition-all shadow-sm shadow-blue-600/20 hover:shadow-md hover:shadow-blue-600/25"
      >
        Sign in
      </button>
    </div>
  );
}
