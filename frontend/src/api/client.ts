export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`api ${status}`);
    this.status = status;
    this.body = body;
  }
}

/** Pull the most useful human message out of any error a mutation might
 * throw. Sparkd domain errors return application/problem+json with
 * `detail`/`title`; FastAPI validation errors return `{detail: [...]}`
 * arrays; plain Errors expose `.message`. Falls back to the status code
 * + body so a 500 with no body still shows *something*. */
export function formatApiError(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | null;
    if (body && typeof body === "object") {
      const detail = body.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        // FastAPI validation: [{loc, msg, type}, ...]
        return detail
          .map((d) =>
            typeof d === "object" && d && "msg" in d
              ? String((d as { msg: unknown }).msg)
              : JSON.stringify(d),
          )
          .join("; ");
      }
      if (typeof body.title === "string") return body.title;
    }
    return `${err.status}: ${JSON.stringify(body)}`;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  // All HTTP endpoints live under /api on the backend; SPA owns the rest of
  // the URL space so /recipes/:name doesn't collide with the API.
  const fullPath = path.startsWith("/api") ? path : `/api${path}`;
  const r = await fetch(fullPath, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 204) return undefined as unknown as T;
  const text = await r.text();
  const data = text ? JSON.parse(text) : null;
  if (!r.ok) throw new ApiError(r.status, data);
  return data as T;
}

export const api = {
  get: <T>(p: string) => req<T>("GET", p),
  post: <T>(p: string, b?: unknown) => req<T>("POST", p, b),
  put: <T>(p: string, b?: unknown) => req<T>("PUT", p, b),
  delete: <T>(p: string) => req<T>("DELETE", p),
};

export function openWS(path: string): WebSocket {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(`${proto}//${location.host}${path}`);
}
