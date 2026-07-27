"""inspect_retrieval.py — 检视检索结果

运行方式:
    .venv/Scripts/python.exe scripts/inspect_retrieval.py "用户问题"
    .venv/Scripts/python.exe scripts/inspect_retrieval.py "用户问题" --top-k 4 --show-preview
    .venv/Scripts/python.exe scripts/inspect_retrieval.py "用户问题" --json

功能:
  - 不调用大模型
  - 显示每条结果的 raw_distance、relevance_score、排名、来源
  - 支持 JSON 模式输出
  - 空问题给出中文用法提示
  - 向量库不存在时提示先建库
  - 对重复 chunk 去重
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _truncate(text: str, max_chars: int = 200) -> str:
    """截断文本到指定字符数。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _format_result(
    rank: int,
    doc,
    rs,          # RetrievalScore
    show_preview: bool,
) -> str:
    """格式化单条检索结果。"""
    meta = doc.metadata
    lines = [
        f"--- 排名 #{rank} ---",
        f"  file_name     : {meta.get('file_name', '?')}",
        f"  page          : {meta.get('page', '?')}",
        f"  chunk_id      : {meta.get('chunk_id', '?')}",
        f"  raw_distance  : {rs.raw_distance:.6f}  (越小越相关)",
        f"  relevance_score: {rs.relevance_score:.6f}  (越大越相关，余弦相似度)",
    ]
    if show_preview:
        preview = _truncate(doc.page_content, 200)
        lines.append(f"  text_preview  : {preview}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检视检索结果（不调用大模型）",
        usage="\n  .venv/Scripts/python.exe scripts/inspect_retrieval.py \"问题\" [选项]\n"
              "  .venv/Scripts/python.exe scripts/inspect_retrieval.py --help",
    )
    parser.add_argument(
        "question", nargs="?", default="",
        help="要检索的问题（中文）",
    )
    parser.add_argument(
        "--top-k", type=int, default=4,
        help="返回结果数（默认 4）",
    )
    parser.add_argument(
        "--show-preview", action="store_true",
        help="显示文本预览（最多 200 字）",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_mode",
        help="JSON 模式输出结构化结果",
    )
    args = parser.parse_args()

    # 空问题
    if not args.question.strip():
        if args.json_mode:
            print(json.dumps({
                "error": True,
                "message": "请提供要检索的问题。用法: python scripts/inspect_retrieval.py \"问题\"",
            }, ensure_ascii=False))
        else:
            print("请提供要检索的问题。")
            print()
            print("用法:")
            print("  .venv/Scripts/python.exe scripts/inspect_retrieval.py \"问题\"")
            print("  .venv/Scripts/python.exe scripts/inspect_retrieval.py \"问题\" --top-k 4")
            print("  .venv/Scripts/python.exe scripts/inspect_retrieval.py \"问题\" --show-preview")
            print("  .venv/Scripts/python.exe scripts/inspect_retrieval.py \"问题\" --json")
            print()
            print("功能:")
            print("  检视向量检索结果，明确显示 raw_distance 和 relevance_score。")
            print("  不调用大模型，不输出完整知识库。")
        return 0 if args.question else 1

    # 检查向量库
    from src.vector_store import vector_store_exists
    if not vector_store_exists():
        msg = "向量库不存在，请先运行: python scripts/build_index.py --reset"
        if args.json_mode:
            print(json.dumps({"error": True, "message": msg}, ensure_ascii=False))
        else:
            print(f"[错误] {msg}")
        return 1

    if args.top_k <= 0:
        msg = f"top_k 必须大于 0，当前值: {args.top_k}"
        if args.json_mode:
            print(json.dumps({"error": True, "message": msg}, ensure_ascii=False))
        else:
            print(f"[错误] {msg}")
        return 1

    # 执行检索
    from src.vector_store import similarity_search_with_relevance

    try:
        results = similarity_search_with_relevance(args.question, k=args.top_k)
    except ValueError as e:
        msg = f"查询参数无效: {e}"
        if args.json_mode:
            print(json.dumps({"error": True, "message": msg}, ensure_ascii=False))
        else:
            print(f"[错误] {msg}")
        return 1

    # 去重（基于 chunk_id）
    seen_ids: set[str] = set()
    deduped: list = []
    for doc, rs in results:
        cid = doc.metadata.get("chunk_id", "")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        deduped.append((doc, rs))

    if not deduped:
        msg = "未检索到任何结果"
        if args.json_mode:
            print(json.dumps({"error": False, "results": [], "count": 0, "message": msg}, ensure_ascii=False))
        else:
            print(msg)
        return 0

    # --- 输出 ---
    if args.json_mode:
        output_results = []
        for rank, (doc, rs) in enumerate(deduped, start=1):
            meta = doc.metadata
            entry = {
                "rank": rank,
                "file_name": meta.get("file_name", ""),
                "page": meta.get("page", 0),
                "chunk_id": meta.get("chunk_id", ""),
                "raw_distance": round(rs.raw_distance, 6),
                "relevance_score": round(rs.relevance_score, 6),
            }
            if args.show_preview:
                entry["text_preview"] = _truncate(doc.page_content, 200)
            output_results.append(entry)

        output = {
            "error": False,
            "query": args.question,
            "top_k": args.top_k,
            "direction_note": "raw_distance 越小越相关，relevance_score 越大越相关（余弦相似度）",
            "count": len(output_results),
            "results": output_results,
        }
        # 确保 Windows 控制台 UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    # 文本模式
    print(f"查询: {args.question}")
    print(f"返回结果数: {len(deduped)}（去重后）")
    print(f"评分方向: raw_distance 越小越相关 | relevance_score 越大越相关（余弦相似度）")
    print()

    for rank, (doc, rs) in enumerate(deduped, start=1):
        print(_format_result(rank, doc, rs, args.show_preview))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
