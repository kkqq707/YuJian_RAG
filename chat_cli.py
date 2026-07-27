#!/usr/bin/env python
r"""企业知识库智能问答 — 命令行交互界面

启动: D:\projects\YuJian_RAG\.venv\Scripts\python.exe chat_cli.py

提供稳定的连续问答体验，显示回答与引用来源，
正确处理拒答、API 错误和退出命令。
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# 确保项目根目录在 sys.path 中
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# UTF-8 输出（Windows 终端兼容）
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 设置环境变量确保 Python 使用 UTF-8
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

WELCOME_BANNER = """========================================
企业知识库智能问答
答案基于企业内部知识库生成，请以正式文件为准。
输入 exit、quit 或 退出 可结束程序。
========================================"""

EXIT_COMMANDS = {"exit", "quit", "退出", "q"}

EXIT_MESSAGE = "已退出企业知识库问答系统。"

DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _safe_print(*args, **kwargs):
    """安全打印，处理 Windows 终端编码问题。"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 降级为 ASCII 安全输出
        safe_args = []
        for a in args:
            if isinstance(a, str):
                safe_args.append(a.encode("ascii", errors="replace").decode("ascii"))
            else:
                safe_args.append(str(a).encode("ascii", errors="replace").decode("ascii"))
        try:
            print(*safe_args, **kwargs)
        except Exception:
            # 最终降级
            print("[编码错误，无法显示此内容]")


def _safe_input(prompt: str = "") -> str:
    """安全读取用户输入，处理 EOF 和编码问题。"""
    try:
        return input(prompt)
    except EOFError:
        return ""
    except UnicodeDecodeError:
        _safe_print("[输入编码错误，请使用 UTF-8 编码]")
        return ""


def _is_exit_command(user_input: str) -> bool:
    """判断是否为退出命令。"""
    return user_input.strip().lower() in EXIT_COMMANDS


def _format_latency(seconds: float) -> str:
    """格式化延迟时间。"""
    if seconds < 0.01:
        return f"{seconds * 1000:.0f} 毫秒"
    elif seconds < 1.0:
        return f"{seconds:.2f} 秒"
    else:
        return f"{seconds:.2f} 秒"


# ---------------------------------------------------------------------------
# 启动检查
# ---------------------------------------------------------------------------


def check_startup() -> bool:
    """启动时依次检查环境是否可用。

    Returns
    -------
    bool
        True 表示所有检查通过，可以进入问答循环
    """
    # 1. 检查 Python 环境
    _safe_print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    _safe_print(f"项目路径: {_PROJECT_ROOT}")

    # 2. 检查向量库是否存在
    try:
        from src.vector_store import vector_store_exists
    except ImportError as e:
        _safe_print(f"导入模块失败: {e}")
        _safe_print("请确认已安装所有依赖: pip install -r requirements.txt")
        return False

    if not vector_store_exists():
        _safe_print()
        _safe_print("向量库不存在，请先运行：")
        _safe_print("python scripts/build_index.py --reset")
        _safe_print()
        return False

    _safe_print("向量库: 存在")

    # 3. 检查 LLM 配置是否有效
    from src.config import validate_llm_config, LLM_MODEL_NAME, LLM_PROVIDER

    cfg_result = validate_llm_config()
    if not cfg_result["valid"]:
        _safe_print()
        _safe_print("LLM 配置无效，无法启动：")
        for issue in cfg_result["issues"]:
            _safe_print(f"  - {issue}")
        _safe_print()
        _safe_print("请检查 .env 文件和系统环境变量配置。")
        return False

    _safe_print(f"LLM 提供方: {LLM_PROVIDER}")
    _safe_print(f"LLM 模型: {LLM_MODEL_NAME}")

    # 4. 检查 RAGService 是否能成功初始化
    try:
        from src.rag_service import RAGService
        RAGService()
    except FileNotFoundError as e:
        _safe_print()
        _safe_print(str(e))
        return False
    except Exception as e:
        _safe_print()
        _safe_print(f"RAG 服务初始化失败: {_sanitize_exception(e)}")
        if DEBUG:
            traceback.print_exc()
        return False

    _safe_print("RAG 服务: 初始化成功")
    _safe_print()
    return True


# ---------------------------------------------------------------------------
# 异常安全处理
# ---------------------------------------------------------------------------


def _sanitize_exception(exc: Exception) -> str:
    """对异常消息进行脱敏处理，不泄露 API Key 和完整堆栈。"""
    msg = str(exc)
    # 只取第一行
    first_line = msg.split("\n")[0]
    # 截断过长消息
    if len(first_line) > 200:
        first_line = first_line[:200] + "..."
    return first_line


def _handle_api_error(exc: Exception) -> str:
    """将 API 异常转换为安全的中文提示。"""
    from src.llm_client import sanitize_llm_error
    return sanitize_llm_error(exc)


# ---------------------------------------------------------------------------
# 结果显示
# ---------------------------------------------------------------------------


def _safe_num(value, default=0.0):
    """安全获取数值，None 时返回默认值。"""
    if value is None:
        return default
    return value


def _display_in_kb_answer(result: dict):
    """显示知识库内问题的回答和来源。"""
    _safe_print()
    _safe_print("回答：")
    _safe_print(result.get("answer", ""))
    _safe_print()

    sources = result.get("sources", [])
    if sources:
        _safe_print("引用来源：")
        for src in sources:
            file_name = src.get("file_name") or "未知文件"
            page = _safe_num(src.get("page"), 1)
            chunk_id = src.get("chunk_id") or "未知"
            relevance = _safe_num(src.get("relevance_score"), 0.0)
            preview = src.get("content_preview") or ""
            raw_distance = src.get("raw_distance")

            _safe_print()
            _safe_print(f"[{src.get('rank', '?')}] {file_name}，第 {page} 页")
            _safe_print(f"片段编号：{chunk_id}")
            _safe_print(f"相关度：{relevance:.4f}")
            if raw_distance is not None:
                _safe_print(f"距离（越小越相关）：{raw_distance:.4f}")
            if preview:
                _safe_print(f"原文预览：{preview}")

        _safe_print()

    # 统计
    _safe_print("统计：")
    _safe_print(f"- 检索片段数：{_safe_num(result.get('retrieved_count'), 0)}")
    _safe_print(f"- 实际使用片段数：{_safe_num(result.get('used_context_count'), 0)}")
    model_name = result.get("model") or "未调用"
    _safe_print(f"- 模型：{model_name}")
    _safe_print(f"- 总耗时：{_format_latency(_safe_num(result.get('latency_seconds'), 0))}")


def _display_refusal(result: dict):
    """显示拒答信息。"""
    _safe_print()
    _safe_print("回答：")
    _safe_print(result["answer"])
    _safe_print()

    refusal_reason = result.get("refusal_reason")
    if refusal_reason:
        _safe_print("说明：")
        _safe_print(f"当前问题与企业知识库内容相关性不足。")

    _safe_print()
    _safe_print("统计：")
    _safe_print(f"- 检索片段数：{result.get('retrieved_count', 0)}")
    _safe_print(f"- 实际使用片段数：0")
    _safe_print(f"- 未调用大模型")


def _display_result(result: dict):
    """根据结果类型显示回答或拒答信息。"""
    if result.get("refused"):
        _display_refusal(result)
    else:
        _display_in_kb_answer(result)


# ---------------------------------------------------------------------------
# 问答循环
# ---------------------------------------------------------------------------


def run_chat_loop():
    """主问答循环。"""
    from src.rag_service import RAGService

    try:
        rag_service = RAGService()
    except Exception as e:
        _safe_print(f"RAG 服务初始化失败: {_sanitize_exception(e)}")
        if DEBUG:
            traceback.print_exc()
        sys.exit(1)

    _safe_print(WELCOME_BANNER)

    while True:
        try:
            _safe_print()
            user_input = _safe_input("用户：")
        except (KeyboardInterrupt, EOFError):
            _safe_print()
            _safe_print(EXIT_MESSAGE)
            break

        # Ctrl+C 或 EOF 也检查退出
        if user_input == "":
            # 区分空输入和 EOF（空输入继续，EOF 在 _safe_input 已返回 ""）
            # 需要判断是否是真正的 EOF
            continue

        # 去除首尾空白
        user_input = user_input.strip()

        # 空输入不调用检索
        if not user_input:
            continue

        # 退出命令
        if _is_exit_command(user_input):
            _safe_print(EXIT_MESSAGE)
            break

        # 调用 RAGService
        _safe_print("正在检索知识库并生成回答……")

        try:
            result = rag_service.ask(user_input)
        except KeyboardInterrupt:
            _safe_print()
            _safe_print(EXIT_MESSAGE)
            break
        except EOFError:
            _safe_print()
            _safe_print(EXIT_MESSAGE)
            break
        except Exception as e:
            # API 错误安全处理
            error_msg = _sanitize_exception(e)

            # 优先使用 sanitize_llm_error
            try:
                from src.llm_client import sanitize_llm_error
                error_msg = sanitize_llm_error(e)
            except Exception:
                pass

            _safe_print()
            _safe_print(f"错误：{error_msg}")
            if DEBUG:
                _safe_print()
                traceback.print_exc()
            continue

        # 显示结果
        _display_result(result)

    _safe_print()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main():
    """程序入口。"""
    # 启动检查
    if not check_startup():
        sys.exit(1)

    # 进入问答循环
    run_chat_loop()


if __name__ == "__main__":
    main()
