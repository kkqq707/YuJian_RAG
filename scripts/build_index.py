"""build_index.py — 构建企业知识库向量索引

用法:
    python scripts/build_index.py          # 首次建库（库已存在则跳过）
    python scripts/build_index.py --reset  # 强制重建

从 data/builtin/ 和 data/uploads/ 读取所有知识文件。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 脚本从项目根目录启动，将项目根添加到 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="构建企业知识库向量索引")
    parser.add_argument(
        "--reset", action="store_true",
        help="强制删除已有向量库并重建",
    )
    args = parser.parse_args()

    # 延迟导入，避免脚本启动时的副作用
    from src.config import (
        DATA_DIR, BUILTIN_DATA_DIR, UPLOADS_DATA_DIR,
        STORAGE_DIR, COLLECTION_NAME, EMBEDDING_MODEL_NAME,
        CHUNK_SIZE, CHUNK_OVERLAP,
    )
    from src.document_loader import find_knowledge_files, load_documents
    from src.text_splitter import split_documents, deduplicate_chunks
    from src.embedding_model import get_embedding_model, get_embedding_device, test_embedding_model
    from src.vector_store import create_vector_store, load_vector_store, vector_store_exists

    # -----------------------------------------------------------------------
    # Step 0: 状态检查
    # -----------------------------------------------------------------------
    if not args.reset and vector_store_exists():
        print("向量库已存在，跳过建库。使用 --reset 强制重建。")
        return 0

    t_start = time.time()

    # -----------------------------------------------------------------------
    # Step 1: 扫描文件（builtin + uploads）
    # -----------------------------------------------------------------------
    files = find_knowledge_files()
    print(f"发现知识文件: {len(files)} 个")
    # 按来源分类
    builtin_files = []
    upload_files = []
    for f in files:
        try:
            f.resolve().relative_to(UPLOADS_DATA_DIR.resolve())
            upload_files.append(f)
        except ValueError:
            builtin_files.append(f)

    print(f"  内置知识库: {len(builtin_files)} 个")
    for f in builtin_files:
        print(f"    - {f.name}")
    print(f"  上传文件: {len(upload_files)} 个")
    for f in upload_files:
        print(f"    - {f.name}")

    # -----------------------------------------------------------------------
    # Step 2: 加载文档
    # -----------------------------------------------------------------------
    raw_docs = load_documents()
    print(f"原始 Document 数量: {len(raw_docs)}")

    # 统计来源
    builtin_count = sum(1 for d in raw_docs if d.metadata.get("knowledge_source") == "builtin")
    upload_count = sum(1 for d in raw_docs if d.metadata.get("knowledge_source") == "upload")
    print(f"  内置来源: {builtin_count} 个")
    print(f"  上传来源: {upload_count} 个")

    # -----------------------------------------------------------------------
    # Step 3: 切分
    # -----------------------------------------------------------------------
    chunks = split_documents(raw_docs)
    print(f"切分后 chunk 数量: {len(chunks)}")

    unique = deduplicate_chunks(chunks)
    if len(unique) != len(chunks):
        print(f"去重: {len(chunks)} → {len(unique)}")
    print(f"最终 chunk 数量: {len(unique)}")

    # -----------------------------------------------------------------------
    # Step 4: Embedding 模型
    # -----------------------------------------------------------------------
    device = get_embedding_device()
    print(f"Embedding 模型: {EMBEDDING_MODEL_NAME}")
    print(f"Embedding 设备: {device}")

    # 运行一次测试确认模型可用
    test_result = test_embedding_model()
    if not test_result["ok"]:
        print(f"[错误] Embedding 模型测试失败: {test_result['errors']}")
        return 1
    dim = test_result["dim"]
    print(f"向量维度: {dim}")

    # -----------------------------------------------------------------------
    # Step 5: 建库
    # -----------------------------------------------------------------------
    print(f"Collection: {COLLECTION_NAME}")
    print(f"持久化目录: {STORAGE_DIR / 'chroma_db'}")
    print(f"重建模式: {'是' if args.reset else '否'}")

    create_vector_store(unique, reset=args.reset)

    # -----------------------------------------------------------------------
    # Step 6: 验证
    # -----------------------------------------------------------------------
    vs = load_vector_store()
    collection = vs._collection
    count = collection.count()
    print(f"向量库验证: collection 中实际记录数 = {count}")

    if count != len(unique):
        print(f"[警告] 记录数 ({count}) 与 chunk 数 ({len(unique)}) 不一致！")
        return 1

    # -----------------------------------------------------------------------
    # Step 7: 最小检索验证
    # -----------------------------------------------------------------------
    from src.vector_store import similarity_search
    test_query = "煜见科技的主营业务是什么？"
    results = similarity_search(test_query, k=4)
    print(f"最小检索验证 (query='{test_query}'): 返回 {len(results)} 条结果")

    if not results:
        print("[警告] 检索返回空结果，请检查数据是否正常入库")
        return 1

    elapsed = time.time() - t_start
    print(f"建库耗时: {elapsed:.1f}s")
    print("建库完成 [OK]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
