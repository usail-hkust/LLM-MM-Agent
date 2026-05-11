import { fetchEventSource, EventStreamContentType } from "@microsoft/fetch-event-source";

// Helper to access store outside of React components
const getStoreState = (key: string) => {
  if (typeof window === 'undefined') return null;
  const storage = key === "mm_agent_config_secure" ? sessionStorage : localStorage;
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw).state : null;
  } catch { return null; }
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

export class SSEConnection {
  private ctrl: AbortController | null = null;
  
  constructor(private onMsg: (d: any, t: string) => void, private onStatus: (s: string) => void) {}

  connect(url: string, token: string, customHeaders?: Record<string, string>) {
    this.disconnect();
    this.ctrl = new AbortController();
    this.onStatus("CONNECTING");

    fetchEventSource(url, {
      headers: { 
        Authorization: `Bearer ${token}`,
        ...getBYOKHeaders(), // [BYOK] Inject user configuration headers
        ...customHeaders // Allow custom headers to override
      },
      signal: this.ctrl.signal,
      async onopen(res) {
        if (res.ok && res.headers.get("content-type")?.includes(EventStreamContentType)) return;
        
        if (res.status === 401 || res.status === 403) {
            // [FIX] Global Auth Logout Trigger
            if (typeof window !== "undefined") {
                window.dispatchEvent(new Event("auth:unauthorized"));
            }
            throw new Error("Fatal:Unauthorized");
        }
        if (res.status === 404) throw new Error("Fatal:NotFound");
        throw new Error("Retry");
      },
      onmessage: (msg) => {
        if (msg.event === "ping") return;
        try {
          this.onMsg(JSON.parse(msg.data), msg.event || "message");
          this.onStatus("OPEN");
        } catch {}
      },
      onclose: () => this.onStatus("CLOSED"),
      onerror: (err) => { 
          if (err.message.startsWith("Fatal")) { 
              this.disconnect(); 
              throw err; 
          } 
      }
    }).catch(() => this.onStatus("CLOSED"));
  }

  disconnect() {
    this.ctrl?.abort();
    this.ctrl = null;
    this.onStatus("CLOSED");
  }
}
