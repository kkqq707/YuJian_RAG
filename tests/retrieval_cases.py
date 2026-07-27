"""tests/retrieval_cases.py — 检索评测问题集

基于真实知识库内容设计，用于验证检索质量和校准拒答阈值。
知识库文件:
  - data/成都市煜见科技有限公司完整介绍.txt
  - data/公司信息.txt

所有 expected_keywords 必须来自知识库真实内容，不得猜测。
"""

from __future__ import annotations

from typing import TypedDict


class RetrievalCase(TypedDict, total=False):
    """单条评测数据。"""
    question: str
    expected_keywords: list[str] | None   # 仅 in_scope 有
    expected_file: str | None              # 仅 in_scope 有
    category: str                          # "in_scope" | "out_of_scope"


# ===================================================================
# 知识库内问题（in_scope）- 至少 8 个
# ===================================================================

IN_SCOPE_CASES: list[RetrievalCase] = [
    # --- 公司基本介绍 ---
    {
        "question": "煜见科技是做什么的？",
        "expected_keywords": ["GEO", "AI搜索", "引流", "AI搜索优化"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },
    {
        "question": "煜见科技的公司全称是什么？",
        "expected_keywords": ["成都市煜见科技有限公司"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },
    {
        "question": "煜见科技是什么时候成立的？",
        "expected_keywords": ["2026", "04月10日"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },
    {
        "question": "煜见科技的办公地址在哪里？",
        "expected_keywords": ["成华区", "成致路", "银龙国际"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },

    # --- 核心业务 / 产品 ---
    {
        "question": "煜见搜荐是什么？",
        "expected_keywords": ["GEO", "生成引擎优化", "AI流量获客"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },
    {
        "question": "煜见科技有哪些核心产品？",
        "expected_keywords": ["GEO", "AI搜索推荐", "私域定向投放", "煜见智能体"],
        "expected_file": "公司信息.txt",
        "category": "in_scope",
    },
    {
        "question": "私域定向投放系统覆盖哪些平台？",
        "expected_keywords": ["微信", "朋友圈", "视频号", "公众号"],
        "expected_file": "公司信息.txt",
        "category": "in_scope",
    },
    {
        "question": "煜见智能体有哪些功能？",
        "expected_keywords": ["数字员工", "自动", "办公", "自媒体"],
        "expected_file": "公司信息.txt",
        "category": "in_scope",
    },

    # --- 技术优势 ---
    {
        "question": "煜见科技的技术优势是什么？",
        "expected_keywords": ["全链路自研", "底层算法", "合规"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },

    # --- 服务对象 / 应用场景 ---
    {
        "question": "煜见科技主要服务哪些客户？",
        "expected_keywords": ["餐饮", "美业", "本地生活", "实体店"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },

    # --- 招商加盟 ---
    {
        "question": "煜见科技提供招商加盟吗？",
        "expected_keywords": ["招商", "加盟", "源码", "代理"],
        "expected_file": "成都市煜见科技有限公司完整介绍.txt",
        "category": "in_scope",
    },

    # --- 解决方案 ---
    {
        "question": "本地生活商户如何通过煜见科技获客？",
        "expected_keywords": ["GEO", "微信", "私域", "龙虾智能体"],
        "expected_file": "公司信息.txt",
        "category": "in_scope",
    },
]


# ===================================================================
# 知识库外问题（out_of_scope）- 至少 4 个
# ===================================================================

OUT_OF_SCOPE_CASES: list[RetrievalCase] = [
    {
        "question": "今天成都天气怎么样？",
        "category": "out_of_scope",
    },
    {
        "question": "如何治疗感冒？",
        "category": "out_of_scope",
    },
    {
        "question": "Python怎么写快速排序？",
        "category": "out_of_scope",
    },
    {
        "question": "美国总统是谁？",
        "category": "out_of_scope",
    },
    {
        "question": "2024年奥运会在哪里举办？",
        "category": "out_of_scope",
    },
    {
        "question": "红烧肉怎么做？",
        "category": "out_of_scope",
    },
]


# ===================================================================
# 汇总
# ===================================================================

ALL_CASES: list[RetrievalCase] = IN_SCOPE_CASES + OUT_OF_SCOPE_CASES


def get_in_scope_cases() -> list[RetrievalCase]:
    return list(IN_SCOPE_CASES)


def get_out_of_scope_cases() -> list[RetrievalCase]:
    return list(OUT_OF_SCOPE_CASES)


def get_all_cases() -> list[RetrievalCase]:
    return list(ALL_CASES)
