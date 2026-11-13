const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message || res.statusText);
  }
  return res.json();
}

// --- Chat ---
export interface ChatResponse {
  message: string;
  image_url?: string;
  download_url?: string;
  rows?: Record<string, string>[];
  report?: Record<string, unknown>;
  preview?: Record<string, string>[];
}

export function sendMessage(
  message: string,
  history: { role: string; content: string }[]
): Promise<ChatResponse> {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

// --- Upload ---
export interface UploadResponse {
  ok: boolean;
  message: string;
  report?: Record<string, unknown>;
  preview?: Record<string, string>[];
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  return res.json();
}

export function useSample(): Promise<UploadResponse> {
  return request("/use-sample", { method: "POST" });
}

// --- Sessions ---
export interface SessionInfo {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  dataset_path: string;
  dataset_name: string;
}

export interface SessionDetail extends SessionInfo {
  history: { role: string; content: string }[];
}

export function listSessions(): Promise<{ ok: boolean; sessions: SessionInfo[] }> {
  return request("/api/sessions");
}

export function getSession(
  id: string
): Promise<{ ok: boolean; session: SessionDetail }> {
  return request(`/api/sessions/${id}`);
}

export function createSession(): Promise<{ ok: boolean; session_id: string }> {
  return request("/api/sessions/new", { method: "POST" });
}

export function deleteSession(id: string): Promise<{ ok: boolean }> {
  return request(`/api/sessions/${id}`, { method: "DELETE" });
}
