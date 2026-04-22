"""Textual TUI 主界面。

布局：
┌───────────┬────────────────────────────┬──────────────┐
│ Agents    │ 会话流                     │ 交付件树     │
│ (左面板)   │                            │ (右面板)      │
│           ├────────────────────────────┤              │
│           │ 任务输入框 [Ctrl+Enter 发送] │              │
└───────────┴────────────────────────────┴──────────────┘
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import yaml
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TextArea,
)

from .config_models import AgentConfig, AppConfig
from .orchestrator import AgentMessage
from .run_events import RunEvent
from .run_service import RunService
from .settings_loader import default_model_config, model_from_claude_settings
from .templates import describe_templates, instantiate_template


AGENT_COLORS = ["cyan", "magenta", "green", "yellow", "blue", "red", "bright_cyan"]


def _color_for(index: int) -> str:
    return AGENT_COLORS[index % len(AGENT_COLORS)]


class AgentEditScreen(ModalScreen[Optional[AgentConfig]]):
    """编辑/新建单个 Agent 的弹窗。"""

    BINDINGS = [Binding("escape", "cancel", "取消")]

    DEFAULT_CSS = """
    AgentEditScreen { align: center middle; }
    #edit-box { width: 80%; height: 80%; border: round $accent; padding: 1 2; background: $panel; }
    #edit-box Input, #edit-box TextArea { margin-bottom: 1; }
    #edit-buttons { height: 3; align-horizontal: right; }
    #edit-buttons Button { margin-left: 1; }
    """

    def __init__(self, agent: Optional[AgentConfig] = None):
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        a = self.agent
        with Vertical(id="edit-box"):
            yield Label("[b]编辑 Agent[/b]" if a else "[b]新建 Agent[/b]")
            yield Label("名称 (name)")
            yield Input(value=a.name if a else "", id="f-name", placeholder="例如 PM")
            yield Label("角色 (role)")
            yield Input(value=a.role if a else "", id="f-role", placeholder="例如 产品经理")
            yield Label("工作目录 (workspace, 相对路径，留空用 name)")
            yield Input(value=(a.workspace or "") if a else "", id="f-ws")
            yield Label("模型 key (留空用默认)")
            yield Input(value=(a.model or "") if a else "", id="f-model")
            yield Label("System Prompt")
            yield TextArea(
                text=a.system_prompt if a else "",
                id="f-prompt",
                show_line_numbers=False,
            )
            with Horizontal(id="edit-buttons"):
                yield Button("取消", id="btn-cancel")
                yield Button("保存", id="btn-save", variant="primary")

    @on(Button.Pressed, "#btn-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def _save(self) -> None:
        name = self.query_one("#f-name", Input).value.strip()
        if not name:
            self.app.bell()
            return
        prompt = self.query_one("#f-prompt", TextArea).text.strip() or "你是一位有用的助手。"
        ws = self.query_one("#f-ws", Input).value.strip() or None
        model = self.query_one("#f-model", Input).value.strip() or None
        role = self.query_one("#f-role", Input).value.strip()
        self.dismiss(AgentConfig(
            name=name,
            role=role,
            system_prompt=prompt,
            workspace=ws,
            model=model,
        ))


class TemplatePickerScreen(ModalScreen[Optional[str]]):
    BINDINGS = [Binding("escape", "cancel", "取消")]

    DEFAULT_CSS = """
    TemplatePickerScreen { align: center middle; }
    #tpl-box { width: 70%; height: 60%; border: round $accent; padding: 1 2; background: $panel; }
    ListView { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="tpl-box"):
            yield Label("[b]选择协作模板[/b]（Enter 确认，Esc 取消）")
            items = [
                ListItem(Label(f"[b]{name}[/b]  —  {desc}"), id=f"tpl-{name}")
                for name, desc in describe_templates()
            ]
            yield ListView(*items, id="tpl-list")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(ListView.Selected)
    def _selected(self, ev: ListView.Selected) -> None:
        if ev.item and ev.item.id:
            self.dismiss(ev.item.id.removeprefix("tpl-"))


class ProjectSettingsScreen(ModalScreen[Optional[AppConfig]]):
    BINDINGS = [Binding("escape", "cancel", "取消")]

    DEFAULT_CSS = """
    ProjectSettingsScreen { align: center middle; }
    #settings-box { width: 88%; height: 88%; border: round $accent; padding: 1 2; background: $panel; }
    #settings-box Input, #settings-box TextArea { margin-bottom: 1; }
    #model-helpers { height: auto; margin-bottom: 1; }
    #model-helpers Button { width: 1fr; margin-right: 1; }
    #settings-buttons { height: 3; align-horizontal: right; }
    #settings-buttons Button { margin-left: 1; }
    """

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        cfg = self.config
        models_yaml = yaml.safe_dump(
            {k: v.model_dump(exclude_none=True) for k, v in cfg.models.items()},
            allow_unicode=True,
            sort_keys=False,
            indent=2,
        ).strip()
        with Vertical(id="settings-box"):
            yield Label("[b]项目设置[/b]")
            yield Label("项目名")
            yield Input(value=cfg.project_name, id="project-name")
            yield Label("工作空间根目录")
            yield Input(value=cfg.workspace_root, id="workspace-root")
            yield Label("默认模型 key")
            yield Input(value=cfg.default_model, id="default-model")
            yield Label("编排模式 (round_robin / selector / single)")
            yield Input(value=cfg.workflow.mode, id="workflow-mode")
            yield Label("最大轮次")
            yield Input(value=str(cfg.workflow.max_turns), id="workflow-turns")
            yield Label("终止关键词（逗号分隔）")
            yield Input(value=", ".join(cfg.workflow.termination_keywords), id="workflow-terms")
            yield Label("Selector Prompt（selector 模式可选）")
            yield TextArea(
                text=cfg.workflow.selector_prompt or "",
                id="selector-prompt",
                show_line_numbers=False,
            )
            yield Label("模型配置 YAML（key -> ModelConfig）")
            with Horizontal(id="model-helpers"):
                yield Button("Claude 默认", id="btn-model-claude")
                yield Button("OpenAI 默认", id="btn-model-openai")
                yield Button("兼容端点模板", id="btn-model-compatible")
            yield TextArea(text=models_yaml, id="models-yaml", show_line_numbers=True)
            with Horizontal(id="settings-buttons"):
                yield Button("取消", id="settings-cancel")
                yield Button("保存", id="settings-save", variant="primary")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#settings-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-model-claude")
    def _fill_claude_model(self) -> None:
        model = model_from_claude_settings() or default_model_config()
        self._replace_models_yaml({
            "default": model.model_dump(exclude_none=True),
        })
        self.query_one("#default-model", Input).value = "default"

    @on(Button.Pressed, "#btn-model-openai")
    def _fill_openai_model(self) -> None:
        self._replace_models_yaml({
            "default": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "base_url": None,
            }
        })
        self.query_one("#default-model", Input).value = "default"

    @on(Button.Pressed, "#btn-model-compatible")
    def _fill_compatible_model(self) -> None:
        self._replace_models_yaml({
            "default": {
                "provider": "openai_compatible",
                "model": "your-model-name",
                "base_url": "https://api.example.com/v1",
                "api_key": "YOUR_API_KEY",
            }
        })
        self.query_one("#default-model", Input).value = "default"

    def _replace_models_yaml(self, data: dict) -> None:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, indent=2).strip()
        self.query_one("#models-yaml", TextArea).text = text

    @on(Button.Pressed, "#settings-save")
    def _save(self) -> None:
        try:
            project_name = self.query_one("#project-name", Input).value.strip() or "m-agent"
            workspace_root = self.query_one("#workspace-root", Input).value.strip() or "deliverables"
            default_model = self.query_one("#default-model", Input).value.strip() or "default"
            mode = self.query_one("#workflow-mode", Input).value.strip() or "round_robin"
            max_turns = int(self.query_one("#workflow-turns", Input).value.strip() or "12")
            termination_keywords = [
                item.strip()
                for item in self.query_one("#workflow-terms", Input).value.split(",")
                if item.strip()
            ] or ["TERMINATE"]
            selector_prompt = self.query_one("#selector-prompt", TextArea).text.strip() or None
            models_text = self.query_one("#models-yaml", TextArea).text.strip()
            models_data = yaml.safe_load(models_text) if models_text else {}
            updated = self.config.model_copy(deep=True)
            updated.project_name = project_name
            updated.workspace_root = workspace_root
            updated.default_model = default_model
            updated.workflow.mode = mode  # type: ignore[assignment]
            updated.workflow.max_turns = max_turns
            updated.workflow.termination_keywords = termination_keywords
            updated.workflow.selector_prompt = selector_prompt
            updated.models = models_data or {}
            updated = AppConfig.model_validate(updated.model_dump())
        except Exception as exc:
            if hasattr(self.app, "notify"):
                self.app.notify(f"保存失败: {exc}", severity="error")
            self.app.bell()
            return
        self.dismiss(updated)


class AgentPanel(VerticalScroll):
    """左侧 Agent 列表 + 操作按钮。"""

    DEFAULT_CSS = """
    AgentPanel { width: 28; border-right: solid $primary; padding: 0 1; }
    AgentPanel #agent-list { height: 1fr; margin-bottom: 1; }
    AgentPanel .agent-item { height: auto; }
    AgentPanel #agent-actions { height: auto; }
    AgentPanel #agent-actions Button { width: 1fr; margin-bottom: 1; }
    """


class ChatLog(VerticalScroll):
    DEFAULT_CSS = """
    ChatLog { padding: 0 1; }
    ChatLog .msg { margin-bottom: 1; }
    """


class MAgentApp(App):
    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #center { width: 1fr; }
    #input-row { height: 5; border-top: solid $primary; padding: 0 1; }
    #task-input { height: 3; }
    #workspace { width: 36; border-left: solid $primary; padding: 0 1; }
    #status { dock: bottom; height: 1; background: $boost; color: $text; padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+n", "new_session", "新会话"),
        Binding("ctrl+s", "save_config", "保存"),
        Binding("ctrl+p", "edit_project", "项目设置"),
        Binding("ctrl+t", "pick_template", "模板"),
        Binding("ctrl+a", "add_agent", "+Agent"),
        Binding("ctrl+e", "open_workspace", "交付件"),
    ]

    status_text: reactive[str] = reactive("就绪")

    def __init__(self, config: AppConfig, config_path: Optional[Path] = None):
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.title = f"magent-tui · {config.project_name}"
        self._running: bool = False
        self._selected_agent_index: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            yield AgentPanel(id="agent-panel")
            with Vertical(id="center"):
                yield ChatLog(id="chat-log")
                with Vertical(id="input-row"):
                    yield Input(
                        placeholder="输入任务描述，回车发送  (Ctrl+P 项目 / Ctrl+T 模板 / Ctrl+A Agent / Ctrl+E 交付件)",
                        id="task-input",
                    )
            with Vertical(id="workspace"):
                yield Label("[b]交付件[/b]")
                yield DirectoryTree(str(self.config.ensure_workspace()), id="ws-tree")
        yield Static(self.status_text, id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_agents()
        self._log_system(
            f"欢迎使用 magent-tui · 项目 [b]{self.config.project_name}[/b]\n"
            f"当前 Agent 数: {len(self.config.agents)}，编排模式: {self.config.workflow.mode}\n"
            f"工作空间: {Path(self.config.workspace_root).resolve()}"
        )

    # ---------------- rendering ----------------

    def _render_agents(self) -> None:
        panel = self.query_one(AgentPanel)
        panel.remove_children()
        panel.mount(Label("[b]Agents[/b]"))
        if not self.config.agents:
            panel.mount(Static("[dim]还没有 Agent。按 Ctrl+T 选模板，或 Ctrl+A 新建。[/dim]"))
        else:
            items = []
            for idx, a in enumerate(self.config.agents):
                color = _color_for(idx)
                items.append(
                    ListItem(
                        Label(
                            f"[{color}]●[/{color}] [b]{a.name}[/b] [dim]{a.role or '未命名角色'}[/dim]\n"
                            f"[dim]model: {self.config.model_name_for_agent(a)} | ws: {a.resolved_workspace()}[/dim]"
                        ),
                        id=f"agent-{idx}",
                        classes="agent-item",
                    )
                )
            agent_list = ListView(*items, id="agent-list")
            panel.mount(agent_list)
            self._selected_agent_index = max(0, min(self._selected_agent_index, len(self.config.agents) - 1))
            self.call_after_refresh(lambda: setattr(agent_list, "index", self._selected_agent_index))
        panel.mount(
            Vertical(
                Button("+模板", id="btn-tpl", variant="primary"),
                Button("+Agent", id="btn-add"),
                Button("项目", id="btn-project"),
                Button("编辑", id="btn-edit"),
                Button("删除", id="btn-del"),
                Button("清空", id="btn-clear"),
                id="agent-actions",
            )
        )

    def _log_message(self, msg: AgentMessage) -> None:
        log = self.query_one(ChatLog)
        idx = next((i for i, a in enumerate(self.config.agents) if a.name == msg.agent), -1)
        color = _color_for(idx) if idx >= 0 else "white"
        header = Text()
        header.append(f"● {msg.agent}", style=f"bold {color}")
        if msg.role:
            header.append(f"  ({msg.role})", style="dim")
        panel = Panel(Markdown(msg.content or ""), title=header, border_style=color)
        log.mount(Static(panel, classes="msg"))
        log.scroll_end(animate=False)

    def _log_system(self, text: str) -> None:
        log = self.query_one(ChatLog)
        log.mount(Static(Panel(Markdown(text), title="系统", border_style="grey50"), classes="msg"))
        log.scroll_end(animate=False)

    def watch_status_text(self, value: str) -> None:
        try:
            self.query_one("#status", Static).update(value)
        except Exception:
            pass

    # ---------------- actions ----------------

    @on(Button.Pressed, "#btn-tpl")
    def _btn_tpl(self) -> None:
        self.action_pick_template()

    @on(Button.Pressed, "#btn-add")
    def _btn_add(self) -> None:
        self.action_add_agent()

    @on(Button.Pressed, "#btn-clear")
    def _btn_clear(self) -> None:
        self.config.agents = []
        self._selected_agent_index = 0
        self._render_agents()
        self.status_text = "已清空 Agent"

    @on(Button.Pressed, "#btn-project")
    def _btn_project(self) -> None:
        self.action_edit_project()

    @on(Button.Pressed, "#btn-edit")
    def _btn_edit(self) -> None:
        self.action_edit_agent()

    @on(Button.Pressed, "#btn-del")
    def _btn_del(self) -> None:
        self.action_delete_agent()

    @on(ListView.Selected, "#agent-list")
    def _selected_agent(self, ev: ListView.Selected) -> None:
        if ev.item and ev.item.id:
            self._selected_agent_index = int(ev.item.id.removeprefix("agent-"))
            agent = self.config.agents[self._selected_agent_index]
            self.status_text = f"当前 Agent: {agent.name}"

    def action_pick_template(self) -> None:
        def _cb(name: Optional[str]) -> None:
            if not name:
                return
            self.config.agents = instantiate_template(name)
            self._selected_agent_index = 0
            self.config.ensure_workspace()
            self._render_agents()
            self._refresh_tree()
            self.status_text = f"已导入模板: {name}"
            self._log_system(f"已导入模板 **{name}**，共 {len(self.config.agents)} 个 Agent。")

        self.push_screen(TemplatePickerScreen(), _cb)

    def action_add_agent(self) -> None:
        def _cb(agent: Optional[AgentConfig]) -> None:
            if not agent:
                return
            self.config.agents.append(agent)
            self._selected_agent_index = len(self.config.agents) - 1
            self.config.ensure_workspace()
            self._render_agents()
            self._refresh_tree()
            self.status_text = f"新增 Agent: {agent.name}"

        self.push_screen(AgentEditScreen(), _cb)

    def action_edit_agent(self) -> None:
        if not self.config.agents:
            self.status_text = "没有可编辑的 Agent"
            return
        agent = self.config.agents[self._selected_agent_index]

        def _cb(updated: Optional[AgentConfig]) -> None:
            if not updated:
                return
            self.config.agents[self._selected_agent_index] = updated
            self.config.ensure_workspace()
            self._render_agents()
            self._refresh_tree()
            self.status_text = f"已更新 Agent: {updated.name}"

        self.push_screen(AgentEditScreen(agent), _cb)

    def action_delete_agent(self) -> None:
        if not self.config.agents:
            self.status_text = "没有可删除的 Agent"
            return
        removed = self.config.agents.pop(self._selected_agent_index)
        if self.config.agents:
            self._selected_agent_index = min(self._selected_agent_index, len(self.config.agents) - 1)
        else:
            self._selected_agent_index = 0
        self._render_agents()
        self._refresh_tree()
        self.status_text = f"已删除 Agent: {removed.name}"

    def action_save_config(self) -> None:
        path = self.config_path or Path("configs") / "current.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.config.to_yaml(path)
        self.status_text = f"已保存到 {path}"

    def action_edit_project(self) -> None:
        def _cb(updated: Optional[AppConfig]) -> None:
            if not updated:
                return
            self.config = updated
            self.title = f"magent-tui · {self.config.project_name}"
            self.config.ensure_workspace()
            self._render_agents()
            self._refresh_tree()
            self.status_text = "已更新项目设置"
            self._log_system(
                f"已更新项目设置：项目 [b]{self.config.project_name}[/b]，"
                f"编排 [b]{self.config.workflow.mode}[/b]，默认模型 [b]{self.config.default_model}[/b]。"
            )

        self.push_screen(ProjectSettingsScreen(self.config), _cb)

    def action_new_session(self) -> None:
        self.query_one(ChatLog).remove_children()
        self._log_system("🆕 新会话开始。")
        self.status_text = "新会话"

    def action_open_workspace(self) -> None:
        self._refresh_tree()
        self.status_text = f"工作空间: {Path(self.config.workspace_root).resolve()}"

    def _refresh_tree(self) -> None:
        try:
            tree = self.query_one("#ws-tree", DirectoryTree)
            tree.path = str(self.config.ensure_workspace())
            tree.reload()
        except Exception:
            pass

    # ---------------- run ----------------

    @on(Input.Submitted, "#task-input")
    def _submit_task(self, ev: Input.Submitted) -> None:
        task = (ev.value or "").strip()
        if not task:
            return
        if self._running:
            self.status_text = "当前任务仍在运行中..."
            return
        if not self.config.agents:
            self._log_system("⚠ 还没有 Agent，请先导入模板 (Ctrl+T) 或新建 (Ctrl+A)。")
            return
        ev.input.value = ""
        self._run_task(task)

    @work(exclusive=True)
    async def _run_task(self, task: str) -> None:
        self._running = True
        self.status_text = "运行中..."
        self._log_system(f"📋 **任务**: {task}")
        service = RunService(self.config)
        try:
            async for event in service.run(task):
                self._consume_event(event)
                await asyncio.sleep(0)
            self._refresh_tree()
            self.status_text = "✓ 完成"
        except Exception as e:
            self._log_system(f"❌ 运行出错: `{e}`")
            self.status_text = "运行出错"
        finally:
            self._running = False

    def _consume_event(self, event: RunEvent) -> None:
        if event.event_type == "run_started":
            run_dir = event.metadata.get("run_dir")
            if run_dir:
                self._log_system(f"🗂 本次运行目录: `{run_dir}`")
            return
        if event.event_type == "run_completed":
            return
        if event.event_type == "run_failed":
            self._log_system(f"❌ RunService 失败: `{event.content or ''}`")
            return
        if event.event_type != "agent_message":
            return
        msg = AgentMessage(
            agent=event.agent or "system",
            role=event.role or "system",
            content=event.content or "",
            final=bool(event.metadata.get("final")),
        )
        if msg.agent == "system":
            self._log_system(msg.content)
        else:
            self._log_message(msg)


def run_app(config: AppConfig, config_path: Optional[Path] = None) -> None:
    MAgentApp(config, config_path).run()
