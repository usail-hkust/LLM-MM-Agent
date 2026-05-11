import { toast } from "sonner";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

const PUBLIC_CONFIG_KEY = "mm_agent_config_public";
const SECURE_CONFIG_KEY = "mm_agent_config_secure";
const LEGACY_CONFIG_KEY = "mm_llm_config";

// 简单的 LocalStorage 帮助函数，避免 SSR 问题
const getToken = () => (typeof window !== "undefined" ? localStorage.getItem("mm_token") : null);

const safeJSONParse = (value: string | null) => {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const extractState = (raw: unknown) => {
  if (raw && typeof raw === "object") {
    if ("state" in raw && typeof raw.state === "object" && raw.state !== null) {
      // For older Zustand persisted payloads
      // @ts-expect-error - dynamic shape
      return raw.state?.config ?? raw.state;
    }
    return raw;
  }
  return {};
};

const getLLMConfig = () => {
  if (typeof window === "undefined") return {};
  const legacyRaw = safeJSONParse(localStorage.getItem(LEGACY_CONFIG_KEY));
  const legacyConfig = extractState(legacyRaw);
  const publicRaw =
    safeJSONParse(localStorage.getItem(PUBLIC_CONFIG_KEY)) || legacyConfig;
  const secureRaw = safeJSONParse(sessionStorage.getItem(SECURE_CONFIG_KEY));
  const secureConfig = extractState(secureRaw);

  return {
    modelName: publicRaw?.modelName || legacyConfig?.modelName || "",
    baseUrl: publicRaw?.baseUrl || legacyConfig?.baseUrl || "",
    apiKey: secureConfig?.apiKey || legacyConfig?.apiKey || "",
  };
};

const handleUnauthorized = () => {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem("mm_token");
    localStorage.removeItem("mm_user");
  } catch {
    // Ignore storage errors; redirect still protects the route.
  }
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
};

const buildHeaders = (options: RequestInit) => {
  const token = getToken();
  const llmConfig = getLLMConfig();
  const headers = new Headers(options.headers);

  if (token) headers.set("Authorization", `Bearer ${token}`);

  // 对于 FormData，不设置 Content-Type，让浏览器自动设置
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // 注入 LLM 配置
  if (llmConfig.apiKey) headers.set("X-LLM-API-Key", llmConfig.apiKey);
  if (llmConfig.modelName) headers.set("X-LLM-Model", llmConfig.modelName);
  if (llmConfig.baseUrl) headers.set("X-LLM-Base-URL", llmConfig.baseUrl);

  return headers;
};

const resolveUrl = (endpoint: string) => {
  if (endpoint.startsWith("http")) return endpoint;
  const base = API_BASE.replace(/\/+$/, "");
  if (base.endsWith("/projects") && endpoint.startsWith("/projects")) {
    return `${base}${endpoint.replace(/^\/projects/, "")}`;
  }
  return `${base}${endpoint}`;
};

const apiRequest = async (endpoint: string, options: RequestInit = {}) => {
  const response = await fetch(resolveUrl(endpoint), {
    ...options,
    headers: buildHeaders(options),
  });

  if (response.status === 401) {
    handleUnauthorized();
  }

  if (!response.ok) {
    const errorText = await response.text();
    // 统一错误处理
    try {
      const json = JSON.parse(errorText);
      throw new Error(json.detail || json.message || "Request failed");
    } catch {
      throw new Error(errorText || `Error ${response.status}`);
    }
  }

  return response;
};

/**
 * 通用 Fetch Wrapper，自动处理 Auth 和 LLM Headers
 */
export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await apiRequest(endpoint, options);

  // 处理空响应
  if (response.status === 204) return {} as T;

  return response.json();
}

export async function apiClientBlob(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const response = await apiRequest(endpoint, options);
  return response.blob();
}

export async function apiClientVoid(endpoint: string, options: RequestInit = {}): Promise<void> {
  await apiRequest(endpoint, options);
}
