import { create } from "zustand";
import { persist } from "zustand/middleware";
import { LucideIcon } from "lucide-react";

// --- Config Store ---
interface ConfigState {
  isOpen: boolean;
  hasHydrated: boolean;
  setIsOpen: (v: boolean) => void;
  setHasHydrated: (v: boolean) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      isOpen: false,
      hasHydrated: false,
      setIsOpen: (v) => set({ isOpen: v }),
      setHasHydrated: (v) => set({ hasHydrated: v }),
    }),
    {
      name: "mm-config-storage",
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

// --- Stage Store ---
interface StageState {
  selectedNodeId: string | null;
  selectedVersionIndex: number | null; // For Time Travel
  selectedArtifactId: string | null;
  isHead: boolean; // Virtual computed property helper
  
  selectNode: (id: string | null) => void;
  selectArtifact: (id: string | null) => void;
  timeTravel: (versionIndex: number | null) => void;
  resetStage: () => void;
}

export const useStageStore = create<StageState>((set, get) => ({
  selectedNodeId: null,
  selectedVersionIndex: null,
  selectedArtifactId: null,
  isHead: true,

  selectNode: (id) => set({ 
    selectedNodeId: id, 
    selectedVersionIndex: null, 
    selectedArtifactId: null,
    isHead: true 
  }),

  selectArtifact: (id) => set({ selectedArtifactId: id }),

  timeTravel: (index) => set({ 
    selectedVersionIndex: index,
    isHead: index === null
  }),

  resetStage: () => set({ 
    selectedNodeId: null, 
    selectedVersionIndex: null, 
    selectedArtifactId: null,
    isHead: true 
  }),
}));

// --- Dock Store ---
export interface DockAction {
  id: string;
  label: string;
  icon?: LucideIcon;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  tooltip?: string;
}

interface DockState {
  rightActions: DockAction[];
  centerContent: React.ReactNode | null;
  
  // Input Mode (for "Reject" reasoning etc.)
  isInputMode: boolean;
  inputPlaceholder: string;
  inputValue: string;
  
  setRightActions: (actions: DockAction[]) => void;
  setCenterContent: (content: React.ReactNode | null) => void;
  
  enterInputMode: (placeholder?: string, initialValue?: string) => void;
  exitInputMode: () => void;
  setInputValue: (v: string) => void;
}

export const useDockStore = create<DockState>((set) => ({
  rightActions: [],
  centerContent: null,
  isInputMode: false,
  inputPlaceholder: "",
  inputValue: "",

  setRightActions: (actions) => set({ rightActions: actions }),
  setCenterContent: (content) => set({ centerContent: content }),

  enterInputMode: (placeholder = "Enter text...", initialValue = "") => 
    set({ isInputMode: true, inputPlaceholder: placeholder, inputValue: initialValue }),
    
  exitInputMode: () => 
    set({ isInputMode: false, inputValue: "" }),
    
  setInputValue: (v) => set({ inputValue: v }),
}));
