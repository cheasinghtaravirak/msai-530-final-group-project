// Thin fetch wrapper: adds the JWT, parses the standard error format
// {"error": {"code", "message", "details"}} and reports 401s to the auth layer.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown };

/** Call the API through the gateway. `path` starts with the service, e.g. "/admin/branches". */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return (await apiResponse<T>(path, options)).body;
}

/** `api` plus the HTTP status, for endpoints where 200 and 201 mean different things. */
export async function apiResponse<T>(
  path: string,
  { json, headers, ...init }: RequestOptions = {},
): Promise<{ status: number; body: T }> {
  const finalHeaders = new Headers(headers);
  if (json !== undefined) finalHeaders.set("Content-Type", "application/json");
  if (accessToken) finalHeaders.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: finalHeaders,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the server");
  }

  const text = await response.text();
  const body = text ? safeJson(text) : null;

  if (!response.ok) {
    if (response.status === 401 && accessToken) onUnauthorized?.();
    const err = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiError(
      response.status,
      err?.code ?? `HTTP_${response.status}`,
      err?.message ?? (response.status >= 500 ? "Service unavailable" : response.statusText),
      err?.details,
    );
  }
  return { status: response.status, body: body as T };
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { error: { code: "BAD_RESPONSE", message: text.slice(0, 200) } };
  }
}
