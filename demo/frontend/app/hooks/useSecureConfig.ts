"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { useCallback } from "react";

const PUBLIC_CONFIG_KEY = "mm_agent_config_public";
const SECURE_CONFIG_KEY = "mm_agent_config_secure";

interface PublicState {
  modelName: string;
  baseUrl: string;
  contextWindowTokens: number;
  setModelName: (name: string) => void;
  setBaseUrl: (url: string) => void;
  setContextWindowTokens: (tokens: number) => void;
}

const usePublicStore = create<PublicState>()(
  persist(
    (set) => ({
      modelName: "",
      baseUrl: "",
      contextWindowTokens: 120000,
      setModelName: (name) => set({ modelName: name }),
      setBaseUrl: (url) => set({ baseUrl: url }),
      setContextWindowTokens: (tokens) => set({ contextWindowTokens: tokens }),
    }),
    {
      name: PUBLIC_CONFIG_KEY,
      storage: typeof window !== "undefined" ? createJSONStorage(() => localStorage) : undefined,
    },
  ),
);

interface SecureState {
  apiKey: string;
  e2bKey: string;
  setApiKey: (key: string) => void;
  setE2bKey: (key: string) => void;
}

const useSecureStore = create<SecureState>()(
  persist(
    (set) => ({
      apiKey: "",
      e2bKey: "",
      setApiKey: (key) => set({ apiKey: key }),
      setE2bKey: (key) => set({ e2bKey: key }),
    }),
    {
      name: SECURE_CONFIG_KEY,
      storage: typeof window !== "undefined" ? createJSONStorage(() => localStorage) : undefined, // 改为 localStorage 持久化
    },
  ),
);

export function useSecureConfig() {
  const publicState = usePublicStore();
  const secureState = useSecureStore();

  const getLLMHeaders = useCallback(() => {
    const headers: Record<string, string> = {};
    if (publicState.modelName) headers["X-LLM-Model"] = publicState.modelName;
    if (publicState.baseUrl) headers["X-LLM-Base-URL"] = publicState.baseUrl;
    if (publicState.contextWindowTokens) {
      headers["X-LLM-Context-Window"] = String(publicState.contextWindowTokens);
    }
    if (secureState.apiKey) headers["X-LLM-API-Key"] = secureState.apiKey;
    if (secureState.e2bKey) headers["X-E2B-API-Key"] = secureState.e2bKey;
    return headers;
  }, [
    publicState.baseUrl,
    publicState.contextWindowTokens,
    publicState.modelName,
    secureState.apiKey,
    secureState.e2bKey,
  ]);

  return {
    config: {
      modelName: publicState.modelName,
      baseUrl: publicState.baseUrl,
      contextWindowTokens: publicState.contextWindowTokens,
      apiKey: secureState.apiKey,
      e2bKey: secureState.e2bKey,
    },
    updateConfig: (updates: Partial<{
      modelName: string;
      baseUrl: string;
      contextWindowTokens: number;
      apiKey: string;
      e2bKey: string;
    }>) => {
      if (updates.modelName !== undefined) publicState.setModelName(updates.modelName);
      if (updates.baseUrl !== undefined) publicState.setBaseUrl(updates.baseUrl);
      if (updates.contextWindowTokens !== undefined) {
        publicState.setContextWindowTokens(updates.contextWindowTokens);
      }
      if (updates.apiKey !== undefined) secureState.setApiKey(updates.apiKey);
      if (updates.e2bKey !== undefined) secureState.setE2bKey(updates.e2bKey);
    },
    getLLMHeaders,
  };
}
