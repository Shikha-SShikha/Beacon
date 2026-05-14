import type {
  InstitutionSummary,
  SearchResponse,
  AskResponse,
  BaselineResponse,
  JournalInfo,
  CitationContextData,
  FoundationalPaper,
} from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

export async function fetchInstitutions(): Promise<InstitutionSummary[]> {
  const data = await request<{ institutions: InstitutionSummary[] }>("/institutions");
  return data.institutions;
}

export async function fetchInstitution(id: string): Promise<InstitutionSummary> {
  return request<InstitutionSummary>(`/institutions/${id}`);
}

export async function fetchJournals(): Promise<Record<string, JournalInfo>> {
  const data = await request<{ journals: Record<string, JournalInfo> }>("/journals");
  return data.journals;
}

export async function postSearch(
  query: string,
  institutionId: string,
  topK: number
): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: institutionId, top_k: topK }),
  });
}

export async function postAsk(
  query: string,
  institutionId: string,
  topK: number = 10
): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: institutionId, top_k: topK }),
  });
}

export async function postBaseline(
  query: string,
  institutionId: string,
  topK: number = 6
): Promise<BaselineResponse> {
  return request<BaselineResponse>("/baseline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: institutionId, top_k: topK }),
  });
}

export async function postBaselineAsk(
  query: string,
  institutionId: string,
  topK: number = 8
): Promise<AskResponse> {
  return request<AskResponse>("/baseline/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: institutionId, top_k: topK }),
  });
}

export async function postWebAiAsk(
  query: string,
  institutionId: string,
): Promise<AskResponse> {
  return request<AskResponse>("/baseline/webai", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: institutionId, top_k: 5 }),
  });
}

export async function fetchCitationContext(source: string): Promise<CitationContextData> {
  return request<CitationContextData>(`/citation/context?source=${encodeURIComponent(source)}`);
}

export async function fetchAttributionSummary(): Promise<import("../types").AttributionSummary> {
  return request("/attribution/summary");
}

export async function fetchAttributionFeed(publisher?: string): Promise<import("../types").FeedEvent[]> {
  const qs = publisher ? `?publisher=${encodeURIComponent(publisher)}` : "";
  return request(`/attribution/feed${qs}`);
}

export async function simulateBlockedRequest(query: string): Promise<void> {
  // Fires query as ai_bot (zero collections, no OA bypass) → always fully blocked
  await request("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, institution_id: "ai_bot", top_k: 8 }),
  }).catch(() => {}); // "No accessible results" is expected — swallow it
}

export async function fetchFoundational(sources: string[]): Promise<{ foundational: FoundationalPaper[] }> {
  return request<{ foundational: FoundationalPaper[] }>("/citation/foundational", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources }),
  });
}
