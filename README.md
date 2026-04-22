# magent-tui

基于 AutoGen + Textual 的本地多智能体协作 TUI。

它的目标很直接：在终端里快速搭一个“可配置角色 + 可切换模板 + 可落盘交付件”的多 Agent 工作台。你可以用它做产品拆解、代码交付、研究分析、内容生产，也可以把它当成一个多智能体原型底座继续往上改。

当前已经具备这些能力：

- 支持多个 Agent，每个 Agent 都可单独配置 `name`、`role`、`system_prompt`、`model`、`workspace`
- 内置多种常见多 Agent 模板，能一键导入
- 支持从 Claude Code 的 `~/.claude/settings.json` 自动读取模型配置
- 支持手工配置 Anthropic / OpenAI / OpenAI 兼容端点
- 支持 `round_robin` / `selector` / `single` / `pipeline` 四种编排模式
- 真实 AutoGen 模式下，Agent 可调用工作目录工具写文件
- 每次运行会把会话流和过程产物自动落盘
- 运行链路通过 `RunService` 输出统一事件流，便于 UI、日志与回放共用
- 带 TUI 界面，适合边配边跑

## 目录

- [安装](#安装)
- [5 分钟启动](#5-分钟启动)
- [CLI 命令](#cli-命令)
- [TUI 怎么用](#tui-怎么用)
- [模型配置](#模型配置)
- [配置文件说明](#配置文件说明)
- [内置模板](#内置模板)
- [运行产物](#运行产物)
- [环境诊断](#环境诊断)
- [常见问题](#常见问题)

## 安装

推荐使用独立虚拟环境。这个项目依赖 `textual`、`autogen-agentchat`、`autogen-ext`，如果直接装进全局环境，容易和你机器上其他 Python 工具的版本冲突。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

如果你后面需要额外能力，也可以安装可选依赖：

```bash
python3 -m pip install -e ".[litellm,anthropic]"
```

安装完成后确认 CLI 可用：

```bash
magent-tui --help
```

## 5 分钟启动

### 方式 1：最快启动

直接用默认模板启动：

```bash
magent-tui run
```

不传 `--config` 时，会自动使用内置 `product_sprint` 模板启动。

### 方式 2：先生成配置，再启动

1. 列出所有模板

```bash
magent-tui templates
```

2. 生成一份配置文件

```bash
magent-tui init --template product_sprint -o configs/my.yaml
```

3. 检查环境是否就绪

```bash
magent-tui doctor --config configs/my.yaml
```

4. 启动 TUI

```bash
magent-tui run --config configs/my.yaml
```

### 方式 3：直接用仓库自带配置

仓库已经带了一份可直接启动的默认配置：

```bash
magent-tui doctor --config configs/default.yaml
magent-tui run --config configs/default.yaml
```

## CLI 命令

### `magent-tui run`

启动 TUI。

```bash
magent-tui run
magent-tui run --config configs/default.yaml
```

行为说明：

- 不传 `--config` 时，自动用内置 `product_sprint` 模板启动
- 传了 `--config` 时，优先读取 YAML
- 如果配置中的模型没有显式 API 信息，运行时会尝试回退到 Claude settings 或环境变量

### `magent-tui init`

生成一份 YAML 配置文件。

```bash
magent-tui init --template research_squad -o configs/research.yaml
```

### `magent-tui templates`

列出所有内置模板。

```bash
magent-tui templates
```

### `magent-tui doctor`

检查环境、依赖、Claude settings、配置文件和模型可用性。

```bash
magent-tui doctor
magent-tui doctor --config configs/default.yaml
```

## TUI 怎么用

TUI 布局大致是三栏：

- 左侧：Agent 列表和管理按钮
- 中间：会话流
- 右侧：工作目录和交付件树

进入 TUI 后，常用操作如下。

### 先做什么

建议第一次进入时按这个顺序：

1. `Ctrl+T` 导入一个模板
2. `Ctrl+P` 检查项目设置、模型和 workflow
3. 左侧选中某个 Agent，必要时点击“编辑”
4. 在底部输入框里输入任务，回车发送
5. 右侧查看 Agent 工作目录和 `runs/` 运行记录

### 常用快捷键

| 键 | 作用 |
|---|---|
| `Enter` | 发送当前任务 |
| `Ctrl+N` | 新建会话 |
| `Ctrl+S` | 保存当前配置 |
| `Ctrl+P` | 编辑项目设置 / 模型 / 编排 |
| `Ctrl+T` | 导入模板 |
| `Ctrl+A` | 新建 Agent |
| `Ctrl+E` | 刷新并查看交付件目录 |
| `Ctrl+Q` | 退出 |

### 左侧 Agent 面板

左侧支持这些操作：

- `+模板`：导入内置模板，覆盖当前 Agent 列表
- `+Agent`：新建一个 Agent
- `项目`：编辑项目级配置
- `编辑`：编辑当前选中的 Agent
- `删除`：删除当前选中的 Agent
- `清空`：清空全部 Agent

每个 Agent 会显示：

- 名称和角色
- 绑定的模型 key
- 它自己的工作目录

### 项目设置里能改什么

按 `Ctrl+P` 可编辑：

- `project_name`
- `workspace_root`
- `default_model`
- `workflow.mode`
- `workflow.max_turns`
- `workflow.termination_keywords`
- `workflow.selector_prompt`
- 整块 `models` YAML

项目设置里还带了几个模型快捷按钮：

- `Claude 默认`
- `OpenAI 默认`
- `兼容端点模板`

适合先快速生成一份模型配置，再细改。

## 模型配置

这个项目支持三种主要来源。

### 1. Claude Code settings

默认会尝试读取：

- `~/.claude/settings.json`
- `~/.config/claude/settings.json`

当前读取逻辑会识别这些字段：

- `env.ANTHROPIC_API_KEY`
- `env.ANTHROPIC_AUTH_TOKEN`
- `env.ANTHROPIC_BASE_URL`
- `env.ANTHROPIC_MODEL`
- 顶层 `model`

这意味着如果你本机已经能正常使用 Claude Code，很多情况下 `magent-tui` 可以直接复用它的模型配置。

### 2. 环境变量

也支持从环境变量读取：

```bash
export ANTHROPIC_API_KEY=...
export ANTHROPIC_MODEL=claude-sonnet-4-5

# 或
export ANTHROPIC_AUTH_TOKEN=...
export ANTHROPIC_BASE_URL=https://your-endpoint.example.com

# 或
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4o-mini
```

### 3. YAML 显式配置

你也可以在配置文件里明确写 `models`：

```yaml
default_model: default
models:
  default:
    provider: anthropic
    model: claude-sonnet-4-5
    api_key: YOUR_KEY
    base_url: https://api.anthropic.com
```

或 OpenAI 兼容端点：

```yaml
default_model: default
models:
  default:
    provider: openai_compatible
    model: your-model-name
    api_key: YOUR_KEY
    base_url: https://your-endpoint.example.com/v1
```

### 配置优先级

运行时的优先级可以理解为：

1. `--config` 指定 YAML
2. Claude settings
3. 环境变量
4. 最后才是代码里的占位默认值

注意：

- 如果 YAML 里写了模型名，但没有可用 `api_key` / `base_url`，运行时可能回退到 Claude settings
- `doctor` 会把这种“配置本身没写，但运行时能回退”的情况显示出来

## 配置文件说明

默认配置文件见 [configs/default.yaml](configs/default.yaml)。

最小结构如下：

```yaml
project_name: m-agent
workspace_root: deliverables
default_model: default

models:
  default:
    provider: anthropic
    model: claude-sonnet-4-5

agents:
  - name: PM
    role: 产品经理
    workspace: PM
    system_prompt: |
      你是资深产品经理。

workflow:
  mode: round_robin
  max_turns: 12
  termination_keywords:
    - TERMINATE
    - 任务完成
```

### 顶层字段

- `project_name`：项目名，显示在 TUI 标题栏
- `workspace_root`：所有交付件的根目录
- `default_model`：默认模型 key，Agent 未显式指定模型时使用它
- `models`：模型配置字典
- `agents`：Agent 列表
- `workflow`：多 Agent 编排配置

### `AgentConfig`

每个 Agent 支持：

- `name`
- `role`
- `system_prompt`
- `model`
- `workspace`
- `description`

说明：

- `workspace` 不写时，默认用 `name`
- `model` 不写时，默认用 `default_model`

### `WorkflowConfig`

支持四个模式：

- `round_robin`：按顺序轮流发言
- `selector`：让模型决定下一位发言者
- `single`：只运行第一个 Agent
- `pipeline`：按 Agent 列表顺序阶段化执行

`selector` 模式下，可额外配置 `selector_prompt`。
`pipeline` 模式下，可通过 `required_artifacts` 配置阶段门禁。

示例：

```yaml
workflow:
  mode: pipeline
  required_artifacts:
    PM:
      - PRD.md
    Architect:
      - architecture.md
```

## 内置模板

当前内置这些模板：

- `product_sprint`：产品冲刺 5 人小队
- `content_factory`：内容生产流水线
- `dev_delivery`：需求 -> 实现 -> 测试 -> 文档
- `research_squad`：研究主管 + 搜集 + 分析 + 批判
- `code_review`：代码阅读 + 安全 + 性能 + 综合评审
- `debate`：正方 / 反方 / 裁判

查看模板列表：

```bash
magent-tui templates
```

生成模板配置：

```bash
magent-tui init --template dev_delivery -o configs/dev.yaml
```

## 运行产物

所有产物默认写到 `workspace_root` 下。

### Agent 工作目录

每个 Agent 都有自己的目录，例如：

```text
deliverables/
  PM/
  Architect/
  Engineer/
  QA/
```

真实 AutoGen 模式下，Agent 可以使用这些工具在自己的目录里读写文件：

- `write_text_file`
- `append_text_file`
- `read_text_file`
- `list_workspace_files`

### 运行记录目录

每次任务运行还会生成一份按时间戳命名的运行记录：

```text
deliverables/
  runs/
    20260422-230501/
      run.json
      task.md
      summary.md
      transcript.jsonl
      events.jsonl
      system.md
```

其中：

- `task.md`：本次任务
- `summary.md`：运行摘要
- `transcript.jsonl`：消息流
- `events.jsonl`：结构化运行事件
- `system.md`：系统消息

同时，各个 Agent 的工作目录下还会持续追加 `activity.md`。

## 环境诊断

如果项目启动不了，第一步不要猜，先运行：

```bash
magent-tui doctor --config configs/default.yaml
```

`doctor` 会检查：

- `textual` / `pydantic` / `autogen_*` 是否安装
- 配置文件是否可解析
- Claude settings 是否存在且可读取
- 环境变量中的模型配置
- `models` / `default_model` 是否一致
- 当前配置是否可通过运行时回退拿到模型连接信息

## 常见问题

### 1. 能启动 TUI，但运行时还是 mock 模式

通常是这几种原因：

- `autogen_agentchat` / `autogen_core` / `autogen_ext` 没装
- 配置文件里的模型没有可用的 `api_key` / `base_url`
- Claude settings 没有被正确读取

先跑：

```bash
magent-tui doctor --config configs/default.yaml
```

### 2. Claude settings 里明明有模型，为什么还跑不起来

先确认你的 `settings.json` 里是否真的包含这些字段之一：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_MODEL`

另外，某些自定义模型名不是官方 Anthropic 名称，AutoGen 默认不认识。项目里已经对这类模型做了兜底处理，但前提是 `base_url` 和认证信息本身要可用。

### 3. 为什么建议用虚拟环境

因为 `textual`、`rich`、`autogen-*` 很容易和其他终端工具的依赖版本冲突。最省事的做法就是：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

### 4. 发送任务是 `Enter` 还是 `Ctrl+Enter`

当前实际行为是：输入框里直接按 `Enter` 提交任务。

### 5. 这项目更适合拿来做什么

目前最适合：

- 多 Agent 工作流原型
- 本地 TUI 多智能体调度台
- 带交付件目录的 AutoGen 实验项目
- 继续往上做“角色市场 / 模板市场 / 工具集成 / 文件编辑代理”的基础工程

## 开发建议

如果你准备继续开发这套系统，推荐优先做这几件事：

1. 给 `models` 做真正的列表式 UI，而不是只编辑 YAML
2. 给 Agent 增加更多工具，比如 shell、代码执行、搜索、Git 操作
3. 增加并维持自动化测试，覆盖配置解析、运行产物和 doctor 输出
4. 增加会话持久化和历史回放
5. 增加模板导入导出

## 许可证

仓库里目前还没有单独的 LICENSE 文件。如果你准备公开发布，建议尽快补上。

## 运行测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```
