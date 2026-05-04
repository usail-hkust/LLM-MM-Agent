"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useAuth } from "@/app/context/AuthContext";
import { useSignal } from "@/app/context/SignalContext";

interface UseBlobUrlResult {
  url: string | null;
  loading: boolean;
  error: string | null;
}

// [FIX] Extended ArtifactSource to allow filename context for backend MIME inference
type ArtifactSource =
  | string
  | { remote_path: string }
  | { blob_hash: string; filename?: string } // [Updated] Added filename
  | null;

export function useBlobUrl(
  source: ArtifactSource,
  projectIdProp?: string,
  mimeType: string = "application/octet-stream"
): UseBlobUrlResult {
  const { token } = useAuth();
  const { projectId: signalProjectId } = useSignal();
  const projectId = projectIdProp || signalProjectId;

  // Track token ref to use in async calls
  const tokenRef = useRef(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const [state, setState] = useState<UseBlobUrlResult>({
    url: null,
    loading: false,
    error: null,
  });

  const activeUrlRef = useRef<string | null>(null);

  // Memoize source key to prevent re-fetching on same object content
  const sourceKey = useMemo(() => {
    if (!source) return null;
    if (typeof source === "string") return source;
    if ("remote_path" in source) return `remote:${source.remote_path}`;
    if ("blob_hash" in source) return `hash:${source.blob_hash}`;
    return null;
  }, [source]);

  useEffect(() => {
    if (!sourceKey) {
      if (activeUrlRef.current) URL.revokeObjectURL(activeUrlRef.current);
      activeUrlRef.current = null;
      setState({ url: null, loading: false, error: null });
      return;
    }

    const controller = new AbortController();
    const signal = controller.signal;

    const load = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        let blob: Blob | null = null;
        const currentToken = tokenRef.current;

        // [FIX] Robust API Root Calculation
        const rawBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
        const apiRoot = rawBase.replace(/\/projects\/?$/, "").replace(/\/$/, "");

        // === STRATEGY 1: Direct Content (Data URL or HTTP) ===
        if (typeof source === "string") {
          if (source.startsWith("data:") || source.startsWith("blob:")) {
            if (!signal.aborted) setState({ url: source, loading: false, error: null });
            return;
          }
          if (source.startsWith("http")) {
            if (!signal.aborted) setState({ url: source, loading: false, error: null });
            return;
          }
          if (source.includes("/") && !source.startsWith("/api")) {
            if (!projectId) throw new Error("Project ID required for file path");
            const encodedPath = encodeURIComponent(source);
            const fetchUrl = `${apiRoot}/projects/${projectId}/files/download?path=${encodedPath}`;
            blob = await fetchBlob(fetchUrl, currentToken, signal);
          } else {
            throw new Error("Invalid source format");
          }
        }

        // === STRATEGY 2: Remote Virtual Path ===
        else if (source && "remote_path" in source) {
          if (!projectId) throw new Error("Project ID required for file path");
          const encodedPath = encodeURIComponent(source.remote_path);
          const fetchUrl = `${apiRoot}/projects/${projectId}/files/download?path=${encodedPath}`;
          blob = await fetchBlob(fetchUrl, currentToken, signal);
        }

        // === STRATEGY 3: CAS Blob Hash (Preferred) ===
        else if (source && "blob_hash" in source) {
          // [FIX] Inject filename param to help backend infer Content-Type header
          // This allows the backend to send "image/png" instead of "application/octet-stream"
          const params = new URLSearchParams();
          if (source.filename) {
              params.append("filename", source.filename);
          }
          
          const queryString = params.toString() ? `?${params.toString()}` : "";
          const fetchUrl = `${apiRoot}/assets/${source.blob_hash}${queryString}`;
          
          blob = await fetchBlob(fetchUrl, currentToken, signal);
        }

        if (!signal.aborted && blob) {
          // [CRITICAL FIX] Type Re-casting (MIME Override)
          // The backend might return 'application/octet-stream' or plain text due to CAS nature.
          // We MUST enforce the expected MIME type (from metadata) for the browser to render images correctly.
          if (mimeType && mimeType !== "application/octet-stream" && blob.type !== mimeType) {
              // Create a new slice with the enforced content type
              // This is efficient as it doesn't copy data, just creates a new view
              blob = blob.slice(0, blob.size, mimeType);
          }

          const url = URL.createObjectURL(blob);
          if (activeUrlRef.current) URL.revokeObjectURL(activeUrlRef.current);
          activeUrlRef.current = url;
          setState({ url, loading: false, error: null });
        }
      } catch (e: any) {
        if (!signal.aborted) {
          console.error("[useBlobUrl]", e);
          setState({ url: null, loading: false, error: e.message });
        }
      }
    };

    load();

    return () => {
      controller.abort();
      if (activeUrlRef.current) URL.revokeObjectURL(activeUrlRef.current);
    };
  }, [sourceKey, projectId, mimeType]);

  return state;
}

// Helper to standardise auth fetch
async function fetchBlob(url: string, token: string | null, signal: AbortSignal) {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { headers, signal });
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return await res.blob();
}
