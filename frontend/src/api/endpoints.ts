import { apiGet, apiPost, apiPut, apiDelete } from "./client";
import type {
  AppConfig,
  AgentConfig,
  Template,
  WorkspaceEntry,
  FileContent,
  Task,
  RunEvent,
  RunSummary,
  DoctorCheck,
} from "@/types";

export interface ConfigUpdateRequest {
  project_name?: string;
  workspace_root?: string;
  workflow_mode?: string;
  max_turns?: number;
}

export interface AgentAddRequest {
  name: string;
  role?: string;
  system_prompt: string;
  workspace?: string;
  model?: string;
}

export const api = {
  // Config
  getConfig: () => apiGet<AppConfig>("/api/config"),
  updateConfig: (req: ConfigUpdateRequest) => apiPut<AppConfig>("/api/config", req),

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

  // Doctor
  runDoctor: () => apiGet<DoctorCheck[]>("/api/doctor"),

  // Runs
  listRuns: () => apiGet<RunSummary[]>("/api/runs"),
  getRunEvents: (runId: string) => apiGet<RunEvent[]>(`/api/runs/${runId}/events`),
};
