"""下载 Reranker 模型到本地 — BAAI/bge-reranker-base

用于企业私有化部署场景，将模型下载到 backend/models/bge-reranker-base/。
下载完成后创建 .model_ready 标志文件，后续启动自动使用本地模型，无需联网。

必需文件:
    - config.json              (模型配置)
    - tokenizer.json           (分词器)
    - tokenizer_config.json    (分词器配置)
    - special_tokens_map.json  (特殊 token 映射)
    - model.safetensors        (模型权重)
    - .model_ready             (就绪标志)

用法:
    python scripts/download_reranker.py

使用镜像加速（国内推荐）:
    set HF_ENDPOINT=https://hf-mirror.com
    python scripts/download_reranker.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 不在脚本内导入 src.config（会设置离线模式阻止下载）
# 直接获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"
TARGET_DIR = PROJECT_ROOT / "backend" / "models" / "bge-reranker-base"
MODEL_READY_FLAG = ".model_ready"

# 国内用户推荐使用镜像
_DEFAULT_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

# 需要下载的核心文件
REQUIRED_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "model.safetensors",
    "sentencepiece.bpe.model",
]


def main():
    print("=" * 60)
    print("  Reranker 模型本地化下载")
    print("=" * 60)
    print(f"  模型: {RERANKER_MODEL_NAME}")
    print(f"  目标: {TARGET_DIR}")
    print(f"  镜像: {_DEFAULT_ENDPOINT}")
    print(f"  必需文件: {', '.join(REQUIRED_FILES)}")
    print()

    # 检查是否已存在完整
    ready_flag = TARGET_DIR / MODEL_READY_FLAG
    if ready_flag.exists() and (TARGET_DIR / "config.json").exists():
        all_present = True
        for f in REQUIRED_FILES:
            if not (TARGET_DIR / f).exists():
                all_present = False
                print(f"[WARN] 缺少文件: {f}")
        if all_present:
            print("[OK] 模型已存在且完整，无需重新下载")
            print(f"     路径: {TARGET_DIR}")
            return

    # 创建目标目录
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 临时关闭离线模式以允许下载
    for env_var in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"]:
        os.environ.pop(env_var, None)
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"
    os.environ["HF_DATASETS_OFFLINE"] = "0"

    try:
        from huggingface_hub import snapshot_download

        print("[下载] 正在从 HuggingFace 下载模型文件...")
        print("       这可能需要几分钟（模型约 1.1 GB），请耐心等待...")

        snapshot_download(
            repo_id=RERANKER_MODEL_NAME,
            local_dir=str(TARGET_DIR),
            endpoint=_DEFAULT_ENDPOINT,
            ignore_patterns=[
                "*.flax*",
                "*.msgpack",
                "*.h5",
                "*.ot",
                "*.onnx",
                "onnx/*",
                "flax_model.*",
                "tf_model.*",
                "rust_model.*",
            ],
        )

        # 验证完整性
        missing = []
        for f in REQUIRED_FILES:
            if not (TARGET_DIR / f).exists():
                missing.append(f)

        if missing:
            print(f"\n[ERROR] 下载不完整，缺少文件: {missing}")
            print("        请重新运行脚本")
            sys.exit(1)

        # 创建下载完成标志
        ready_flag.touch()
        print(f"\n[OK] 模型下载完成!")
        print(f"     路径: {TARGET_DIR}")

        # 列出下载的文件
        print("\n  文件列表:")
        for f in sorted(TARGET_DIR.iterdir()):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    {f.name} ({size_mb:.1f} MB)")

        # 清理缓存
        cache_dir = TARGET_DIR / ".cache"
        if cache_dir.exists():
            import shutil
            shutil.rmtree(str(cache_dir), ignore_errors=True)
            print("\n  已清理临时缓存")

    except ImportError:
        print("[ERROR] 未安装 huggingface_hub 库")
        print("        请运行: pip install huggingface_hub")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        print()
        print("  可能的原因:")
        print("    1. 网络无法访问 HuggingFace 或镜像")
        print("    2. 磁盘空间不足（需要约 1.5 GB）")
        print()
        print("  解决方案:")
        print("    1. 检查网络连接")
        print("    2. 尝试不同镜像: set HF_ENDPOINT=https://hf-mirror.com")
        print("    3. 手动下载模型文件放到:", TARGET_DIR)
        print(f"       需要文件: {', '.join(REQUIRED_FILES)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
