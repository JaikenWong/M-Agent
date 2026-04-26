import { create } from "zustand";
import type { RunEvent } from "@/types";

/** 一次任务在终端的可见结果，避免用户发完不知道有没有做完 */
export type RunOutcome = {
  kind: "success" | "failed" | "cancelled";
  message: string;
};

interface RunState {
  events: RunEvent[];
  running: boolean;
  error: string | null;
  lastOutcome: RunOutcome | null;
  appendEvent: (event: RunEvent) => void;
  setRunComplete: (success: boolean, error?: string) => void;
  dismissLastOutcome: () => void;
  clear: () => void;
}

const successHint =
  "本次任务已结束。交付物在「工作区」里按 Agent 目录查看；运行时间线与记录列表在「历史」。";

export const useRunStore = create<RunState>((set) => ({
  events: [],
  running: false,
  error: null,
  lastOutcome: null,

  appendEvent: (event) =>
    set((s) => {
      if (event.event_type === "run_started") {
        return {
          events: [...s.events, event],
          running: true,
          lastOutcome: null,
          error: null,
        };
      }
      return {
        events: [...s.events, event],
        running: event.event_type !== "run_completed" && event.event_type !== "run_failed",
      };
    }),

  setRunComplete: (success, error) =>
    set(() => {
      let lastOutcome: RunOutcome | null = null;
      if (success) {
        lastOutcome = { kind: "success", message: successHint };
      } else {
        const e = (error ?? "").trim();
        if (e === "已取消" || e.includes("取消")) {
          lastOutcome = { kind: "cancelled", message: "任务已取消。若需结果请先完成运行再查看「工作区」/「历史」。" };
        } else {
          lastOutcome = { kind: "failed", message: e || "任务失败" };
        }
      }
      return { running: false, error: success ? null : (error ?? null), lastOutcome };
    }),

  dismissLastOutcome: () => set({ lastOutcome: null }),

  clear: () => set({ events: [], running: false, error: null, lastOutcome: null }),
}));
