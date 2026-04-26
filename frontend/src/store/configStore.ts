import { create } from "zustand";
import type { AppConfig } from "@/types";
import { api } from "@/api/endpoints";

interface ConfigState {
  config: AppConfig | null;
  loading: boolean;
  setConfig: (cfg: AppConfig) => void;
  fetchConfig: () => Promise<void>;
}

export const useConfigStore = create<ConfigState>((set) => ({
  config: null,
  loading: false,

  setConfig: (cfg) => set({ config: cfg }),

  fetchConfig: async () => {
    set({ loading: true });
    try {
      const cfg = await api.getConfig();
      set({ config: cfg });
    } finally {
      set({ loading: false });
    }
  },
}));
