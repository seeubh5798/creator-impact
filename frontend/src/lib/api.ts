// Browser calls go to /api/* on the same origin; next.config.ts rewrites them to
// the FastAPI backend, so the session cookie stays first-party.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {}
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

// Server-side calls (server components) talk to the backend directly.
export function backendUrl(path: string): string {
  const base = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}
