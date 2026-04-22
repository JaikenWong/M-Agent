"""Tab 化 Textual TUI 主界面。"""

from __future__ import annotations

import asyncio
import os
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
    TabPane,
    TabbedContent,
    TextArea,
)

from .config_models import AgentConfig, AppConfig
from .orchestrator import AgentMessage
from .run_events import RunEvent
from .run_service import RunService
from .settings_loader import default_model_config, find_claude_settings, model_from_claude_settings
from .templates import describe_templates, instantiate_template

AGENT_COLORS = ["cyan", "magenta", "green", "yellow", "blue", "red", "bright_cyan"]


def _color_for(index: int) -> str:
    return AGENT_COLORS[index % len(AGENT_COLORS)]


class AgentEditScreen(ModalScreen[Optional[AgentConfig]]):
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
            yield TextArea(text=a.system_prompt if a else "", id="f-prompt", show_line_numbers=False)
            with Horizontal(id="edit-buttons"):
                yield Button("取消", id="btn-cancel")
                yield Button("保存", id="btn-save", variant="primary")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-cancel")
    def _cancel(self) -> None:
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
        self.dismiss(
            AgentConfig(
                name=name,
                role=role,
                system_prompt=prompt,
                workspace=ws,
                model=model,
            )
        )


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
            items = [ListItem(Label(f"[b]{name}[/b]  —  {desc}"), id=f"tpl-{name}") for name, desc in describe_templates()]
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
            yield Label("编排模式 (round_robin / selector / single / pipeline)")
            yield Input(value=cfg.workflow.mode, id="workflow-mode")
            yield Label("最大轮次")
            yield Input(value=str(cfg.workflow.max_turns), id="workflow-turns")
            yield Label("终止关键词（逗号分隔）")
            yield Input(value=", ".join(cfg.workflow.termination_keywords), id="workflow-terms")
            yield Label("Selector Prompt（selector 模式可选）")
            yield TextArea(text=cfg.workflow.selector_prompt or "", id="selector-prompt", show_line_numbers=False)
            yield Label("required_artifacts YAML（pipeline 门禁）")
            required_text = yaml.safe_dump(cfg.workflow.required_artifacts or {}, allow_unicode=True, sort_keys=False).strip()
            yield TextArea(text=required_text, id="required-yaml", show_line_numbers=False)
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
        self._replace_models_yaml({"default": model.model_dump(exclude_none=True)})
        self.query_one("#default-model", Input).value = "default"

    @on(Button.Pressed, "#btn-model-openai")
    def _fill_openai_model(self) -> None:
        self._replace_models_yaml({"default": {"provider": "openai", "model": "gpt-4o-mini", "base_url": None}})
        self.query_one("#default-model", Input).value = "default"

    @on(Button.Pressed, "#btn-model-compatible")
    def _fill_compatible_model(self) -> None:
        self._replace_models_yaml(
            {
                "default": {
                    "provider": "openai_compatible",
                    "model": "your-model-name",
                    "base_url": "https://api.example.com/v1",
                    "api_key": "YOUR_API_KEY",
                }
            }
        )
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
            termination_keywords = [item.strip() for item in self.query_one("#workflow-terms", Input).value.split(",") if item.strip()]
            selector_prompt = self.query_one("#selector-prompt", TextArea).text.strip() or None
            models_data = yaml.safe_load(self.query_one("#models-yaml", TextArea).text.strip() or "{}")
            required_data = yaml.safe_load(self.query_one("#required-yaml", TextArea).text.strip() or "{}")

            updated = self.config.model_copy(deep=True)
            updated.project_name = project_name
            updated.workspace_root = workspace_root
            updated.default_model = default_model
            updated.workflow.mode = mode  # type: ignore[assignment]
            updated.workflow.max_turns = max_turns
            updated.workflow.termination_keywords = termination_keywords or ["TERMINATE"]
            updated.workflow.selector_prompt = selector_prompt
            updated.workflow.required_artifacts = required_data or {}
            updated.models = models_data or {}
            updated = AppConfig.model_validate(updated.model_dump())
        except Exception as exc:
            self.app.bell()
            if hasattr(self.app, "notify"):
                self.app.notify(f"保存失败: {exc}", severity="error")
            return
        self.dismiss(updated)


class AgentPanel(VerticalScroll):
    DEFAULT_CSS = """
    AgentPanel { padding: 0 1; }
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


class MAgentTabApp(App):
    CSS = """
    Screen { layout: vertical; }
    #tabs { height: 1fr; }
    #chat-status { height: 3; border: round $primary; margin: 1 1 0 1; padding: 0 1; }
    #chat-input-row { height: 5; border-top: solid $primary; padding: 0 1; }
    #task-input { height: 3; }
    #send-row { height: 3; }
    #deliverable-body { height: 1fr; }
    #deliverable-tree { width: 40%; border-right: solid $primary; }
    #deliverable-preview { width: 1fr; padding: 0 1; }
    #config-view { padding: 1 2; }
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
        Binding("ctrl+enter", "send_task", "发送"),
        Binding("f5", "send_task", "发送"),
        Binding("ctrl+1", "tab_chat", "Chat"),
        Binding("ctrl+2", "tab_agents", "Agents"),
        Binding("ctrl+3", "tab_deliverables", "Deliverables"),
        Binding("ctrl+4", "tab_config", "Config"),
    ]

    status_text: reactive[str] = reactive("就绪")

    def __init__(self, config: AppConfig, config_path: Optional[Path] = None):
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.title = f"magent-tui · {config.project_name}"
        self._task_running = False
        self._selected_agent_index = 0
        self._turn_count = 0
        self._agent_status: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-chat", id="tabs"):
            with TabPane("Chat", id="tab-chat"):
                yield Static("", id="chat-status")
                yield ChatLog(id="chat-log")
                with Vertical(id="chat-input-row"):
                    yield Input(
                        id="task-input",
                        placeholder="输入任务后按 Enter 发送（F5 兜底）",
                    )
                    with Horizontal(id="send-row"):
                        yield Label("Enter 发送 | F5 兜底")
                        yield Button("发送", id="btn-send-task", variant="primary")
            with TabPane("Agents", id="tab-agents"):
                yield AgentPanel(id="agent-panel")
            with TabPane("Deliverables", id="tab-deliverables"):
                with Horizontal(id="deliverable-body"):
                    yield DirectoryTree(str(self.config.ensure_workspace()), id="deliverable-tree")
                    yield Static("选择文件后在这里预览", id="deliverable-preview")
            with TabPane("Config", id="tab-config"):
                with Vertical(id="config-view"):
                    yield Static("", id="config-overview")
                    yield Button("编辑项目设置", id="btn-config-edit")
        yield Static(self.status_text, id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_agents()
        self._render_config_overview()
        self._update_agent_status_bar()
        self._log_system(
            f"欢迎使用 magent-tui · 项目 [b]{self.config.project_name}[/b]\n"
            f"当前 Agent 数: {len(self.config.agents)}，编排模式: {self.config.workflow.mode}\n"
            "提示: Ctrl+1~4 切换 Tab，Enter 发送任务。"
        )

    def watch_status_text(self, value: str) -> None:
        try:
            self.query_one("#status", Static).update(value)
        except Exception:
            pass

    def _set_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab_id

    def action_tab_chat(self) -> None:
        self._set_tab("tab-chat")

    def action_tab_agents(self) -> None:
        self._set_tab("tab-agents")

    def action_tab_deliverables(self) -> None:
        self._set_tab("tab-deliverables")

    def action_tab_config(self) -> None:
        self._set_tab("tab-config")

    def _render_agents(self) -> None:
        panel = self.query_one(AgentPanel)
        panel.remove_children()
        panel.mount(Label("[b]Agents[/b]"))
        if not self.config.agents:
            panel.mount(Static("[dim]还没有 Agent。按 Ctrl+T 选模板，或 Ctrl+A 新建。[/dim]"))
        else:
            items = []
            for idx, agent in enumerate(self.config.agents):
                color = _color_for(idx)
                items.append(
                    ListItem(
                        Label(
                            f"[{color}]●[/{color}] [b]{agent.name}[/b] [dim]{agent.role or '未命名角色'}[/dim]\n"
                            f"[dim]model: {self.config.model_name_for_agent(agent)} | ws: {agent.resolved_workspace()}[/dim]"
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

    def _render_config_overview(self) -> None:
        model_lines = [f"- `{k}`: {v.summary()}" for k, v in self.config.models.items()]
        claude = "已检测到" if find_claude_settings() else "未检测到"
        env_flags = [
            f"ANTHROPIC_API_KEY={'yes' if os.getenv('ANTHROPIC_API_KEY') else 'no'}",
            f"OPENAI_API_KEY={'yes' if os.getenv('OPENAI_API_KEY') else 'no'}",
        ]
        text = "\n".join(
            [
                f"### 项目: {self.config.project_name}",
                "",
                f"- workflow: `{self.config.workflow.mode}`",
                f"- max_turns: `{self.config.workflow.max_turns}`",
                f"- default_model: `{self.config.default_model}`",
                f"- workspace_root: `{Path(self.config.workspace_root).resolve()}`",
                "",
                "### 模型配置",
                *model_lines,
                "",
                "### 配置来源检测",
                f"- Claude settings: {claude}",
                f"- Env: {', '.join(env_flags)}",
            ]
        )
        self.query_one("#config-overview", Static).update(Markdown(text))

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

    def _status_icon(self, status: str) -> str:
        mapping = {"active": "🟢", "waiting": "🟡", "error": "🔴", "idle": "⚪", "done": "✅"}
        return mapping.get(status, "⚪")

    def _update_agent_status_bar(self, active: Optional[str] = None) -> None:
        if not self.config.agents:
            self.query_one("#chat-status", Static).update("暂无 Agent")
            return
        for a in self.config.agents:
            if a.name not in self._agent_status:
                self._agent_status[a.name] = "idle"
        if active:
            self._agent_status[active] = "active"
            for a in self.config.agents:
                if a.name != active and self._agent_status[a.name] == "active":
                    self._agent_status[a.name] = "waiting"
        line = "  ".join(f"{self._status_icon(self._agent_status[a.name])} {a.name}" for a in self.config.agents)
        term = "TERMINATE?" if self._task_running else "IDLE"
        turn = f"{self._turn_count}/{self.config.workflow.max_turns}"
        self.query_one("#chat-status", Static).update(f"{line}\nTurn: {turn}   [{term}]")

    def _refresh_tree(self) -> None:
        try:
            tree = self.query_one("#deliverable-tree", DirectoryTree)
            tree.path = str(self.config.ensure_workspace())
            tree.reload()
        except Exception:
            pass

    @on(DirectoryTree.FileSelected, "#deliverable-tree")
    def _preview_file(self, event: DirectoryTree.FileSelected) -> None:
        path = event.path
        if path is None or not path.is_file():
            return
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            self.query_one("#deliverable-preview", Static).update(f"无法预览文件: {path}")
            return
        if len(content) > 6000:
            content = content[:6000] + "\n\n... (已截断)"
        self.query_one("#deliverable-preview", Static).update(Panel(Markdown(content), title=str(path)))

    @on(Button.Pressed, "#btn-send-task")
    def _button_send(self) -> None:
        self.action_send_task()

    def action_send_task(self) -> None:
        area = self.query_one("#task-input", Input)
        task = area.value.strip()
        if not task:
            return
        if self._task_running:
            self.status_text = "当前任务仍在运行中..."
            return
        if not self.config.agents:
            self._log_system("⚠ 还没有 Agent，请先导入模板 (Ctrl+T) 或新建 (Ctrl+A)。")
            return
        area.value = ""
        self._run_task(task)

    @on(Input.Submitted, "#task-input")
    def _submit_task_input(self) -> None:
        if self.query_one("#tabs", TabbedContent).active != "tab-chat":
            return
        self.action_send_task()

    @on(Button.Pressed, "#btn-tpl")
    def _btn_tpl(self) -> None:
        self.action_pick_template()

    @on(Button.Pressed, "#btn-add")
    def _btn_add(self) -> None:
        self.action_add_agent()

    @on(Button.Pressed, "#btn-project")
    @on(Button.Pressed, "#btn-config-edit")
    def _btn_project(self) -> None:
        self.action_edit_project()

    @on(Button.Pressed, "#btn-edit")
    def _btn_edit(self) -> None:
        self.action_edit_agent()

    @on(Button.Pressed, "#btn-del")
    def _btn_del(self) -> None:
        self.action_delete_agent()

    @on(Button.Pressed, "#btn-clear")
    def _btn_clear(self) -> None:
        self.config.agents = []
        self._selected_agent_index = 0
        self._render_agents()
        self._update_agent_status_bar()
        self.status_text = "已清空 Agent"

    @on(ListView.Selected, "#agent-list")
    def _selected_agent(self, ev: ListView.Selected) -> None:
        if ev.item and ev.item.id:
            idx = int(ev.item.id.removeprefix("agent-"))
            if idx < 0 or idx >= len(self.config.agents):
                return
            self._selected_agent_index = idx
            self.status_text = f"当前 Agent: {self.config.agents[self._selected_agent_index].name}"

    def action_pick_template(self) -> None:
        def _cb(name: Optional[str]) -> None:
            if not name:
                return
            self.config.agents = instantiate_template(name)
            self._selected_agent_index = 0
            self.config.ensure_workspace()
            self._agent_status = {a.name: "idle" for a in self.config.agents}
            self._render_agents()
            self._update_agent_status_bar()
            self._refresh_tree()
            self.status_text = f"已导入模板: {name}"
            self._log_system(f"已导入模板 **{name}**，共 {len(self.config.agents)} 个 Agent。")

        self.push_screen(TemplatePickerScreen(), _cb)

    def action_add_agent(self) -> None:
        def _cb(agent: Optional[AgentConfig]) -> None:
            if not agent:
                return
            self.config.agents.append(agent)
            self.config.ensure_workspace()
            self._selected_agent_index = len(self.config.agents) - 1
            self._agent_status[agent.name] = "idle"
            self._render_agents()
            self._update_agent_status_bar()
            self._refresh_tree()
            self.status_text = f"新增 Agent: {agent.name}"

        self.push_screen(AgentEditScreen(), _cb)

    def action_edit_agent(self) -> None:
        if not self.config.agents:
            self.status_text = "没有可编辑的 Agent"
            return
        original = self.config.agents[self._selected_agent_index]

        def _cb(updated: Optional[AgentConfig]) -> None:
            if not updated:
                return
            self.config.agents[self._selected_agent_index] = updated
            if original.name != updated.name:
                self._agent_status.pop(original.name, None)
            self._agent_status[updated.name] = "idle"
            self.config.ensure_workspace()
            self._render_agents()
            self._update_agent_status_bar()
            self._refresh_tree()
            self.status_text = f"已更新 Agent: {updated.name}"

        self.push_screen(AgentEditScreen(original), _cb)

    def action_delete_agent(self) -> None:
        if not self.config.agents:
            self.status_text = "没有可删除的 Agent"
            return
        removed = self.config.agents.pop(self._selected_agent_index)
        self._agent_status.pop(removed.name, None)
        self._selected_agent_index = min(self._selected_agent_index, len(self.config.agents) - 1) if self.config.agents else 0
        self._render_agents()
        self._update_agent_status_bar()
        self._refresh_tree()
        self.status_text = f"已删除 Agent: {removed.name}"

    def action_edit_project(self) -> None:
        def _cb(updated: Optional[AppConfig]) -> None:
            if not updated:
                return
            self.config = updated
            self.title = f"magent-tui · {self.config.project_name}"
            self.config.ensure_workspace()
            self._render_agents()
            self._render_config_overview()
            self._update_agent_status_bar()
            self._refresh_tree()
            self.status_text = "已更新项目设置"

        self.push_screen(ProjectSettingsScreen(self.config), _cb)

    def action_save_config(self) -> None:
        path = self.config_path or Path("configs") / "current.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.config.to_yaml(path)
        self.status_text = f"已保存到 {path}"

    def action_new_session(self) -> None:
        self.query_one(ChatLog).remove_children()
        self._turn_count = 0
        self._agent_status = {a.name: "idle" for a in self.config.agents}
        self._update_agent_status_bar()
        self._log_system("🆕 新会话开始。")
        self.status_text = "新会话"

    def action_open_workspace(self) -> None:
        self.action_tab_deliverables()
        self._refresh_tree()
        self.status_text = f"工作空间: {Path(self.config.workspace_root).resolve()}"

    @work(exclusive=True)
    async def _run_task(self, task: str) -> None:
        self._task_running = True
        self._turn_count = 0
        self._agent_status = {a.name: "waiting" for a in self.config.agents}
        self._update_agent_status_bar()
        self.status_text = "运行中..."
        self._log_system(f"📋 **任务**: {task}")
        service = RunService(self.config)
        try:
            async for event in service.run(task):
                self._consume_event(event)
                await asyncio.sleep(0)
            self._refresh_tree()
            self.status_text = "✓ 完成"
        except Exception as exc:
            self._log_system(f"❌ 运行出错: `{exc}`")
            self.status_text = "运行出错"
        finally:
            self._task_running = False
            for name in list(self._agent_status):
                if self._agent_status[name] != "error":
                    self._agent_status[name] = "done"
            self._update_agent_status_bar()

    def _consume_event(self, event: RunEvent) -> None:
        if event.event_type == "run_started":
            run_dir = event.metadata.get("run_dir")
            if run_dir:
                self._log_system(f"🗂 本次运行目录: `{run_dir}`")
            return
        if event.event_type == "run_failed":
            self._log_system(f"❌ RunService 失败: `{event.content or ''}`")
            return
        if event.event_type in {"run_state_changed", "run_completed"}:
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
            if "失败" in msg.content:
                for name in list(self._agent_status):
                    self._agent_status[name] = "error"
                self._update_agent_status_bar()
            return

        self._turn_count += 1
        self._update_agent_status_bar(active=msg.agent)
        self._log_message(msg)


def run_app(config: AppConfig, config_path: Optional[Path] = None) -> None:
    MAgentTabApp(config, config_path).run()

