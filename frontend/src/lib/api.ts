const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000").replace(/\/$/, "");
export const REQUIRE_AUTH = process.env.NEXT_PUBLIC_REQUIRE_AUTH === "1";
let csrfTokenPromise: Promise<string> | null = null;
let refreshPromise: Promise<boolean> | null = null;
let activeSessionId: string | null = null;
let accessToken: string | null = null;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
}

export interface AuthResponse {
  ok: boolean;
  access_token: string;
  user: AuthUser;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          accessToken = null;
          return false;
        }
        const data = await res.json();
        if (typeof data.access_token !== "string") {
          accessToken = null;
          return false;
        }
        accessToken = data.access_token;
        return true;
      })
      .catch(() => {
        accessToken = null;
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function isAuthPath(path: string) {
  return path.startsWith("/api/auth/");
}

async function authRequest(path: string, body: Record<string, string>): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(err.message || res.statusText, res.status);
  }
  const data = (await res.json()) as AuthResponse;
  accessToken = data.access_token;
  return data;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return authRequest("/api/auth/login", { email, password });
}

export function register(name: string, email: string, password: string): Promise<AuthResponse> {
  return authRequest("/api/auth/register", { name, email, password });
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } finally {
    accessToken = null;
  }
}

async function getCsrfToken(): Promise<string> {
  if (!csrfTokenPromise) {
    csrfTokenPromise = fetch(`${API_BASE}/api/csrf`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error("Gagal menyiapkan keamanan sesi.");
        const data = await res.json();
        return data.csrf_token as string;
      })
      .catch((error) => {
        csrfTokenPromise = null;
        throw error;
      });
  }
  return csrfTokenPromise;
}

function isStateChanging(method?: string) {
  return ["POST", "PUT", "PATCH", "DELETE"].includes((method || "GET").toUpperCase());
}

export function setActiveSessionId(id: string | null) {
  activeSessionId = id;
}

export function resolveApiUrl(path?: string): string | undefined {
  if (!path) return undefined;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method || "GET";
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (activeSessionId) headers.set("X-Session-Id", activeSessionId);
  if (accessToken && !isAuthPath(path)) headers.set("Authorization", `Bearer ${accessToken}`);
  if (isStateChanging(method) && !isAuthPath(path)) headers.set("X-CSRF-Token", await getCsrfToken());

  let res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });
  if (res.status === 401 && !isAuthPath(path) && await refreshAccessToken()) {
    headers.set("Authorization", `Bearer ${accessToken}`);
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers,
    });
  }
  if (res.status === 403 && isStateChanging(method)) csrfTokenPromise = null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(err.message || res.statusText, res.status);
  }
  return res.json();
}

export interface ChatResponse {
  message: string;
  image_url?: string;
  download_url?: string;
  rows?: Record<string, string>[];
  table?: Record<string, string | number>;
  report?: Record<string, unknown>;
  preview?: Record<string, string>[];
}

export async function streamMessage(
  message: string,
  history: { role: string; content: string }[],
  onToken: (text: string) => void,
  signal?: AbortSignal,
  onStatus?: (status: string) => void,
): Promise<ChatResponse> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (activeSessionId) headers.set("X-Session-Id", activeSessionId);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  headers.set("X-CSRF-Token", await getCsrfToken());

  const requestStream = () => fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers,
    signal,
    body: JSON.stringify({ message, history }),
  });
  let res = await requestStream();
  if (res.status === 401 && await refreshAccessToken()) {
    headers.set("Authorization", `Bearer ${accessToken}`);
    res = await requestStream();
  }
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message || res.statusText);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: ChatResponse | null = null;

  const consume = (chunk: string) => {
    buffer += chunk;
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const event of events) {
      const eventName = event.match(/^event: (.+)$/m)?.[1];
      const dataLine = event.match(/^data: (.+)$/m)?.[1];
      if (!dataLine) continue;
      const data = JSON.parse(dataLine);
      if (eventName === "status" && onStatus) onStatus(data.text || "");
      if (eventName === "token") onToken(data.text || "");
      if (eventName === "done") finalResult = data as ChatResponse;
      if (eventName === "error") throw new Error(data.message || "Streaming gagal.");
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    consume(decoder.decode(value, { stream: true }));
  }
  consume(decoder.decode());
  return finalResult || { message: "Streaming selesai tanpa hasil." };
}

export function sendMessage(message: string, history: { role: string; content: string }[]): Promise<ChatResponse> {
  return request("/chat", { method: "POST", body: JSON.stringify({ message, history }) });
}


export interface UploadResponse {
  ok: boolean;
  message: string;
  report?: Record<string, unknown>;
  preview?: Record<string, string>[];
}

export function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request("/upload", { method: "POST", body: form });
}

export function loadSample(): Promise<UploadResponse> {
  return request("/use-sample", { method: "POST" });
}

export interface SessionInfo {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  dataset_name: string;
}

export interface SessionDetail extends SessionInfo {
  history: { role: string; content: string }[];
  dataset_preview?: Record<string, string>[];
  dataset_report?: Record<string, unknown>;
}

export interface DatasetInfo {
  id: string;
  name: string;
  created_at: string;
  active: boolean;
}

export function listSessions(): Promise<{ ok: boolean; sessions: SessionInfo[] }> {
  return request("/api/sessions");
}

export function getSession(id: string): Promise<{ ok: boolean; session: SessionDetail }> {
  return request(`/api/sessions/${id}`);
}

export function createSession(): Promise<{ ok: boolean; session_id: string }> {
  return request("/api/sessions/new", { method: "POST" });
}

export function deleteSession(id: string): Promise<{ ok: boolean }> {
  return request(`/api/sessions/${id}`, { method: "DELETE" });
}

export function listDatasets(id: string): Promise<{ ok: boolean; datasets: DatasetInfo[] }> {
  return request(`/api/sessions/${id}/datasets`);
}

export function activateDataset(
  sessionId: string,
  datasetId: string,
): Promise<{ ok: boolean; datasets: DatasetInfo[] }> {
  return request(`/api/sessions/${sessionId}/datasets/${datasetId}/active`, { method: "PUT" });
}

export async function downloadExport(format: "pdf" | "xlsx"): Promise<void> {
  const headers = new Headers({ "X-CSRF-Token": await getCsrfToken() });
  if (activeSessionId) headers.set("X-Session-Id", activeSessionId);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const requestExport = () => fetch(`${API_BASE}/export/${format}`, {
    method: "POST",
    credentials: "include",
    headers,
  });
  let response = await requestExport();
  if (response.status === 401 && await refreshAccessToken()) {
    headers.set("Authorization", `Bearer ${accessToken}`);
    response = await requestExport();
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Export gagal." }));
    throw new ApiError(error.message || "Export gagal.", response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `echabot-export.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
