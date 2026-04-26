import { create } from "zustand";
import type { AppConfig } from "@/types";
import { api } from "@/api/endpoints";

interface ConfigState {
  config: AppConfig | null;
  loading: boolean;
  error: string | null;
  setConfig: (cfg: AppConfig) => void;
  fetchConfig: () => Promise<void>;
}

const RETRIES = 10;
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const useConfigStore = create<ConfigState>((set) => ({
  config: null,
  loading: false,
  error: null,

  setConfig: (cfg) => set({ config: cfg, error: null }),

  fetchConfig: async () => {
    set({ loading: true, error: null });
    for (let attempt = 0; attempt < RETRIES; attempt++) {
      try {
        const cfg = await api.getConfig();
        set({ config: cfg, loading: false, error: null });
        return;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (attempt === RETRIES - 1) {
          set({
            loading: false,
            error: `拉取配置失败（请确认本机已运行 magent-tui serve，或 Tauri 已启动内嵌服务）: ${msg}`,
          });
          return;
        }
        await delay(400 + attempt * 200);
      }
    }
  },
}));
