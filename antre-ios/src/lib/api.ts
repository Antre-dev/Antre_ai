// Typed client for the Antre web app API.
// Endpoints used:
//   GET  /api/status              — system status
//   POST /chat                    — chat with Antre
//   GET  /api/mode  POST /api/mode — auto mode
//   GET  /activity/history        — recent events
//   GET  /activity/stream         — SSE live feed (see activity.ts)
//   GET  /api/permissions/pending — pending approval requests (phase 2)
//   POST /api/permissions/{id}/approve | /deny (phase 2)

import { getSettings } from "./settings";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export interface ActivityEvent {
  id?: number;
  ts?: string;
  type: string;
  category?: string;
  tool?: string;
  args?: string;
  result?: string;
  status?: string;
  duration_ms?: number;
  screenshot_url?: string;
  host?: string;
  command?: string;
  action?: string;
  url?: string;
  title?: string;
  text?: string;
  auto?: boolean;
  [key: string]: unknown;
}

export interface Status {
  busy: boolean;
  active_tools: number;
  uptime_seconds: number;
  memory_count: number;
  screenshot_count: number;
  auto: boolean;
  [key: string]: unknown;
}

export interface PendingPermission {
  id: string;
  tool: string;
  summary: string;
  danger_level: number; // 1..5
  created_at: string;
  expires_at: string;
  [key: string]: unknown;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { serverUrl } = await getSettings();
  if (!serverUrl) throw new ApiError("No server URL configured — set it in Settings.", 0);
  let res: Response;
  try {
    res = await fetch(`${serverUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (e) {
    throw new ApiError(`Cannot reach ${serverUrl} — is the laptop online?`, 0);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(body || `HTTP ${res.status}`, res.status);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------- status

export function getStatus(): Promise<Status> {
  return request<Status>("/api/status");
}

// ----------------------------------------------------------------- chat

export interface ChatReply {
  response: string;
  images?: string[];
}

export function sendChat(message: string): Promise<ChatReply> {
  return request<ChatReply>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// -------------------------------------------------------------- auto mode

export function getMode(): Promise<{ auto: boolean }> {
  return request<{ auto: boolean }>("/api/mode");
}

export function setMode(auto: boolean): Promise<{ auto: boolean }> {
  return request<{ auto: boolean }>("/api/mode", {
    method: "POST",
    body: JSON.stringify({ auto }),
  });
}

// --------------------------------------------------------------- activity

export function getHistory(limit = 100): Promise<{ events: ActivityEvent[] }> {
  return request<{ events: ActivityEvent[] }>(
    `/activity/history?limit=${limit}`,
  );
}

// ------------------------------------------------------------ permissions
// Phase 2 — the backend queue. These are the agreed contract.

export function getPendingPermissions(): Promise<{ requests: PendingPermission[] }> {
  return request<{ requests: PendingPermission[] }>("/api/permissions/pending");
}

export function approvePermission(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/permissions/${id}/approve`, {
    method: "POST",
  });
}

export function denyPermission(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/permissions/${id}/deny`, {
    method: "POST",
  });
}

// ----------------------------------------------------------- connectivity

export async function ping(): Promise<{ status: Status; latencyMs: number }> {
  const t0 = Date.now();
  const status = await getStatus();
  return { status, latencyMs: Date.now() - t0 };
}
