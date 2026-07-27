"""系统设置服务 — 管理可动态配置的系统参数

提供:
- 读取所有设置
- 批量保存设置
- 获取单个设置
- 初始化默认设置

安全:
- 敏感设置值加密存储
- 不返回 JWT Secret 等敏感配置
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.system_setting import SystemSetting
from backend.app.services.encryption_service import encrypt, decrypt

logger = logging.getLogger(__name__)

# 默认设置
DEFAULT_SETTINGS = {
    "chat_max_context_length": {"value": "4000", "type": "int", "description": "最大上下文长度（tokens）"},
    "chat_max_answer_length": {"value": "2000", "type": "int", "description": "回答最大长度（tokens）"},
    "chat_history_days": {"value": "90", "type": "int", "description": "聊天历史保存天数"},
    "kb_chunk_size": {"value": "500", "type": "int", "description": "知识库 Chunk Size"},
    "kb_chunk_overlap": {"value": "50", "type": "int", "description": "知识库 Chunk Overlap"},
    "kb_top_k": {"value": "5", "type": "int", "description": "知识库检索 Top K"},
}

# 敏感设置键（需要加密存储）
SENSITIVE_KEYS = set()


class SystemSettingsService:
    """系统设置服务。"""

    def __init__(self, db: Session):
        self.db = db

    def get_all_settings(self) -> dict:
        """获取所有设置（键值对形式）。

        Returns
        -------
        dict
            {"chat_max_context_length": "4000", ...}
        """
        stmt = select(SystemSetting)
        rows = self.db.execute(stmt).scalars().all()

        result = {}
        for row in rows:
            value = row.value
            if row.type == "encrypted" and value:
                try:
                    value = decrypt(value)
                except Exception:
                    value = ""
            result[row.key] = value

        # 补充默认值
        for key, default in DEFAULT_SETTINGS.items():
            if key not in result:
                result[key] = default["value"]

        return result

    def get_setting(self, key: str) -> Optional[str]:
        """获取单个设置值。

        Parameters
        ----------
        key : str
            设置键

        Returns
        -------
        str or None
        """
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        row = self.db.execute(stmt).scalar_one_or_none()

        if row is None:
            # 返回默认值
            default = DEFAULT_SETTINGS.get(key)
            return default["value"] if default else None

        value = row.value
        if row.type == "encrypted" and value:
            try:
                value = decrypt(value)
            except Exception:
                value = ""
        return value

    def save_setting(self, key: str, value: str) -> SystemSetting:
        """保存单个设置。

        Parameters
        ----------
        key : str
            设置键
        value : str
            设置值

        Returns
        -------
        SystemSetting
        """
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        row = self.db.execute(stmt).scalar_one_or_none()

        setting_type = "string"
        default = DEFAULT_SETTINGS.get(key)
        if default:
            setting_type = default["type"]
        if key in SENSITIVE_KEYS:
            setting_type = "encrypted"

        store_value = value
        if setting_type == "encrypted" and value:
            store_value = encrypt(value)

        if row:
            row.value = store_value
            row.type = setting_type
        else:
            row = SystemSetting(
                key=key,
                value=store_value,
                type=setting_type,
                description=default["description"] if default else "",
            )
            self.db.add(row)

        self.db.flush()
        self.db.refresh(row)
        return row

    def save_settings_bulk(self, settings: dict) -> dict:
        """批量保存设置。

        Parameters
        ----------
        settings : dict
            设置键值对

        Returns
        -------
        dict
            保存后的所有设置
        """
        for key, value in settings.items():
            self.save_setting(key, str(value))
        self.db.flush()
        return self.get_all_settings()

    def init_defaults(self) -> None:
        """初始化默认设置（仅在不存在时创建）。"""
        for key, default in DEFAULT_SETTINGS.items():
            stmt = select(SystemSetting).where(SystemSetting.key == key)
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing is None:
                setting_type = default["type"]
                if key in SENSITIVE_KEYS:
                    setting_type = "encrypted"
                store_value = default["value"]
                if setting_type == "encrypted":
                    store_value = encrypt(default["value"])
                row = SystemSetting(
                    key=key,
                    value=store_value,
                    type=setting_type,
                    description=default["description"],
                )
                self.db.add(row)
        self.db.flush()
