# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
# TUI 模式
magent-tui run --config configs/default.yaml

# 无头模式 — 直接执行任务
magent-tui run --task "帮我写一个用户注册系统的PRD"

# 指定模板
magent-tui run --template dev_team_oob --task "设计微服务架构"

# 其他命令
magent-tui init --template dev_team_oob -o configs/my.yaml
magent-tui templates
magent-tui doctor
```

## Test

```bash
# 全部测试
python -m unittest discover -s tests -p "test_*.py"

# 单个测试文件
python -m unittest tests.test_run_service

# 单个测试方法
python -m unittest tests.test_pipeline_gate.PipelineGateTest.test_missing_artifact_fails
```

测试使用 `unittest.IsolatedAsyncioTestCase`，无 pytest 依赖。

## Architecture

```
AppConfig (config_models.py)
  ├── models: Dict[str, ModelConfig]  (provider, model, api_key, base_url)
  ├── agents: List[AgentConfig]       (name, role, system_prompt, workspace, tools)
  └── workflow: WorkflowConfig        (mode, max_turns, required_artifacts)

RunService (run_service.py)           — async iterator yielding RunEvent
  └── OrchestratorBase (orchestrator.py)
      ├── MockOrchestrator      — demo fallback, no API needed
      └── AutoGenOrchestrator   — real AutoGen agents with workspace tools
              ├── RoundRobinGroupChat / SelectorGroupChat (round_robin, selector)
              ├── _run_pipeline()     (pipeline mode — artifact gating)
              └── _run_single()       (single mode)

MAgentTabApp (tab_app.py)        — 5-tab TUI
  ├── Chat        — agent status bar, markdown messages, task input
  ├── Agents      — list, add/edit/delete, template import
  ├── Deliverables — directory tree + file preview
  ├── Config      — project settings, model detection
  └── History     — task list, session replay

TaskManager (task_state.py)      — in-memory task queue with JSON persistence
  └── States: todo → pending → running ↔ input_required → done | failed | cancelled

FastAPI Server (server.py)       — REST + WebSocket for web/desktop frontends
  └── Endpoints: /api/config, /api/models, /api/agents, /api/templates,
      /api/workspace, /api/tasks, /api/doctor, /api/runs
  └── WebSocket /ws: start_task, cancel_task, update_config → run_event broadcast

Frontend (frontend/)             — React 18 + TypeScript + Vite + Tailwind CSS
  └── Tauri 2 desktop app (frontend/src-tauri/)
  └── State: Zustand stores (configStore, runStore, runListStore)
  └── WebSocket client: frontend/src/ws/
```

### Data Flow

1. User submits task via TUI or `--task` CLI flag
2. `RunService.run(task)` creates `RunArtifacts` dir under `workspace_root/runs/<timestamp>/`
3. `build_orchestrator(config)` selects MockOrchestrator (no API key / missing autogen) or AutoGenOrchestrator
4. Orchestrator yields agent messages → `RunService` wraps as `RunEvent` (run_events.py)
5. Events stream to TUI chat panel + persisted to `events.jsonl` + `transcript.jsonl`
6. Each agent writes output via sandboxed workspace tools (`workspace_tools.py`) to `deliverables/<agent-name>/`

### Workflow Modes

| Mode | Description |
|------|-------------|
| `round_robin` | Fixed-turn agent rotation (default) |
| `selector` | LLM selects next speaker |
| `single` | Single agent execution |
| `pipeline` | Sequential with artifact gating + predecessor file references |

### Config Fallback Chain

1. Project YAML config (`--config`)
2. Claude Code `settings.json` (`~/.claude/settings.json`)
3. Env vars: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `OPENAI_API_KEY`

Provider auto-detection: if `base_url` doesn't contain `anthropic.com`, switches to `openai_compatible`.

### Run Artifacts Layout

```
workspace_root/runs/YYYYMMDD-HHMMSS/
  run.json          — metadata (project, workflow, started_at)
  task.md           — user prompt
  summary.md        — run summary
  events.jsonl      — structured event stream
  transcript.jsonl  — message stream (ArtifactRecord per line)
```

## Frontend

```bash
cd frontend
npm install
npm run dev           # Vite dev server
npm run tauri:dev     # Tauri desktop dev
npm run tauri:build   # Tauri production build
```

Frontend connects to FastAPI backend via REST (`/api/*`) and WebSocket (`/ws`).
Tauri Rust side (`src-tauri/`) manages server lifecycle — starts/stops FastAPI process.

## Server Mode

```bash
magent-tui serve                          # localhost:8765
magent-tui serve --host 0.0.0.0 --port 8765 --config configs/default.yaml
```

WebSocket message types (client → server): `start_task`, `cancel_task`, `update_config`
WebSocket broadcast types (server → client): `run_event`, `run_cancelled`, `run_failed`, `config_updated`

## Key Conventions

- **Source layout**: all code under `src/magent_tui/`
- **UI language is Chinese**: agent names, system prompts, template keys in Chinese
- **Workspace convention**: each agent gets a subdirectory under `workspace_root` (default: `deliverables/`)
- **Model providers**: `anthropic` (via `autogen-ext[anthropic]`), `openai` / `openai_compatible` (via `autogen-ext[openai]`)
- **Orchestrator factory**: `build_orchestrator(config)` in orchestrator.py — always use this, never construct directly
- **Agent tools**: `workspace_tools.py` provides `write_text_file`, `append_text_file`, `read_text_file`, `list_workspace_files`; `claude_agent.py` adds Claude Agent SDK integration (Read/Write/Edit/Bash/Grep/Glob) — enable per-agent via `tools: ["claude_agent"]` in config
- **Templates**: `templates.py` — built-in templates (dev_team_oob, product_sprint, content_factory, dev_delivery, research_squad, code_review, debate); apply via CLI `init --template` or API `POST /api/templates/{name}/apply`

## Not Yet Implemented

- Human-in-the-loop `INPUT_REQUIRED` UI flow
- Streaming message rendering (currently waits for full message)
- Agent tool call visualization in chat
- Run resumption after interruption
- LiteLLM client wiring (optional dep exists, not connected in `_build_model_client()`)
