import type { ServerMessage } from "@/types";
import { useRunStore } from "@/store/runStore";
import { useConfigStore } from "@/store/configStore";
import { useTaskStore } from "@/store/taskStore";
import { useRunListStore } from "@/store/runListStore";

export function handleServerMessage(rawData: unknown): void {
  const msg = rawData as ServerMessage;
  if (!msg || typeof msg !== "object" || !("type" in msg)) return;

  switch (msg.type) {
    case "run_event":
      useRunStore.getState().appendEvent(msg.event);
      if (msg.event.event_type === "run_completed") {
        useRunStore.getState().setRunComplete(true);
        useTaskStore.getState().fetchTasks();
        void useRunListStore.getState().fetchRuns();
      } else if (msg.event.event_type === "run_failed") {
        useRunStore.getState().setRunComplete(false, msg.event.content ?? "未知错误");
        useTaskStore.getState().fetchTasks();
        void useRunListStore.getState().fetchRuns();
      }
      break;

    case "run_cancelled":
      useRunStore.getState().setRunComplete(false, "已取消");
      useTaskStore.getState().fetchTasks();
      void useRunListStore.getState().fetchRuns();
      break;

    case "run_failed":
      useRunStore.getState().setRunComplete(false, msg.error);
      useTaskStore.getState().fetchTasks();
      void useRunListStore.getState().fetchRuns();
      break;

    case "config_updated":
      useConfigStore.getState().setConfig(msg.config);
      break;

    case "error":
      console.error("[WS error]", msg.content);
      break;
  }
}
