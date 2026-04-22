# magent-tui · 多智能体协作 TUI

基于 **AutoGen** + **Textual** 的本地多智能体协作系统，带终端界面，支持：

- 🎭 **多角色自定义**：每个 Agent 可配置名字、角色、system prompt、模型、工作目录
- 🧰 **Agent 工作目录工具**：真实 AutoGen 模式下可调用 `write_text_file` / `append_text_file` / `read_text_file` / `list_workspace_files`
- 📚 **模板库一键导入**：内置 `product_sprint` / `content_factory` / `dev_delivery` / `research_squad` / `code_review` 等流行协作模板
- 🧠 **模型灵活配置**：自动读取 Claude Code 的 `~/.claude/settings.json`，或通过 YAML / 环境变量配置 OpenAI / Anthropic / 任意 OpenAI 兼容端点
- 📁 **每个 Agent 独立工作空间**：自动在 `deliverables/<agent>/` 下生成过程交付件
- 📝 **运行过程自动落盘**：每次任务会写入 `deliverables/runs/<timestamp>/`，并同步追加到各 Agent 的 `activity.md`
- 💬 **实时 TUI 聊天**：左侧 Agent 面板 + 中间会话流 + 右侧任务 / 交付件监控
- 🔁 **多种编排策略**：RoundRobin / Selector / 单任务委派

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 快速上手

```bash
# 1. 用内置模板生成默认配置
magent-tui init --template product_sprint -o configs/my.yaml

# 2. 启动 TUI
magent-tui run --config configs/my.yaml

# 3. 列出所有可用模板
magent-tui templates

# 4. 检查依赖、配置与模型环境
magent-tui doctor --config configs/my.yaml
```

在 TUI 中：

- 用 `Ctrl+T` 导入模板，`Ctrl+A` 新建 Agent
- 用 `Ctrl+P` 编辑项目名、工作空间、workflow 和 models YAML
- 左侧列表选中 Agent 后可点击“编辑 / 删除”
- `Ctrl+S` 将当前配置保存到 YAML
- 右侧文件树会显示每个 Agent 工作目录和 `runs/` 运行记录

## 配置优先级

1. `--config` 指定的 YAML
2. `~/.claude/settings.json`(Claude Code 的模型/API Key)
3. 环境变量：`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENAI_BASE_URL`

## 配置示例

见 `configs/default.yaml`。

## 环境诊断

`magent-tui doctor` 会检查：

- `textual` / `pydantic` / `autogen_*` 是否已安装
- `--config` YAML 是否能成功解析
- `~/.claude/settings.json` 是否存在且含可用模型信息
- 环境变量中的 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENAI_BASE_URL`
- 配置文件里的 `models` 和 `default_model` 是否一致

## 快捷键

| 键 | 作用 |
|---|---|
| `Ctrl+Enter` | 发送任务 |
| `Ctrl+N` | 新建会话 |
| `Ctrl+S` | 保存当前配置 |
| `Ctrl+P` | 编辑项目设置 / 模型 / 编排 |
| `Ctrl+E` | 打开交付件目录 |
| `Ctrl+Q` | 退出 |
