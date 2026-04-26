import { create } from "zustand";
import type { RunEvent } from "@/types";

interface RunState {
  events: RunEvent[];
  running: boolean;
  error: string | null;
  appendEvent: (event: RunEvent) => void;
  setRunComplete: (success: boolean, error?: string) => void;
  clear: () => void;
}

export const useRunStore = create<RunState>((set) => ({
  events: [],
  running: false,
  error: null,

  appendEvent: (event) =>
    set((s) => ({
      events: [...s.events, event],
      running: event.event_type !== "run_completed" && event.event_type !== "run_failed",
    })),

  setRunComplete: (success, error) =>
    set({ running: false, error: success ? null : (error ?? null) }),

  clear: () => set({ events: [], running: false, error: null }),
}));
