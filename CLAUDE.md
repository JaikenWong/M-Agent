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
  ├── agents: List[AgentConfig]       (name, role, system_prompt, workspace)
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

## Key Conventions

- **Source layout**: all code under `src/magent_tui/`
- **UI language is Chinese**: agent names, system prompts, template keys in Chinese
- **Workspace convention**: each agent gets a subdirectory under `workspace_root` (default: `deliverables/`)
- **Model providers**: `anthropic` (via `autogen-ext[anthropic]`), `openai` / `openai_compatible` (via `autogen-ext[openai]`)
- **Orchestrator factory**: `build_orchestrator(config)` in orchestrator.py — always use this, never construct directly

## Not Yet Implemented

- Human-in-the-loop `INPUT_REQUIRED` UI flow
- Streaming message rendering (currently waits for full message)
- Agent tool call visualization in chat
- Run resumption after interruption
- LiteLLM client wiring (optional dep exists, not connected in `_build_model_client()`)
