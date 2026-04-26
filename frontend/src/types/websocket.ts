import type { AppConfig, RunEvent } from "./models";

export type ClientMessage =
  | { type: "start_task"; prompt: string }
  | { type: "cancel_task"; task_id: string }
  | { type: "update_config"; updates: { template?: string } };

export type ServerMessage =
  | { type: "run_event"; task_id: string; event: RunEvent }
  | { type: "run_cancelled"; task_id: string }
  | { type: "run_failed"; task_id: string; error: string }
  | { type: "config_updated"; config: AppConfig }
  | { type: "error"; content: string };
