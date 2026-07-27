"""src/retrieval_judge.py — 检索置信度判断与拒答策略

基于多维度的检索结果质量评估，决定是否可以安全地将检索结果
送入大模型进行回答。

所有阈值来自 config.py，语义明确：
  - MAX_RAW_DISTANCE: L2 距离上限（超过视为不相关）
  - MIN_RELEVANCE_SCORE: 余弦相似度下限（低于视为不相关）
  - MIN_TOP1_TOP2_RELEVANCE_GAP: Top1 与 Top2 最小分差
  - MIN_VALID_CHUNKS: 至少需要的有效片段数
"""

from __future__ import annotations

from src.config import (
    MAX_RAW_DISTANCE,
    MIN_RELEVANCE_SCORE,
    MIN_TOP1_TOP2_RELEVANCE_GAP,
    MIN_VALID_CHUNKS,
)
from src.vector_store import RetrievalScore


def count_valid_chunks(
    scores: list[RetrievalScore],
    min_relevance: float | None = None,
) -> int:
    """统计达到相关度阈值的有效片段数。

    Parameters
    ----------
    scores : list[RetrievalScore]
    min_relevance : float, optional
        相关度阈值，默认使用 config.MIN_RELEVANCE_SCORE

    Returns
    -------
    int
    """
    threshold = min_relevance if min_relevance is not None else MIN_RELEVANCE_SCORE
    return sum(1 for rs in scores if rs.relevance_score >= threshold)


def is_retrieval_confident(
    results: list[tuple[any, RetrievalScore]],
) -> tuple[bool, str]:
    """多维度判断检索结果是否足够可靠，可以送入大模型回答。

    判断维度：
    1. 是否有有效结果
    2. Top 1 的距离是否在阈值内
    3. Top 1 的相关度是否达到阈值
    4. Top 1 与 Top 2 的差距是否足够大（避免无明确最佳匹配）
    5. 有效片段数量是否足够

    基于当前 12 题评测集校准的初始保守策略。
    样本量有限（12 题），后续应扩大评测集重新校准。

    Parameters
    ----------
    results : list[tuple[Document, RetrievalScore]]
        按 relevance_score 降序排列的检索结果

    Returns
    -------
    tuple[bool, str]
        - bool: 是否允许进入大模型回答
        - str: 判断原因（中文）
    """
    # 维度 1: 是否有结果
    if not results:
        return False, "未检索到任何有效片段"

    top1_rs = results[0][1]

    # 维度 2: Top 1 的 L2 距离是否过大
    if top1_rs.raw_distance > MAX_RAW_DISTANCE:
        return False, (
            f"Top 1 的 L2 距离 ({top1_rs.raw_distance:.4f}) "
            f"超过阈值 ({MAX_RAW_DISTANCE})，最相关片段距离过大"
        )

    # 维度 3: Top 1 的相关度是否过低
    if top1_rs.relevance_score < MIN_RELEVANCE_SCORE:
        return False, (
            f"Top 1 相关度 ({top1_rs.relevance_score:.4f}) "
            f"低于阈值 ({MIN_RELEVANCE_SCORE})，最相关片段不够可靠"
        )

    # 维度 4: Top 1 与 Top 2 的差距
    if len(results) >= 2:
        top2_rs = results[1][1]
        gap = top1_rs.relevance_score - top2_rs.relevance_score
        if gap < MIN_TOP1_TOP2_RELEVANCE_GAP:
            return False, (
                f"Top 1 与 Top 2 的相关度差距 ({gap:.4f}) "
                f"小于阈值 ({MIN_TOP1_TOP2_RELEVANCE_GAP})，检索结果之间缺乏一致性"
            )

    # 维度 5: 有效片段数
    scores = [rs for _, rs in results]
    valid_count = count_valid_chunks(scores)
    if valid_count < MIN_VALID_CHUNKS:
        return False, (
            f"有效片段数 ({valid_count}) 不足，"
            f"至少需要 {MIN_VALID_CHUNKS} 个达到阈值的片段"
        )

    return True, "检索置信度通过"


def diagnose_retrieval(
    results: list[tuple[any, RetrievalScore]],
) -> dict:
    """生成检索结果的详细诊断信息（用于调试和分析）。

    Parameters
    ----------
    results : list[tuple[Document, RetrievalScore]]

    Returns
    -------
    dict
    """
    if not results:
        return {
            "has_results": False,
            "message": "无检索结果",
            "is_confident": False,
        }

    scores = [rs for _, rs in results]
    top1 = scores[0]

    confident, reason = is_retrieval_confident(results)

    info = {
        "has_results": True,
        "result_count": len(results),
        "top1_raw_distance": round(top1.raw_distance, 6),
        "top1_relevance_score": round(top1.relevance_score, 6),
        "valid_chunks": count_valid_chunks(scores),
        "is_confident": confident,
        "reason": reason,
    }

    if len(scores) >= 2:
        top2 = scores[1]
        info["top2_raw_distance"] = round(top2.raw_distance, 6)
        info["top2_relevance_score"] = round(top2.relevance_score, 6)
        info["top1_top2_gap"] = round(top1.relevance_score - top2.relevance_score, 6)

    # 距离分布
    info["distance_range"] = {
        "min": round(min(s.raw_distance for s in scores), 6),
        "max": round(max(s.raw_distance for s in scores), 6),
        "mean": round(sum(s.raw_distance for s in scores) / len(scores), 6),
    }

    # 每个维度的独立判断
    checks = {
        "has_results": True,
        "top1_distance_ok": top1.raw_distance <= MAX_RAW_DISTANCE,
        "top1_relevance_ok": top1.relevance_score >= MIN_RELEVANCE_SCORE,
    }

    if len(scores) >= 2:
        gap = top1.relevance_score - scores[1].relevance_score
        checks["top1_top2_gap_ok"] = gap >= MIN_TOP1_TOP2_RELEVANCE_GAP

    checks["valid_chunks_ok"] = count_valid_chunks(scores) >= MIN_VALID_CHUNKS

    info["checks"] = checks

    return info
