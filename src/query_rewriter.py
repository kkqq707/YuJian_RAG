"""Query Rewrite 查询改写模块 — 企业知识库场景优化

将用户的简短口语化查询改写为适合检索的精确查询语句。

企业场景优化:
- 补充企业上下文（制度、流程、规范等）
- 展开缩写和简称
- 添加同义词和相关术语
- 保持原始语义不变

示例:
  输入: "怎么请假"
  改写: "查询企业员工请假制度、审批流程、假期规则"

  输入: "加班费"
  改写: "企业加班费计算标准、加班审批流程、加班补贴政策"

配置:
  QUERY_REWRITE_ENABLE: bool — 是否启用查询改写（默认 True）
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 查询改写 Prompt 模板
_QUERY_REWRITE_PROMPT = """你是一个企业知识库查询优化助手。你的任务是将用户简短的口语化问题改写为适合检索的精确查询语句。

改写规则：
1. 补充企业场景上下文（制度、流程、规范、标准等）
2. 展开缩写和简称
3. 添加相关同义词和术语
4. 保持原始语义不变
5. 不要添加问题中没有的信息
6. 只返回改写后的查询文本，不要添加任何解释

用户问题：{question}

改写后的查询："""

# 备选：使用规则改写（无需 LLM 调用，零延迟）
_ENTERPRISE_RULES = {
    "请假": "企业员工请假制度 请假审批流程 假期类型 请假天数规定",
    "加班": "加班申请流程 加班费计算标准 加班补贴政策 调休制度",
    "报销": "费用报销流程 报销审批制度 报销标准 差旅报销规定",
    "入职": "新员工入职流程 入职手续 入职培训 试用期规定",
    "离职": "员工离职流程 离职手续 离职交接 离职结算",
    "考核": "绩效考核制度 KPI考核标准 绩效评估流程 绩效面谈要求",
    "薪资": "薪酬管理制度 工资结构 薪资调整 薪资保密规定",
    "培训": "员工培训制度 培训计划 培训考核 内外部培训规定",
    "福利": "员工福利政策 五险一金 补充福利 节日福利标准",
    "合同": "劳动合同管理 合同签订流程 合同续签 合同终止规定",
    "安全": "安全生产制度 安全操作规程 安全检查标准 事故报告流程",
    "出差": "出差申请流程 出差标准 差旅报销 出差报告要求",
    "采购": "采购管理制度 采购审批流程 供应商管理 采购验收标准",
    "会议": "会议管理制度 会议室预约 会议纪要要求 会议决策流程",
    "印章": "印章管理制度 用印申请流程 印章保管 用印审批权限",
    "oa": "OA办公系统使用说明 OA审批流程 OA操作指南",
    "erp": "ERP企业资源计划系统 进销存管理",
    "hr": "人力资源管理 HR系统操作 HR政策 人力资源制度",
    "财务": "财务管理制度 财务报表 预算管理 成本控制",
}


def rewrite_query(
    question: str,
    use_llm: bool = False,
    llm_client=None,
) -> str:
    """对用户查询进行改写优化。

    Parameters
    ----------
    question : str
        原始用户问题
    use_llm : bool
        是否使用 LLM 改写（默认 False，使用规则改写）
    llm_client : optional
        LLM 客户端实例（use_llm=True 时必需）

    Returns
    -------
    str
        改写后的查询文本
    """
    if not question or not question.strip():
        return question

    question = question.strip()

    # 策略 1: LLM 改写（更精确，但有延迟）
    if use_llm and llm_client:
        return _rewrite_with_llm(question, llm_client)

    # 策略 2: 规则改写（零延迟，适合企业场景）
    return _rewrite_with_rules(question)


def _rewrite_with_rules(question: str) -> str:
    """基于预定义规则的查询改写（零延迟）。

    识别问题中的关键词，返回对应的扩展查询。
    如果没有匹配的规则，返回原始问题。
    """
    # 查找匹配的关键词
    matched_expansions = []
    for keyword, expansion in _ENTERPRISE_RULES.items():
        if keyword.lower() in question.lower():
            matched_expansions.append(expansion)

    if matched_expansions:
        # 合并原始问题和所有匹配的扩展
        combined = " ".join(matched_expansions)
        # 如果扩展已经很长，直接使用；否则添加原始问题
        if len(combined) >= len(question):
            return combined
        else:
            return f"{question} {combined}"

    # 没有匹配规则：检查是否为短查询（< 10 字），如果是则添加通用企业知识库前缀
    if len(question) < 10:
        return f"企业 {question} 制度 流程 规定"

    return question


def _rewrite_with_llm(question: str, llm_client) -> str:
    """使用 LLM 进行查询改写。

    Parameters
    ----------
    question : str
        原始用户问题
    llm_client
        LLM 客户端（如 ChatOpenAI 实例）

    Returns
    -------
    str
        改写后的查询；LLM 调用失败时返回原始问题
    """
    prompt = _QUERY_REWRITE_PROMPT.format(question=question)

    try:
        from langchain_core.messages import HumanMessage
        response = llm_client.invoke([HumanMessage(content=prompt)])
        if hasattr(response, "content"):
            rewritten = response.content.strip()
        else:
            rewritten = str(response).strip()

        # 安全检查：改写结果不应为空或过短
        if rewritten and len(rewritten) >= len(question):
            logger.info("Query Rewrite: '%s' → '%s'", question, rewritten)
            return rewritten
        else:
            logger.warning("Query Rewrite 结果异常（过短），使用原始查询: '%s'", question)
            return question

    except Exception as e:
        logger.warning("Query Rewrite LLM 调用失败，使用原始查询: %s", str(e)[:100])
        return question


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 是否启用查询改写（可通过环境变量或数据库配置控制）
QUERY_REWRITE_ENABLE = True


def is_query_rewrite_enabled() -> bool:
    """检查查询改写是否已启用。"""
    try:
        from src.config import RERANK_ENABLE  # 复用类似逻辑
    except ImportError:
        pass
    return QUERY_REWRITE_ENABLE


def set_query_rewrite_enabled(enabled: bool) -> None:
    """设置查询改写启用状态（供管理后台调用）。"""
    global QUERY_REWRITE_ENABLE
    QUERY_REWRITE_ENABLE = enabled
    logger.info("Query Rewrite 状态变更: %s", "启用" if enabled else "关闭")
