"""统一路由注册"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import admin_api_config, admin_files, admin_rag_config, admin_ragas, admin_system, admin_users, auth, chat, health, system
from backend.app.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.API_PREFIX)

# 公开端点
api_router.include_router(health.router)
# 需登录端点
api_router.include_router(system.router)
api_router.include_router(chat.router)
api_router.include_router(auth.router)
# 管理员端点（Phase 3）
api_router.include_router(admin_files.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_system.router)
api_router.include_router(admin_system.logs_router)
api_router.include_router(admin_api_config.router)
api_router.include_router(admin_rag_config.router)
api_router.include_router(admin_ragas.router)
