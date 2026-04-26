import { create } from "zustand";
import { api } from "@/api/endpoints";
import type { RunSummary } from "@/types";

interface RunListState {
  runs: RunSummary[];
  fetchRuns: () => Promise<void>;
  deleteRun: (runId: string) => Promise<void>;
}

export const useRunListStore = create<RunListState>((set) => ({
  runs: [],
  fetchRuns: async () => {
    try {
      const runs = await api.listRuns();
      set({ runs });
    } catch {
      set({ runs: [] });
    }
  },

  deleteRun: async (runId) => {
    await api.deleteRun(runId);
    set((s) => ({ runs: s.runs.filter((r) => r.run_id !== runId) }));
  },
}));
