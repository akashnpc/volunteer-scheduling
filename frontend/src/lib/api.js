const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "vs_token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage can be unavailable (private mode); the user just has to sign in again */
  }
}

function buildUrl(path, params) {
  const url = new URL(`${BASE}/api${path}`);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "" && value !== false) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

async function request(path, { method = "GET", body, params } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server. If it was idle it may still be waking up, so try again in a moment.", 0);
  }

  if (response.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event("vs-auth-expired"));
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, response.status);
  }
  // Anything that changed data can change the alert badge in the navigation.
  if (method !== "GET") window.dispatchEvent(new Event("vs-data-changed"));
  return response;
}

export async function api(path, options) {
  const response = await request(path, options);
  return response.status === 204 ? null : response.json();
}

/** Fetch a file with the auth header and hand it to the browser as a download. */
export async function download(path, fallbackName) {
  const response = await request(path);
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
