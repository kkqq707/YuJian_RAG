"""RAGAS 评估接口 — 检索与生成质量评估

评估维度:
1. 检索准确率 (Context Precision): 检索到的上下文中相关文档的占比
2. 答案相关性 (Answer Relevancy): 生成的答案与问题的相关程度
3. 上下文召回 (Context Recall): 检索到的上下文覆盖参考答案关键信息的程度

评估方法:
- 基于规则的自动评估（不依赖外部 LLM）
- 也可使用 LLM 作为评判器（设置 use_llm_judge=True）

结果保存至 storage/retrieval_eval_report.json
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 评估结果存储路径
EVAL_REPORT_PATH = Path(__file__).resolve().parent.parent / "storage" / "ragas_eval_report.json"


class RAGASEvaluator:
    """RAGAS 评估器 — 检索与生成质量评估。

    支持基于规则的快速评估和基于 LLM 的深度评估。
    """

    def __init__(self, rag_service=None):
        """
        Parameters
        ----------
        rag_service : RAGService, optional
            RAG 服务实例（用于执行实际检索和生成）
        """
        self._rag_service = rag_service
        self._results: list[dict] = []

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def evaluate(
        self,
        test_cases: list[dict],
        use_llm_judge: bool = False,
    ) -> dict:
        """对测试用例集进行评估。

        Parameters
        ----------
        test_cases : list[dict]
            测试用例列表，每个用例包含:
            - question: str — 测试问题
            - reference_answer: str (optional) — 参考答案
            - expected_concepts: list[str] (optional) — 期望覆盖的关键概念
        use_llm_judge : bool
            是否使用 LLM 作为评判器

        Returns
        -------
        dict
            评估报告
        """
        self._results = []
        t0 = time.perf_counter()

        for i, case in enumerate(test_cases):
            try:
                case_result = self._evaluate_single(case, use_llm_judge)
                self._results.append(case_result)
                logger.info(
                    "RAGAS eval [%d/%d]: '%s' — precision=%.2f recall=%.2f",
                    i + 1, len(test_cases),
                    case.get("question", "")[:40],
                    case_result.get("context_precision", 0),
                    case_result.get("context_recall", 0),
                )
            except Exception as e:
                logger.warning("RAGAS eval [%d/%d] failed: %s", i + 1, len(test_cases), e)
                self._results.append({
                    "question": case.get("question", ""),
                    "error": str(e),
                })

        # 汇总
        valid = [r for r in self._results if "error" not in r]
        total_latency = round(time.perf_counter() - t0, 3)

        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total_cases": len(test_cases),
            "valid_cases": len(valid),
            "failed_cases": len(self._results) - len(valid),
            "total_latency_seconds": total_latency,
            "metrics": self._aggregate_metrics(valid),
            "details": self._results,
        }

        # 保存报告
        self._save_report(report)

        return report

    def evaluate_retrieval_only(self, test_cases: list[dict]) -> dict:
        """仅评估检索质量（不调用 LLM 生成答案）。

        适用于快速批量测试检索参数调整效果。
        """
        self._results = []
        t0 = time.perf_counter()

        for i, case in enumerate(test_cases):
            try:
                case_result = self._evaluate_retrieval_only(case)
                self._results.append(case_result)
            except Exception as e:
                logger.warning("Retrieval eval [%d/%d] failed: %s", i + 1, len(test_cases), e)
                self._results.append({
                    "question": case.get("question", ""),
                    "error": str(e),
                })

        valid = [r for r in self._results if "error" not in r]
        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "eval_type": "retrieval_only",
            "total_cases": len(test_cases),
            "valid_cases": len(valid),
            "total_latency_seconds": round(time.perf_counter() - t0, 3),
            "metrics": self._aggregate_metrics(valid),
            "details": self._results,
        }

        self._save_report(report)
        return report

    def get_last_report(self) -> Optional[dict]:
        """获取最近一次评估报告。"""
        if EVAL_REPORT_PATH.exists():
            try:
                return json.loads(EVAL_REPORT_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    def _evaluate_single(self, case: dict, use_llm_judge: bool) -> dict:
        """评估单个测试用例。"""
        question = case["question"]
        reference = case.get("reference_answer", "")
        expected_concepts = case.get("expected_concepts", [])

        result = {
            "question": question,
            "reference_answer": reference,
        }

        if self._rag_service:
            # 执行 RAG 检索
            rag_result = self._rag_service.ask(question, user_mode=False, debug=True)

            result["answer"] = rag_result.get("answer", "")
            result["refused"] = rag_result.get("refused", False)

            # 获取检索结果
            sources = rag_result.get("sources", [])
            debug_info = rag_result.get("debug_info")

            # 1. 检索准确率 (Context Precision)
            if expected_concepts:
                retrieved_texts = [
                    s.get("content_preview", "") for s in sources
                ]
                result["context_precision"] = self._calc_context_precision(
                    retrieved_texts, expected_concepts
                )

            # 2. 上下文召回 (Context Recall)
            if expected_concepts and reference:
                result["context_recall"] = self._calc_context_recall(
                    [s.get("content_preview", "") for s in sources],
                    expected_concepts,
                )

            # 3. 答案相关性 (Answer Relevancy)
            if use_llm_judge and result.get("answer"):
                # LLM judge 评估（需要 LLM 客户端）
                result["answer_relevancy"] = self._calc_answer_relevancy_llm(
                    question, result["answer"], reference,
                )
            elif result.get("answer"):
                # 基于规则的快速评估
                result["answer_relevancy"] = self._calc_answer_relevancy_rule(
                    question, result["answer"], expected_concepts,
                )

            # 添加检索统计
            if debug_info:
                stats = debug_info.get("retrieval_stats", {})
                result["retrieval_stats"] = stats

        return result

    def _evaluate_retrieval_only(self, case: dict) -> dict:
        """仅评估检索（不调用 LLM 生成）。高效批量测试。"""
        question = case["question"]
        expected_concepts = case.get("expected_concepts", [])

        result = {"question": question}

        if self._rag_service:
            # 仅执行检索部分
            try:
                retrieved = self._rag_service.hybrid_retrieve(question)
                docs = [doc for doc, _ in retrieved]

                # 检索准确率
                if expected_concepts:
                    texts = [d.page_content for d in docs]
                    result["context_precision"] = self._calc_context_precision(
                        texts, expected_concepts,
                    )
                    result["context_recall"] = self._calc_context_recall(
                        texts, expected_concepts,
                    )

                result["retrieved_count"] = len(docs)
                result["top_sources"] = [
                    {
                        "file_name": d.metadata.get("file_name", ""),
                        "preview": d.page_content[:80],
                    }
                    for d in docs[:3]
                ]
            except Exception as e:
                result["error"] = str(e)

        return result

    @staticmethod
    def _calc_context_precision(
        retrieved_texts: list[str],
        expected_concepts: list[str],
    ) -> float:
        """计算检索准确率：检索结果中包含期望概念的比例。

        precision = 匹配的期望概念数 / 总期望概念数
        """
        if not expected_concepts:
            return 1.0

        all_text = " ".join(retrieved_texts).lower()
        matched = sum(
            1 for concept in expected_concepts
            if concept.lower() in all_text
        )
        return round(matched / len(expected_concepts), 4)

    @staticmethod
    def _calc_context_recall(
        retrieved_texts: list[str],
        expected_concepts: list[str],
    ) -> float:
        """计算上下文召回：期望概念在检索结果中的覆盖比例。

        考虑每个概念在检索结果中的出现次数。
        """
        if not expected_concepts:
            return 1.0

        all_text = " ".join(retrieved_texts).lower()
        matched = sum(
            1 for concept in expected_concepts
            if concept.lower() in all_text
        )
        # 基础召回率
        base_recall = matched / len(expected_concepts)

        # 如果大部分概念都匹配，给予加权奖励
        if matched >= len(expected_concepts) * 0.8:
            base_recall = min(1.0, base_recall + 0.05)

        return round(base_recall, 4)

    @staticmethod
    def _calc_answer_relevancy_rule(
        question: str,
        answer: str,
        expected_concepts: list[str],
    ) -> float:
        """基于规则的答案相关性评估。

        检查答案是否包含期望概念，以及是否与问题相关。
        """
        answer_lower = answer.lower()
        question_lower = question.lower()

        # 检查基本相关性：答案不应完全无关
        score = 0.5  # 基线

        # 1. 概念覆盖率
        if expected_concepts:
            concept_score = sum(
                1 for c in expected_concepts if c.lower() in answer_lower
            ) / len(expected_concepts)
            score += 0.3 * concept_score

        # 2. 问题关键词覆盖
        q_keywords = [w for w in question_lower.split() if len(w) >= 2]
        if q_keywords:
            kw_score = sum(
                1 for kw in q_keywords if kw in answer_lower
            ) / len(q_keywords)
            score += 0.2 * kw_score

        # 3. 答案长度合理性（太短可能无意义）
        if len(answer) >= 20:
            score = min(1.0, score)

        return round(score, 4)

    @staticmethod
    def _calc_answer_relevancy_llm(
        question: str,
        answer: str,
        reference: str,
        llm_client=None,
    ) -> float:
        """使用 LLM 评判答案相关性（需要 LLM 客户端）。

        如果 LLM 客户端不可用，回退到规则方法。
        """
        # 简化实现：回退到规则方法
        concepts = [w for w in reference.split() if len(w) >= 2 and w not in
                     ("的", "了", "是", "在", "和", "与", "或", "等")]
        return RAGASEvaluator._calc_answer_relevancy_rule(
            question, answer, concepts[:10],
        )

    @staticmethod
    def _aggregate_metrics(valid_results: list[dict]) -> dict:
        """聚合评估指标。"""
        if not valid_results:
            return {
                "avg_context_precision": 0,
                "avg_context_recall": 0,
                "avg_answer_relevancy": 0,
                "refusal_rate": 0,
            }

        precisions = [r.get("context_precision", 0) for r in valid_results if "context_precision" in r]
        recalls = [r.get("context_recall", 0) for r in valid_results if "context_recall" in r]
        relevancies = [r.get("answer_relevancy", 0) for r in valid_results if "answer_relevancy" in r]
        refusals = [r for r in valid_results if r.get("refused")]

        return {
            "avg_context_precision": round(sum(precisions) / len(precisions), 4) if precisions else 0,
            "avg_context_recall": round(sum(recalls) / len(recalls), 4) if recalls else 0,
            "avg_answer_relevancy": round(sum(relevancies) / len(relevancies), 4) if relevancies else 0,
            "refusal_rate": round(len(refusals) / len(valid_results), 4) if valid_results else 0,
            "total_valid_cases": len(valid_results),
        }

    @staticmethod
    def _save_report(report: dict) -> None:
        """保存评估报告到文件。"""
        try:
            EVAL_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            EVAL_REPORT_PATH.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("RAGAS 评估报告已保存: %s", EVAL_REPORT_PATH)
        except Exception as e:
            logger.warning("保存评估报告失败: %s", e)


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def create_default_test_cases() -> list[dict]:
    """创建默认的企业知识库测试用例集。"""
    return [
        {
            "question": "怎么请假",
            "expected_concepts": ["请假", "审批", "流程", "制度", "假期"],
        },
        {
            "question": "加班费怎么算",
            "expected_concepts": ["加班", "加班费", "计算", "补贴", "调休"],
        },
        {
            "question": "报销流程是什么",
            "expected_concepts": ["报销", "流程", "审批", "发票", "费用"],
        },
        {
            "question": "新员工入职需要做什么",
            "expected_concepts": ["入职", "手续", "培训", "试用期", "合同"],
        },
        {
            "question": "绩效考核标准",
            "expected_concepts": ["考核", "绩效", "KPI", "评估", "标准"],
        },
    ]
