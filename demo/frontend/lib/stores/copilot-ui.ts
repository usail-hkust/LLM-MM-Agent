import { create } from "zustand";

interface CopilotUIState {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

export const useCopilotUIStore = create<CopilotUIState>((set) => ({
  isOpen: false, // Default closed
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
}));
