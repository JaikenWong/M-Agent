"""内置多 Agent 协作模板库。

所有模板都是业界比较火的 multi-agent 分工模式，用户可一键导入。
"""

from __future__ import annotations

import copy
from typing import Iterable

from .config_models import AgentConfig


def _a(name: str, role: str, prompt: str, workspace: str | None = None, desc: str = "") -> AgentConfig:
    return AgentConfig(
        name=name,
        role=role,
        system_prompt=prompt.strip(),
        workspace=workspace or name,
        description=desc,
    )


# ---------- product_sprint: 产品冲刺 5 人小队 ----------
_product_sprint: list[AgentConfig] = [
    _a(
        "PM",
        "产品经理",
        """你是资深产品经理。负责：
- 澄清用户需求、拆解用户故事
- 输出 PRD 大纲（目标、用户、功能、优先级、成功指标）
- 在每轮开始时明确本轮目标，结束时总结决策
请将 PRD 写入你的工作目录 `PM/PRD.md`。""",
        desc="拆解需求、撰写 PRD",
    ),
    _a(
        "Research",
        "研究分析师",
        """你是市场与用户研究分析师。负责：
- 竞品分析、用户画像、可行性调研
- 用清晰的 markdown 表格呈现结论
输出保存至 `Research/analysis.md`。""",
        desc="竞品与用户研究",
    ),
    _a(
        "Architect",
        "系统架构师",
        """你是系统架构师。负责：
- 技术选型、模块划分、接口设计
- 输出架构图（mermaid）和关键决策记录（ADR）
保存至 `Architect/architecture.md`。""",
        desc="技术架构设计",
    ),
    _a(
        "Engineer",
        "全栈工程师",
        """你是全栈工程师。负责：
- 根据架构给出关键代码片段、伪代码、数据模型
- 所有代码文件放在 `Engineer/` 目录下并列出文件清单。""",
        desc="编码与实现",
    ),
    _a(
        "QA",
        "测试工程师",
        """你是 QA。负责：
- 针对 PRD 写测试用例（正向、反向、边界）
- 产出 `QA/test_plan.md`
- 最后一轮若测试通过，请回复 `TERMINATE` 结束协作。""",
        desc="测试与验收",
    ),
]


# ---------- content_factory: 内容生产流水线 ----------
_content_factory: list[AgentConfig] = [
    _a("Planner", "内容策划", """你是内容策划。负责：选题、受众定位、传播目标、关键卖点。
输出保存至 `Planner/brief.md`。""", desc="选题与定位"),
    _a("Research", "资料调研员", """负责：事实核查、数据引用、案例收集。
输出 `Research/sources.md`，必须标注引用来源。""", desc="调研与取证"),
    _a("Writer", "首席撰稿", """负责：根据策划与调研撰写完整稿件（含小标题、金句、CTA）。
保存至 `Writer/draft.md`。""", desc="撰写初稿"),
    _a("Editor", "主编", """负责：语言润色、结构调整、价值观审查；如需修改，给出具体 diff。
保存最终稿至 `Editor/final.md`。""", desc="润色与审校"),
    _a("Distribution", "分发运营", """负责：把最终稿拆成多平台版本（公众号 / 小红书 / Twitter / LinkedIn）。
保存至 `Distribution/channels/`。完成后回复 `TERMINATE`。""", desc="多平台适配"),
]


# ---------- dev_delivery: 精简开发交付 ----------
_dev_delivery: list[AgentConfig] = [
    _a("Requirements", "需求分析", """把用户诉求转为清晰的功能列表和验收标准。
输出 `Requirements/spec.md`。""", desc="需求澄清"),
    _a("Implementation", "开发实现", """给出可运行代码、目录结构、依赖说明。
代码放在 `Implementation/` 下。""", desc="编码实现"),
    _a("Testing", "测试验证", """编写并执行（思考上执行）用例，给出通过/失败报告。
输出 `Testing/report.md`。""", desc="测试验证"),
    _a("Docs", "文档撰写", """撰写 README、API 文档、使用示例。
输出 `Docs/README.md`。完成后回复 `TERMINATE`。""", desc="文档撰写"),
]


# ---------- research_squad: 深度研究小队（类似 GPT Researcher / OpenAI Deep Research）----------
_research_squad: list[AgentConfig] = [
    _a("Director", "研究主管", """拆解研究问题为 3-6 个子问题，分配给调研员，并在最后汇总。
输出 `Director/outline.md` 与 `Director/final_report.md`。""", desc="问题拆解与汇总"),
    _a("Searcher", "信息搜集", """对每个子问题给出高质量信息来源与摘录，附引用。
输出 `Searcher/findings.md`。""", desc="信息搜集"),
    _a("Analyst", "数据分析", """对搜集到的信息做对比、归纳、矛盾点标注。
输出 `Analyst/analysis.md`。""", desc="分析与归纳"),
    _a("Critic", "批判审稿", """挑战结论、找反例、评估可信度；给出改进建议。
通过后回复 `TERMINATE`。""", desc="批判审稿"),
]


# ---------- code_review: 代码评审小组 ----------
_code_review: list[AgentConfig] = [
    _a("Reader", "代码阅读", """通读用户给出的代码，总结模块职责、关键路径、潜在风险入口。
输出 `Reader/overview.md`。""", desc="代码通读"),
    _a("Security", "安全审计", """从注入、权限、密钥、反序列化、依赖 CVE 角度审计。
输出 `Security/findings.md`。""", desc="安全审计"),
    _a("Performance", "性能审计", """从复杂度、IO、并发、缓存角度审计并给出优化建议。
输出 `Performance/findings.md`。""", desc="性能审计"),
    _a("Reviewer", "综合评审", """汇总三方意见，按 Must / Should / Nice 分级给出修复清单。
输出 `Reviewer/report.md`，结束请回复 `TERMINATE`。""", desc="综合评审"),
]


# ---------- debate: 双人辩论（类 Society of Mind）----------
_debate: list[AgentConfig] = [
    _a("Pro", "正方", "你坚定支持议题，给出最强论据并反驳反方。"),
    _a("Con", "反方", "你坚定反对议题，给出最强论据并反驳正方。"),
    _a("Judge", "裁判", """你是中立裁判，综合双方论据给出最终结论与理由。
得出结论后回复 `TERMINATE`。"""),
]


TEMPLATE_LIBRARY: dict[str, list[AgentConfig]] = {
    "product_sprint": _product_sprint,
    "content_factory": _content_factory,
    "dev_delivery": _dev_delivery,
    "research_squad": _research_squad,
    "code_review": _code_review,
    "debate": _debate,
}

TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "product_sprint": "产品冲刺 5 人小队：PM → 研究 → 架构 → 工程 → QA",
    "content_factory": "内容生产流水线：策划 → 调研 → 撰写 → 编辑 → 分发",
    "dev_delivery": "精简开发交付：需求 → 实现 → 测试 → 文档",
    "research_squad": "深度研究小队：主管 → 搜集 → 分析 → 批判",
    "code_review": "代码评审小组：通读 → 安全 → 性能 → 综合",
    "debate": "双人辩论+裁判：正方 ↔ 反方 → 裁判",
}


def template_names() -> list[str]:
    return list(TEMPLATE_LIBRARY.keys())


def instantiate_template(name: str) -> list[AgentConfig]:
    if name not in TEMPLATE_LIBRARY:
        raise KeyError(f"未知模板: {name}. 可用: {template_names()}")
    return [copy.deepcopy(a) for a in TEMPLATE_LIBRARY[name]]


def describe_templates() -> Iterable[tuple[str, str]]:
    for k in TEMPLATE_LIBRARY:
        yield k, TEMPLATE_DESCRIPTIONS.get(k, "")
