"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ElementType, ReactNode } from "react";

// --- Dock Store ---
export type DockActionVariant = "primary" | "secondary" | "danger" | "ghost";

export interface DockAction {
  id: string;
  label: string;
  onClick: () => void;
  variant?: DockActionVariant;
  disabled?: boolean;
  loading?: boolean;
  icon?: ElementType;
  tooltip?: string;
}

interface DockState {
  rightActions: DockAction[];
  centerContent: ReactNode;
  isInputMode: boolean;
  inputValue: string;
  inputPlaceholder: string;
  setRightActions: (actions: DockAction[]) => void;
  setCenterContent: (content: ReactNode) => void;
  enterInputMode: (placeholder?: string, initialValue?: string) => void;
  exitInputMode: () => void;
  setInputValue: (val: string) => void;
}

export const useDockStore = create<DockState>((set) => ({
  rightActions: [],
  centerContent: null,
  isInputMode: false,
  inputValue: "",
  inputPlaceholder: "",
  setRightActions: (actions) => set({ rightActions: actions }),
  setCenterContent: (content) => set({ centerContent: content }),
  enterInputMode: (placeholder = "Enter feedback...", initialValue = "") =>
    set({
      isInputMode: true,
      inputPlaceholder: placeholder,
      inputValue: initialValue,
    }),
  exitInputMode: () =>
    set({
      isInputMode: false,
      inputValue: "",
      inputPlaceholder: "",
    }),
  setInputValue: (val) => set({ inputValue: val }),
}));

// --- UI Stage Store ---
interface StageState {
  selectedNodeId: string | null;
  selectedVersionId: string | null; // null = Head (Live)
  selectedVersionIndex: number | null; // null = Head (Live)
  selectedIteration: number;
  selectedArtifactId: string | null;
  isAgentWorking: boolean;
  selectedNodeStatus?: string; // 节点执行状态（DRAFTING、REVIEWING 等）
  selectedNodeType?: string; // 节点类型（EXECUTOR、CODE_GENERATOR 等）

  // Actions
  selectNode: (nodeId: string | null) => void;
  timeTravel: (versionIndex: number | null) => void;
  switchIteration: (iteration: number) => void;
  selectArtifact: (artifactId: string | null) => void;
  setAgentWorking: (working: boolean) => void;
  setNodeStatus: (status?: string) => void; // [NEW] 设置节点状态
  setNodeType: (type?: string) => void; // [NEW] 设置节点类型
  resetStage: () => void;

  // Computed helper
  isHead: boolean;
}

export const useStageStore = create<StageState>((set) => ({
  selectedNodeId: null,
  selectedVersionId: null,
  selectedVersionIndex: null,
  selectedIteration: 0,
  selectedArtifactId: null,
  isAgentWorking: false,
  selectedNodeStatus: undefined,
  selectedNodeType: undefined,
  isHead: true,

  selectNode: (nodeId) => set({
    selectedNodeId: nodeId,
    selectedVersionId: null,
    selectedVersionIndex: null, // Reset to head when switching nodes
    selectedArtifactId: null,
    selectedIteration: 0,
    isAgentWorking: false, // [FIX] Reset working state when switching context
    selectedNodeStatus: undefined, // [NEW] Reset node status
    selectedNodeType: undefined, // [NEW] Reset node type
    isHead: true,
  }),

  timeTravel: (versionIndex) => set({
    selectedVersionIndex: versionIndex,
    selectedVersionId: versionIndex ? String(versionIndex) : null,
    selectedArtifactId: null, // Reset artifact selection when changing versions
    isHead: versionIndex === null,
  }),

  switchIteration: (iteration) => set({ selectedIteration: iteration }),

  selectArtifact: (artifactId) => set({ selectedArtifactId: artifactId }),

  setAgentWorking: (working) => set({ isAgentWorking: working }),

  setNodeStatus: (status) => set({ selectedNodeStatus: status }), // [NEW] Set node status

  setNodeType: (type) => set({ selectedNodeType: type }), // [NEW] Set node type

  resetStage: () => set({
    selectedNodeId: null,
    selectedVersionId: null,
    selectedVersionIndex: null,
    selectedArtifactId: null,
    selectedIteration: 0,
    isAgentWorking: false,
    selectedNodeStatus: undefined,
    selectedNodeType: undefined,
    isHead: true,
  }),
}));

// --- Config UI Store ---
interface ConfigState {
  isOpen: boolean;
  hasHydrated: boolean;
  setIsOpen: (open: boolean) => void;
  setHasHydrated: (hydrated: boolean) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      isOpen: false,
      hasHydrated: false,
      setIsOpen: (open) => set({ isOpen: open }),
      setHasHydrated: (hydrated) => set({ hasHydrated: hydrated }),
    }),
    {
      name: "mm_config_ui",
      storage: typeof window !== "undefined" ? createJSONStorage(() => localStorage) : undefined,
      partialize: (state) => ({ isOpen: state.isOpen }),
      skipHydration: true,
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);

// --- Auth Store (简化版) ---
interface AuthState {
  token: string | null;
  user: { username: string } | null;
  login: (username: string, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      login: (username, token) => {
        // 同步到 localStorage (保持兼容性)
        if (typeof window !== "undefined") {
          localStorage.setItem("mm_token", token);
        }
        set({ user: { username }, token });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("mm_token");
        }
        set({ user: null, token: null });
      },
    }),
    { name: "mm_auth" },
  )
);
