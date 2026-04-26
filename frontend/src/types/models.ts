export type Provider = "anthropic" | "openai" | "openai_compatible" | "litellm";

/** 后端不会回传 api_key 原文，只返回 source / present；UI 据此显示「已合并自 Claude / 本配置 / 环境变量 / 未设」 */
export type CredentialSource = "config" | "claude_settings" | "env" | "none";

export interface ModelConfig {
  provider: Provider;
  model: string;
  api_key?: string | null;
  base_url?: string | null;
  temperature: number;
  max_tokens?: number | null;
  extra: Record<string, unknown>;
  /** 是否已解析到可用 api_key（包含来自 Claude settings 与 env 的） */
  resolved_api_key_present?: boolean;
  resolved_api_key_source?: CredentialSource;
  resolved_base_url?: string | null;
  resolved_base_url_source?: CredentialSource;
}

export interface AgentConfig {
  name: string;
  role: string;
  system_prompt: string;
  model?: string | null;
  workspace?: string | null;
  tools: string[];
  description: string;
}

export type WorkflowMode = "round_robin" | "selector" | "single" | "pipeline";

export interface WorkflowConfig {
  mode: WorkflowMode;
  max_turns: number;
  termination_keywords: string[];
  selector_prompt?: string | null;
  required_artifacts: Record<string, string[]>;
  /** 对用户的总接口，须与某 Agent 的 name 一致（如 PM）；约定谁面向用户汇报，不改编排 */
  liaison_agent?: string | null;
}

export interface AppConfig {
  project_name: string;
  workspace_root: string;
  /**
   * true：合并 ~/.claude 等与 Claude Code 一致的 settings 到 models
   * false：仅用 YAML + 环境变量
   */
  use_claude_code_settings?: boolean;
  default_model: string;
  models: Record<string, ModelConfig>;
  agents: AgentConfig[];
  workflow: WorkflowConfig;
}

export type TaskStatus =
  | "todo"
  | "pending"
  | "running"
  | "input_required"
  | "done"
  | "failed"
  | "cancelled";

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "待执行",
  pending: "排队中",
  running: "运行中",
  input_required: "需要确认",
  done: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  todo: "text-gray-400",
  pending: "text-yellow-400",
  running: "text-blue-400",
  input_required: "text-orange-400",
  done: "text-green-400",
  failed: "text-red-400",
  cancelled: "text-gray-500",
};

export interface Task {
  id: string;
  name: string;
  prompt: string;
  status: TaskStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  attention_requested_at: string | null;
  run_dir: string | null;
  metadata: Record<string, unknown>;
  error_message: string | null;
}

export type RunEventType =
  | "run_started"
  | "run_state_changed"
  | "agent_message"
  | "run_completed"
  | "run_failed";

export interface RunEvent {
  event_type: RunEventType;
  run_id: string;
  timestamp: string;
  agent?: string | null;
  role?: string | null;
  content?: string | null;
  metadata: Record<string, unknown>;
}

export interface DoctorCheck {
  label: string;
  ok: boolean;
  detail: string;
}

export interface Template {
  name: string;
  description: string;
}

export interface WorkspaceEntry {
  path: string;
  is_dir: boolean;
  size: number;
}

export interface FileContent {
  path: string;
  content: string;
}

export interface RunSummary {
  run_id: string;
  project: string;
  workflow: string;
  started_at: string;
  run_dir: string;
}

export interface RunDetail {
  run_id: string;
  project: string;
  workflow: string;
  started_at: string;
  task_content: string | null;
  summary_content: string | null;
}

// Agent color palette matching TUI convention
export const AGENT_COLORS = [
  "text-cyan-400",
  "text-pink-400",
  "text-green-400",
  "text-yellow-400",
  "text-blue-400",
  "text-red-400",
  "text-cyan-300",
  "text-purple-400",
  "text-orange-400",
  "text-teal-400",
] as const;

export const AGENT_BG_COLORS = [
  "bg-cyan-400",
  "bg-pink-400",
  "bg-green-400",
  "bg-yellow-400",
  "bg-blue-400",
  "bg-red-400",
  "bg-cyan-300",
  "bg-purple-400",
  "bg-orange-400",
  "bg-teal-400",
] as const;
