export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  remote_allowed: boolean;
  url: string;
  keyword_score: number | null;
  embedding_score: number | null;
  posted_at: string | null;
}

export interface Draft {
  id: string;
  application_id: string;
  resume_md: string | null;
  cover_letter_md: string | null;
  email_subject: string | null;
  email_body: string | null;
  model_used: string | null;
  prompt_version: string | null;
}

interface ApplicationResult {
  id: string;
  status: string;
}

export interface Application {
  id: string;
  job_id?: string | null;
  status: "DRAFTED" | "APPROVED" | "SENDING" | "SENT" | "RESPONDED" | "INTERVIEWING" | "OFFERED" | "REJECTED" | "WITHDRAWN" | "FAILED";
  job_title?: string | null;
  company?: string | null;
  created_at?: string | null;
}

export interface DraftWithJob {
  id: string;
  application_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  resume_md: string | null;
  cover_letter_md: string | null;
  email_subject: string | null;
  email_body: string | null;
  model_used: string | null;
  prompt_version: string | null;
  job_title: string;
  company: string;
}

const BASE = "/api";

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  jobs: {
    list: (limit = 50) =>
      request<Job[]>("GET", `/jobs?limit=${limit}`),
  },
  drafts: {
    generate: (jobId: string) =>
      request<Draft>("POST", `/drafts/generate/${jobId}`),
    get: (draftId: string) =>
      request<Draft>("GET", `/drafts/${draftId}`),
    patch: (draftId: string, body: Partial<Draft>) =>
      request<Draft>("PATCH", `/drafts/${draftId}`, body),
    approve: (draftId: string) =>
      request<ApplicationResult>("POST", `/drafts/${draftId}/approve`),
    reject: (draftId: string) =>
      request<ApplicationResult>("POST", `/drafts/${draftId}/reject`),
    list: (status?: string) =>
      request<DraftWithJob[]>("GET", status ? `/drafts?status=${status}` : "/drafts"),
  },
  applications: {
    list: () => request<Application[]>("GET", "/applications"),
    patch: (id: string, body: { status: string }) =>
      request<Application>("PATCH", `/applications/${id}`, body),
  },
  auth: {
    login: (email: string, password: string) =>
      request<{ id: string; email: string }>("POST", "/auth/login", {
        email,
        password,
      }),
    logout: () => request<{ ok: boolean }>("POST", "/auth/logout"),
    me: () => request<{ id: string; email: string }>("GET", "/auth/me"),
  },
};
