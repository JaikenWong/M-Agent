# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run with: `magent-tui --config configs/default.yaml` (entry point `magent_tui.main:main` — not yet implemented).

## Project State

This project is in early scaffold stage. Only the configuration layer and template library are implemented. The following are **not yet built**: TUI (Textual), AutoGen orchestration (`RoundRobinGroupChat` + `AssistantAgent`), YAML config loading, Claude Code `settings.json` fallback, and the `main.py` entry point.

## Architecture

Four designed layers:

1. **Configuration layer** (`config_models.py`) — Pydantic models: `ModelConfig` → `AgentConfig` → `WorkflowConfig` → `AppConfig`. `AppConfig.ensure_workspace()` auto-creates per-agent deliverable directories under `workspace_root`.
2. **Template layer** (`templates.py` + `__init__.py`) — `TEMPLATE_LIBRARY` dict maps template names to pre-built `list[AgentConfig]`. Use `instantiate_template(name)` to get deep-copied agent configs; `template_names()` lists available keys.
3. **Orchestration layer** (unimplemented) — Designed to use AutoGen `RoundRobinGroupChat` with `AssistantAgent` instances.
4. **Model compatibility layer** (unimplemented) — Designed to use `LiteLLMChatCompletionClient` from `autogen-ext[litellm]` for multi-provider support.

## Key Conventions

- **Source layout**: all code lives under `src/magent_tui/` (setuptools `package-dir` config).
- **UI language is Chinese**: agent names, system prompts, and template keys are in Chinese. Keep new agent content in Chinese.
- **Config fallback chain**: project YAML config → Claude Code `settings.json` → env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
- **Workspace convention**: each agent gets a subdirectory under `workspace_root` (default: `deliverables/`), specified by `AgentConfig.workspace`.

## Dependencies

| Package | Role |
|---|---|
| `autogen-agentchat` | Multi-agent orchestration |
| `autogen-ext[litellm]` | LiteLLM model client for cross-provider LLM access |
| `pydantic` | Config/validation models |
| `pyyaml` | YAML config file parsing |
| `textual` | Terminal UI framework |

## Built-in Templates

- `product_sprint` — 5 agents: PM / Research Analyst / Architect / Engineer / QA
- `content_factory` — 5 agents: Planner / Research / Writer / Editor / Distribution
- `dev_delivery` — 4 agents: Requirements / Implementation / Testing / Docs
