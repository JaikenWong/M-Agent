# m-agent 详细技术设计

本文档面向后续开发人员，描述建议的核心数据模型、模块边界、运行数据流、目录组织和实现要点。

## 1. 设计目标

未来版本应满足以下目标：

- 支持结构化任务驱动的多智能体协作
- 支持多种 workflow 编排模式
- 支持统一事件流
- 支持工具权限与工作目录边界
- 支持运行回放与质量评估
- 保持与当前 TUI 形态兼容

## 2. 建议的核心领域模型

## 2.1 TaskSpec

建议引入结构化任务规格模型，用于替代单一字符串输入。

```python
class TaskSpec(BaseModel):
    title: str
    goal: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    output_contract: dict[str, Any] = Field(default_factory=dict)
```

### 作用

- 将用户输入标准化
- 让 orchestrator 可以按字段分发上下文
- 为门禁和评估提供明确依据

## 2.2 RunContext

```python
class RunContext(BaseModel):
    run_id: str
    project_name: str
    workspace_root: str
    workflow_mode: str
    started_at: datetime
    config_snapshot: dict[str, Any]
```

### 作用

- 为一次 run 提供完整上下文
- 支撑回放和问题定位
- 避免执行中依赖可变配置对象

## 2.3 RunEvent

```python
class RunEvent(BaseModel):
    event_type: Literal[
        "run_started",
        "run_state_changed",
        "agent_started",
        "agent_message",
        "tool_called",
        "tool_result",
        "artifact_written",
        "agent_completed",
        "run_completed",
        "run_failed",
    ]
    timestamp: datetime
    run_id: str
    agent: str | None = None
    role: str | None = None
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 作用

- 统一 UI、日志、回放、评估的数据基础
- 取代当前“聊天消息即运行事实”的隐式设计

## 2.4 AgentRuntimeState

```python
class AgentRuntimeState(BaseModel):
    name: str
    role: str
    status: Literal["idle", "running", "waiting", "blocked", "done", "failed"]
    workspace: str
    current_task: str | None = None
    produced_artifacts: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
```

### 作用

- 为 TUI 面板提供运行态信息
- 为 orchestrator 提供阶段调度依据

## 2.5 ToolPermission

```python
class ToolPermission(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    read_scopes: list[str] = Field(default_factory=list)
    write_scopes: list[str] = Field(default_factory=list)
```

### 作用

- 限制 Agent 的能力边界
- 支撑后续 repo / shell / search 工具扩展

## 2.6 WorkflowConfig 扩展建议

```python
class WorkflowConfig(BaseModel):
    mode: Literal[
        "round_robin",
        "selector",
        "single",
        "pipeline",
        "review_loop",
        "manager_worker",
    ] = "round_robin"
    max_turns: int = 12
    termination_keywords: list[str] = Field(default_factory=lambda: ["TERMINATE"])
    selector_prompt: str | None = None
    retry_limit: int = 1
    review_required: bool = False
    routing_rules: list[dict[str, Any]] = Field(default_factory=list)
    required_artifacts: dict[str, list[str]] = Field(default_factory=dict)
```

## 3. 建议的模块划分

建议逐步演进为如下结构：

```text
src/magent_tui/
  main.py
  app.py
  domain/
    models.py
    events.py
    task_spec.py
  services/
    run_service.py
    config_service.py
    template_service.py
    artifact_service.py
    doctor_service.py
  orchestrators/
    base.py
    mock.py
    autogen.py
    pipeline.py
    review_loop.py
    selector.py
  tools/
    workspace.py
    repo.py
    search.py
    shell.py
    artifact_writer.py
  ui/
    screens.py
    panels.py
    widgets.py
  templates.py
  settings_loader.py
```

## 4. 各层职责定义

## 4.1 UI 层

主要职责：

- 展示 Agent 列表
- 展示运行状态
- 接收任务输入
- 展示消息和产物
- 触发配置编辑和模板导入

设计要求：

- UI 不直接组织复杂业务逻辑
- UI 只调用 `RunService` 和相关应用服务

## 4.2 Application Service 层

建议把下列能力从 UI 层抽离：

### RunService

职责：

- 接收 `TaskSpec`
- 创建 `RunContext`
- 初始化 orchestrator
- 订阅并转发 `RunEvent`
- 驱动 ArtifactService 落盘
- 统一完成 / 失败处理

接口建议：

```python
class RunService:
    async def run(
        self,
        task: TaskSpec,
        config: AppConfig,
    ) -> AsyncIterator[RunEvent]:
        ...
```

### ArtifactService

职责：

- 创建 run 目录
- 写 event log
- 写 transcript
- 写 summary
- 建立 artifacts index

### ConfigService

职责：

- 加载配置
- 校验配置
- 补齐默认值
- 输出 config snapshot

### DoctorService

职责：

- 执行依赖检查
- 执行配置检查
- 执行模型认证检查
- 输出面向 CLI 的诊断报告

## 4.3 Orchestrator 层

### 统一接口建议

```python
class OrchestratorBase(Protocol):
    async def run(
        self,
        task: TaskSpec,
        context: RunContext,
    ) -> AsyncIterator[RunEvent]:
        ...
```

### MockOrchestrator

用途：

- 本地无依赖演示
- 快速联调 UI 和 artifacts
- 回退路径保证系统可启动

### AutoGenOrchestrator

用途：

- 封装真实模型与 Agent 运行时
- 负责适配 AutoGen 事件到 `RunEvent`

### PipelineOrchestrator

用途：

- 处理线性依赖流程
- 支持上游产物可见、下游接力、阶段门禁

### ReviewLoopOrchestrator

用途：

- 处理实现-评审-修正闭环
- 支持 reviewer 驳回和 retry

## 5. 推荐的运行数据流

建议执行链路如下：

1. UI 接收自然语言输入
2. `RunService` 将输入转换为 `TaskSpec`
3. `ConfigService` 生成不可变 `config_snapshot`
4. `ArtifactService` 创建 run 目录并写入起始记录
5. Orchestrator 按 workflow 驱动 Agent 执行
6. 执行过程中所有事实输出为 `RunEvent`
7. `ArtifactService` 消费事件并落盘
8. UI 根据同一事件流更新展示
9. run 结束后生成 summary、metrics 和 artifacts index

这样可以确保：

- UI 与持久化基于同一事实源
- 回放和评估不依赖 UI 专属逻辑
- 后续可以接 Web UI 而不需要重写底层

## 6. 工具系统详设

## 6.1 工具分类

建议工具分为五类：

### Workspace Tools

职责：

- 当前 Agent 工作目录内写文件
- 读取已有产物
- 列出目录

### Repo Tools

职责：

- 读取项目文件
- 查看配置
- 列出目录结构

### Search Tools

职责：

- 搜索文件
- 搜索符号
- 搜索关键内容

### Shell Tools

职责：

- 受限执行命令
- 运行测试和 lint
- 返回结构化执行结果

### Artifact Writer Tools

职责：

- 按标准模板写 PRD、ADR、测试计划、报告等

## 6.2 工具权限边界

建议每个 Agent 的工具权限显式配置：

- `allowed_tools`
- `read_scopes`
- `write_scopes`

示例：

- PM：
  - 可写 `PM/`
  - 可读公共目录
  - 禁止 shell
- Architect：
  - 可读 `PM/`
  - 可写 `Architect/`
- Engineer：
  - 可读 `PM/` 和 `Architect/`
  - 可写 `Engineer/`
  - 可使用受限 shell
- QA：
  - 可读所有交付目录
  - 可写 `QA/`
  - 可运行测试工具

## 7. 产物系统详设

建议固定 run 目录结构：

```text
deliverables/
  runs/
    <run_id>/
      run.json
      task.md
      transcript.jsonl
      events.jsonl
      summary.md
      metrics.json
      judgments.json
      artifacts_index.json
```

其中：

- `run.json`：run 元信息
- `task.md`：结构化任务描述
- `transcript.jsonl`：用户和 Agent 消息文本流
- `events.jsonl`：统一事件流
- `summary.md`：面向人阅读的总结
- `metrics.json`：结构化指标
- `judgments.json`：门禁或质量检查结果
- `artifacts_index.json`：产物索引

Agent 工作目录建议继续保留：

```text
deliverables/
  PM/
    activity.md
    PRD.md
  Architect/
    activity.md
    architecture.md
    adr/
  Engineer/
    activity.md
    src/
  QA/
    activity.md
    test_plan.md
    report.md
```

## 8. 门禁与质量判断

建议将“任务完成”从 prompt 里解耦出来，交给门禁系统做基础判断。

### 8.1 门禁规则示例

PM 阶段：

- 必须产生 `PRD.md`
- 必须包含目标、用户、功能、验收标准

Architect 阶段：

- 必须产生 `architecture.md`
- 必须包含模块划分、关键流程、技术选型

Engineer 阶段：

- 必须产生代码清单或实现说明

QA 阶段：

- 必须产生测试计划或验收报告

### 8.2 判断结果建议

每个门禁节点输出：

- `passed`
- `failed`
- `warnings`
- `missing_artifacts`
- `missing_sections`

门禁结果进入 `judgments.json`，并同步进入 summary。

## 9. 指标与评估

V1 建议先做以下基础指标：

- `run_success_rate`
- `avg_turns_per_run`
- `avg_duration_seconds`
- `artifact_completion_rate`
- `termination_reason_distribution`
- `agent_contribution_ratio`

后续可扩展：

- 不同 workflow 的成功率对比
- 不同模板的完成质量对比
- 不同模型组合的成本与效果对比

## 10. 测试建议

建议至少建立以下测试模块：

### 单元测试

- `config_models`
- `workspace_tools`
- `artifacts`
- `settings_loader`
- `templates`

### 集成测试

- mock workflow 运行
- pipeline workflow 运行
- doctor 命令
- run 目录落盘结构

### 回归测试重点

- workspace 越权路径校验
- fallback 行为
- workflow 终止条件
- 产物缺失时的门禁结果

## 11. 迁移建议

建议分三步演进，避免一次性重构：

### 第一步

- 保留当前文件结构
- 新增 `services/` 与 `domain/`
- 先把 `RunService` 和 `RunEvent` 接起来

### 第二步

- 把 `orchestrator.py` 拆到 `orchestrators/`
- 把 `workspace_tools.py` 拆到 `tools/`
- `artifacts.py` 过渡到 `ArtifactService`

### 第三步

- 把 `app.py` 中的 UI 组件和行为拆离
- 为后续 Web UI 或更复杂 TUI 演进做准备

## 12. 详细设计结论

`m-agent` 下一阶段最重要的技术目标不是继续堆功能，而是建立以下稳定底盘：

- 结构化任务模型
- 统一运行事件模型
- 显式 workflow 抽象
- 工具权限模型
- 可评估的产物与 run 数据

只要这五个底盘到位，后续无论是扩展模板、增加工具、接入更多模型，还是支持更多 UI 形态，系统都会更容易演进和维护。
