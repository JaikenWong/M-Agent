import { apiGet, apiPost, apiPut, apiDelete } from "./client";
import type {
  AppConfig,
  AgentConfig,
  Provider,
  Template,
  WorkspaceEntry,
  FileContent,
  Task,
  RunEvent,
  RunSummary,
  RunDetail,
  DoctorCheck,
} from "@/types";

export interface ConfigUpdateRequest {
  project_name?: string;
  workspace_root?: string;
  workflow_mode?: string;
  max_turns?: number;
  use_claude_code_settings?: boolean;
  default_model?: string;
}

export interface AgentAddRequest {
  name: string;
  role?: string;
  system_prompt: string;
  workspace?: string;
  model?: string;
}

/** 编辑/新增 model；空字符串视为清空，让运行时回退到合并 Claude settings 或环境变量。 */
export interface ModelUpsertRequest {
  provider?: Provider;
  model?: string;
  api_key?: string;
  base_url?: string;
  temperature?: number;
  max_tokens?: number;
}

export const api = {
  // Config
  getConfig: () => apiGet<AppConfig>("/api/config"),
  updateConfig: (req: ConfigUpdateRequest) => apiPut<AppConfig>("/api/config", req),
  upsertModel: (key: string, req: ModelUpsertRequest) =>
    apiPut<AppConfig>(`/api/models/${encodeURIComponent(key)}`, req),
  deleteModel: (key: string) =>
    apiDelete<AppConfig>(`/api/models/${encodeURIComponent(key)}`),

  // Templates
  listTemplates: () => apiGet<Template[]>("/api/templates"),
  applyTemplate: (name: string) =>
    apiPost<{ applied: string; agent_count: number }>(`/api/templates/${name}/apply`),

  // Agents
  listAgents: () => apiGet<AgentConfig[]>("/api/agents"),
  addAgent: (req: AgentAddRequest) => apiPost<AgentConfig>("/api/agents", req),
  deleteAgent: (index: number) => apiDelete<{ deleted: string }>(`/api/agents/${index}`),

  // Workspace
  getWorkspaceTree: (path = ".") =>
    apiGet<{ path: string; entries: WorkspaceEntry[] }>("/api/workspace/tree", { path }),
  getWorkspaceFile: (path: string) =>
    apiGet<FileContent>("/api/workspace/file", { path }),

  // Tasks
  listTasks: () => apiGet<Task[]>("/api/tasks"),
  getTask: (taskId: string) => apiGet<Task>(`/api/tasks/${taskId}`),
  cancelTask: (taskId: string) => apiPost<{ cancelled: string }>(`/api/tasks/${taskId}/cancel`),
  deleteTask: (taskId: string) => apiDelete<{ deleted: string }>(`/api/tasks/${taskId}`),

  // Doctor
  runDoctor: () => apiGet<DoctorCheck[]>("/api/doctor"),

  // Runs
  listRuns: () => apiGet<RunSummary[]>("/api/runs"),
  getRunEvents: (runId: string) => apiGet<RunEvent[]>(`/api/runs/${runId}/events`),
  getRunDetail: (runId: string) => apiGet<RunDetail>(`/api/runs/${runId}/detail`),
  deleteRun: (runId: string) => apiDelete<{ deleted: string }>(`/api/runs/${runId}`),
};
