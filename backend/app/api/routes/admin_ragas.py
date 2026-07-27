"""管理员 RAGAS 评估接口 — RAG 3.0 检索质量评估

权限:
- POST /api/v1/admin/ragas/evaluate: 需要管理员权限
- GET /api/v1/admin/ragas/report: 需要管理员权限
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from backend.app.models.user import User
from backend.app.security.dependencies import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAGAS评估"])


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class RAGASTestCase(BaseModel):
    """RAGAS 测试用例。"""

    question: str = Field(..., description="测试问题")
    reference_answer: Optional[str] = Field(None, description="参考答案")
    expected_concepts: list[str] = Field(default_factory=list, description="期望覆盖的关键概念")


class RAGASEvaluateRequest(BaseModel):
    """RAGAS 评估请求。"""

    test_cases: list[RAGASTestCase] = Field(..., description="测试用例列表")
    eval_type: str = Field(
        default="full", description="评估类型: full (完整) | retrieval_only (仅检索)"
    )
    use_default_cases: bool = Field(
        default=False, description="是否追加默认测试用例"
    )


class RAGASMetricsResponse(BaseModel):
    """RAGAS 评估指标。"""

    avg_context_precision: float = Field(0, description="平均检索准确率")
    avg_context_recall: float = Field(0, description="平均上下文召回率")
    avg_answer_relevancy: float = Field(0, description="平均答案相关性")
    refusal_rate: float = Field(0, description="拒答率")
    total_valid_cases: int = Field(0, description="有效测试用例数")


class RAGASEvaluateResponse(BaseModel):
    """RAGAS 评估响应。"""

    success: bool = Field(default=True)
    message: str = Field(default="评估完成")
    evaluated_at: Optional[str] = Field(None)
    total_cases: int = Field(0)
    valid_cases: int = Field(0)
    failed_cases: int = Field(0)
    total_latency_seconds: float = Field(0)
    metrics: Optional[RAGASMetricsResponse] = None
    details: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/admin/ragas/evaluate", response_model=RAGASEvaluateResponse)
async def run_ragas_evaluation(
    request: Request,
    body: RAGASEvaluateRequest,
    current_user: User = Depends(require_admin),
):
    """执行 RAGAS 评估。

    需要管理员权限。

    评估类型:
    - full: 完整评估（检索 + 生成答案 + 相关性评分）
    - retrieval_only: 仅评估检索质量（不调用 LLM，快速）
    """
    import sys
    from pathlib import Path

    settings = __import__('backend.app.config', fromlist=['get_settings']).get_settings()
    project_root = settings.PROJECT_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.ragas_evaluator import RAGASEvaluator, create_default_test_cases

    # 构建测试用例
    test_cases = [tc.model_dump() for tc in body.test_cases]
    if body.use_default_cases:
        test_cases.extend(create_default_test_cases())

    if not test_cases:
        return RAGASEvaluateResponse(
            success=False,
            message="没有提供测试用例",
        )

    # 初始化 RAG 服务
    try:
        from src.rag_service import RAGService
        rag_service = RAGService()
    except Exception as e:
        logger.error("RAG 服务初始化失败: %s", e)
        return RAGASEvaluateResponse(
            success=False,
            message=f"RAG 服务不可用: {str(e)[:200]}",
        )

    # 执行评估
    evaluator = RAGASEvaluator(rag_service=rag_service)

    if body.eval_type == "retrieval_only":
        report = evaluator.evaluate_retrieval_only(test_cases)
    else:
        report = evaluator.evaluate(test_cases)

    logger.info(
        "RAGAS 评估完成 | user=%s | type=%s | cases=%d | valid=%d",
        current_user.username,
        body.eval_type,
        report.get("total_cases", 0),
        report.get("valid_cases", 0),
    )

    metrics = report.get("metrics", {})
    return RAGASEvaluateResponse(
        success=True,
        message="评估完成",
        evaluated_at=report.get("evaluated_at"),
        total_cases=report.get("total_cases", 0),
        valid_cases=report.get("valid_cases", 0),
        failed_cases=report.get("failed_cases", 0),
        total_latency_seconds=report.get("total_latency_seconds", 0),
        metrics=RAGASMetricsResponse(
            avg_context_precision=metrics.get("avg_context_precision", 0),
            avg_context_recall=metrics.get("avg_context_recall", 0),
            avg_answer_relevancy=metrics.get("avg_answer_relevancy", 0),
            refusal_rate=metrics.get("refusal_rate", 0),
            total_valid_cases=metrics.get("total_valid_cases", 0),
        ) if metrics else None,
        details=report.get("details", []),
    )


@router.get("/admin/ragas/report")
async def get_last_ragas_report(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取最近一次 RAGAS 评估报告。

    需要管理员权限。
    """
    import sys
    from pathlib import Path

    settings = __import__('backend.app.config', fromlist=['get_settings']).get_settings()
    project_root = settings.PROJECT_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.ragas_evaluator import RAGASEvaluator

    evaluator = RAGASEvaluator()
    report = evaluator.get_last_report()

    if report is None:
        return {"success": True, "message": "暂无评估报告", "report": None}

    return {"success": True, "message": "获取成功", "report": report}
