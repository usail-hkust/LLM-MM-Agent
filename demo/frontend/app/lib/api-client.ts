import { assetService } from "./asset-service";

const getApiRoot = () => {
  // Use environment variable or fallback to localhost
  return process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
};

// Helper to access store outside of React components
const getStoreState = (key: string) => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // zustand persist format: {"state": {...}, "version": 0}
    return parsed.state || parsed;
  } catch (e) {
    console.error(`[api-client] Failed to read storage key "${key}":`, e);
    return null;
  }
};

function getBYOKHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const pub = getStoreState("mm_agent_config_public");
  const sec = getStoreState("mm_agent_config_secure");

  if (pub?.modelName) headers["X-LLM-Model"] = pub.modelName;
  if (pub?.baseUrl) headers["X-LLM-Base-URL"] = pub.baseUrl;
  if (sec?.apiKey) headers["X-LLM-API-Key"] = sec.apiKey;
  if (sec?.e2bKey) headers["X-E2B-API-Key"] = sec.e2bKey;

  return headers;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiClient<T>(endpoint: string, token: string | null, options: RequestInit = {}): Promise<T> {
  const root = getApiRoot();
  const url = `${root}${endpoint.startsWith("/") ? endpoint : "/" + endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...getBYOKHeaders(), // [BYOK] Inject user configuration headers
    ...(options.headers as Record<string, string>),
  };

  if (options.body instanceof FormData) {
    delete headers["Content-Type"];
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    console.error("[ApiClient] 401 Unauthorized for URL:", url);
    assetService.clear();
    // [FIX] Dispatch event so AuthContext can logout cleanly
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth:unauthorized"));
    }
  }

  if (!response.ok) {
    let errorData;
    try { errorData = await response.json(); } catch { errorData = await response.text(); }
    throw new ApiError(response.status, response.statusText, errorData);
  }

  if (response.status === 204) return {} as T;
  return response.json();
}
