# magent-tui · 多智能体协作 TUI

基于 **AutoGen** + **Textual** 的本地多智能体协作系统，带终端界面，支持：

- 🎭 **多角色自定义**：每个 Agent 可配置名字、角色、system prompt、模型、工作目录
- 📚 **模板库一键导入**：内置 `product_sprint` / `content_factory` / `dev_delivery` / `research_squad` / `code_review` 等流行协作模板
- 🧠 **模型灵活配置**：自动读取 Claude Code 的 `~/.claude/settings.json`，或通过 YAML / 环境变量配置 OpenAI / Anthropic / 任意 OpenAI 兼容端点
- 📁 **每个 Agent 独立工作空间**：自动在 `deliverables/<agent>/` 下生成过程交付件
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
```

## 配置优先级

1. `--config` 指定的 YAML
2. `~/.claude/settings.json`(Claude Code 的模型/API Key)
3. 环境变量：`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENAI_BASE_URL`

## 配置示例

见 `configs/default.yaml`。

## 快捷键

| 键 | 作用 |
|---|---|
| `Ctrl+Enter` | 发送任务 |
| `Ctrl+N` | 新建会话 |
| `Ctrl+S` | 保存当前配置 |
| `Ctrl+E` | 打开交付件目录 |
| `Ctrl+Q` | 退出 |
