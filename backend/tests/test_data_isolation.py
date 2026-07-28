"""数据隔离与越权修复测试

测试覆盖:
- 认证边界：未登录/管理员/普通用户各自访问限制
- 会话隔离：用户 A 和 B 之间会话数据隔离
- 消息隔离：用户 A 和 B 之间消息数据隔离
- 创建安全：伪造 user_id 无效
- 管理员边界：管理员不能调用普通聊天接口
- 普通用户不能调用管理员接口

注意：所有 fixtures 为 module 作用域，DB 共享。每个测试负责清理自己创建的数据。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.chat import ChatSession, ChatMessage


# ============================================================================
# 认证边界测试
# ============================================================================

class TestAuthBoundaries:
    """认证边界测试。"""

    def test_unauthenticated_get_sessions_returns_401(self, client: TestClient):
        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 401

    def test_unauthenticated_create_session_returns_401(self, client: TestClient):
        response = client.post("/api/v1/chat/sessions", json={"title": "test"})
        assert response.status_code == 401

    def test_unauthenticated_send_message_returns_401(self, client: TestClient):
        response = client.post("/api/v1/chat/message", json={
            "session_id": 1, "question": "test"
        })
        assert response.status_code == 401

    def test_admin_access_user_chat_returns_403(self, client: TestClient, admin_headers: dict):
        response = client.post("/api/v1/chat", json={"question": "test"}, headers=admin_headers)
        assert response.status_code == 403

    def test_admin_access_user_sessions_returns_403(self, client: TestClient, admin_headers: dict):
        response = client.get("/api/v1/chat/sessions", headers=admin_headers)
        assert response.status_code == 403

    def test_normal_user_access_admin_endpoint_returns_403(self, client: TestClient, user_a_headers: dict):
        response = client.get("/api/v1/admin/users", headers=user_a_headers)
        assert response.status_code == 403

    def test_normal_user_access_admin_files_returns_403(self, client: TestClient, user_a_headers: dict):
        response = client.get("/api/v1/admin/files", headers=user_a_headers)
        assert response.status_code == 403

    def test_admin_access_admin_endpoint_succeeds(self, client: TestClient, admin_headers: dict):
        response = client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200


# ============================================================================
# 会话隔离测试
# ============================================================================

class TestSessionIsolation:
    """会话数据隔离测试。"""

    def test_user_a_creates_session_success(self, client: TestClient, user_a_headers: dict):
        response = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话"},
            headers=user_a_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session"]["title"] == "A的会话"

    def test_user_b_cannot_see_user_a_sessions(
        self, client: TestClient, user_a: User, user_b: User,
        user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 看不到 A 的会话。"""
        # A 创建会话
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_a_id = resp.json()["session"]["id"]

        # B 的会话列表不应包含 A 的会话
        resp2 = client.get("/api/v1/chat/sessions", headers=user_b_headers)
        assert resp2.status_code == 200
        session_ids = [s["id"] for s in resp2.json()["sessions"]]
        assert session_a_id not in session_ids

    def test_user_b_accesses_user_a_session_returns_404(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 访问 A 的会话应返回 404。"""
        # A 创建会话
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话2"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_a_id = resp.json()["session"]["id"]

        # B 尝试获取 A 的会话消息
        resp2 = client.get(
            f"/api/v1/chat/sessions/{session_a_id}/messages",
            headers=user_b_headers,
        )
        assert resp2.status_code == 404

    def test_user_b_cannot_update_user_a_session_title(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能修改 A 的会话标题。"""
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话3"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_a_id = resp.json()["session"]["id"]

        resp2 = client.put(
            f"/api/v1/chat/sessions/{session_a_id}/title",
            json={"title": "被B修改"},
            headers=user_b_headers,
        )
        assert resp2.status_code == 404

    def test_user_b_cannot_delete_user_a_session(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能删除 A 的会话。"""
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话4"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_a_id = resp.json()["session"]["id"]

        resp2 = client.delete(
            f"/api/v1/chat/sessions/{session_a_id}",
            headers=user_b_headers,
        )
        assert resp2.status_code == 404

    def test_user_b_cannot_clear_user_a_session(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能清空 A 的会话。"""
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的会话5"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_a_id = resp.json()["session"]["id"]

        resp2 = client.delete(
            f"/api/v1/chat/sessions/{session_a_id}/messages",
            headers=user_b_headers,
        )
        assert resp2.status_code == 404

    def test_user_a_can_operate_own_session(
        self, client: TestClient, user_a_headers: dict,
    ):
        """用户 A 可以正常操作自己的会话。"""
        # 创建
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "A的操作测试"},
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # 查看
        resp2 = client.get(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=user_a_headers,
        )
        assert resp2.status_code == 200

        # 修改标题
        resp3 = client.put(
            f"/api/v1/chat/sessions/{session_id}/title",
            json={"title": "A的新标题"},
            headers=user_a_headers,
        )
        assert resp3.status_code == 200
        assert resp3.json()["title"] == "A的新标题"

        # 删除
        resp4 = client.delete(
            f"/api/v1/chat/sessions/{session_id}",
            headers=user_a_headers,
        )
        assert resp4.status_code == 200

    def test_user_a_session_list_only_contains_own_sessions(
        self, client: TestClient, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 A 的会话列表只包含自己的会话。"""
        # A 和 B 各自创建会话
        resp_a = client.post("/api/v1/chat/sessions", json={"title": "A独有"}, headers=user_a_headers)
        resp_b = client.post("/api/v1/chat/sessions", json={"title": "B独有"}, headers=user_b_headers)
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        a_id = resp_a.json()["session"]["id"]
        b_id = resp_b.json()["session"]["id"]

        # A 的列表只含自己的会话
        resp = client.get("/api/v1/chat/sessions", headers=user_a_headers)
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()["sessions"]]
        assert a_id in ids
        assert b_id not in ids


# ============================================================================
# 消息隔离测试
# ============================================================================

class TestMessageIsolation:
    """消息数据隔离测试。"""

    def test_user_b_cannot_access_user_a_session_messages(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能获取 A 的会话消息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "A私聊"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        resp2 = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=user_b_headers)
        assert resp2.status_code == 404

    def test_user_a_can_access_own_session_messages(
        self, client: TestClient, user_a_headers: dict,
    ):
        """用户 A 可以查看自己会话的消息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "A的消息测试"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # 发送消息
        client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "你好"
        }, headers=user_a_headers)

        resp2 = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=user_a_headers)
        assert resp2.status_code == 200
        msgs = resp2.json()["messages"]
        assert len(msgs) >= 2  # user + assistant

    def test_user_b_cannot_delete_user_a_message(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能删除 A 的消息。"""
        # A 创建会话并发送消息
        resp = client.post("/api/v1/chat/sessions", json={"title": "A的消息"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # 通过 API 发送消息
        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "测试"
        }, headers=user_a_headers)
        assert resp2.status_code == 200
        msg_id = resp2.json()["user_message"]["id"]

        # B 尝试删除
        resp3 = client.delete(f"/api/v1/chat/messages/{msg_id}", headers=user_b_headers)
        assert resp3.status_code == 404

    def test_user_a_can_delete_own_message(
        self, client: TestClient, user_a_headers: dict,
    ):
        """用户 A 可以删除自己的消息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "可删除"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "删除测试"
        }, headers=user_a_headers)
        assert resp2.status_code == 200
        msg_id = resp2.json()["user_message"]["id"]

        resp3 = client.delete(f"/api/v1/chat/messages/{msg_id}", headers=user_a_headers)
        assert resp3.status_code == 200

    def test_user_b_cannot_submit_feedback_on_user_a_message(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能对 A 的消息提交反馈。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "反馈测试"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "需要反馈"
        }, headers=user_a_headers)
        assert resp2.status_code == 200
        asst_msg_id = resp2.json()["assistant_message"]["id"]

        resp3 = client.post(
            f"/api/v1/chat/messages/{asst_msg_id}/feedback",
            json={"rating": "like"},
            headers=user_b_headers,
        )
        assert resp3.status_code == 404

    def test_user_a_can_submit_feedback_on_own_message(
        self, client: TestClient, user_a_headers: dict,
    ):
        """用户 A 可以对助手消息提交反馈。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "反馈"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "评价"
        }, headers=user_a_headers)
        assert resp2.status_code == 200
        asst_msg_id = resp2.json()["assistant_message"]["id"]

        resp3 = client.post(
            f"/api/v1/chat/messages/{asst_msg_id}/feedback",
            json={"rating": "like"},
            headers=user_a_headers,
        )
        assert resp3.status_code == 200

    def test_user_b_cannot_send_message_to_user_a_session(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """用户 B 不能向 A 的会话发送消息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "A的私聊"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "B的入侵"
        }, headers=user_b_headers)
        assert resp2.status_code == 404


# ============================================================================
# 创建安全测试
# ============================================================================

class TestCreationSecurity:
    """创建资源时的安全验证。"""

    def test_session_created_with_correct_user_id(
        self, client: TestClient, user_a: User, user_a_headers: dict,
    ):
        """会话创建时 user_id 绑定到 current_user.id。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "安全测试"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # 验证列表中有且属于 A
        resp2 = client.get("/api/v1/chat/sessions", headers=user_a_headers)
        sessions = resp2.json()["sessions"]
        found = [s for s in sessions if s["id"] == session_id]
        assert len(found) == 1

    def test_clear_session_only_affects_own_data(
        self, client: TestClient, user_a: User, user_b: User,
        user_a_headers: dict, user_b_headers: dict,
    ):
        """清空会话只清空自己的会话，不影响他人。"""
        resp_a = client.post("/api/v1/chat/sessions", json={"title": "A清空测试"}, headers=user_a_headers)
        resp_b = client.post("/api/v1/chat/sessions", json={"title": "B保留"}, headers=user_b_headers)
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        a_session_id = resp_a.json()["session"]["id"]
        b_session_id = resp_b.json()["session"]["id"]

        # A 发送消息
        client.post("/api/v1/chat/message", json={
            "session_id": a_session_id, "question": "A的消息"
        }, headers=user_a_headers)

        # B 发送消息
        client.post("/api/v1/chat/message", json={
            "session_id": b_session_id, "question": "B的消息"
        }, headers=user_b_headers)

        # A 清空自己的会话
        resp_clear = client.delete(
            f"/api/v1/chat/sessions/{a_session_id}/messages",
            headers=user_a_headers,
        )
        assert resp_clear.status_code == 200

        # B 的消息不受影响
        resp_b_msgs = client.get(
            f"/api/v1/chat/sessions/{b_session_id}/messages",
            headers=user_b_headers,
        )
        assert resp_b_msgs.status_code == 200
        assert len(resp_b_msgs.json()["messages"]) >= 2

    def test_message_deletion_only_affects_target_message(
        self, client: TestClient, user_a_headers: dict,
    ):
        """删除消息只删除目标消息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "删除测试"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # 发送两条消息
        resp2 = client.post("/api/v1/chat/message", json={
            "session_id": session_id, "question": "问题1"
        }, headers=user_a_headers)
        msg1_id = resp2.json()["user_message"]["id"]
        msg2_id = resp2.json()["assistant_message"]["id"]

        # 删除第一条
        resp3 = client.delete(f"/api/v1/chat/messages/{msg1_id}", headers=user_a_headers)
        assert resp3.status_code == 200

        # 第二条仍存在
        resp4 = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=user_a_headers)
        remaining = [m for m in resp4.json()["messages"] if m["id"] == msg2_id]
        assert len(remaining) == 1


# ============================================================================
# 管理员边界测试
# ============================================================================

class TestAdminBoundaries:
    """管理员数据边界测试。"""

    def test_admin_can_access_admin_users(self, client: TestClient, admin_headers: dict):
        response = client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200

    def test_admin_cannot_use_chat_api(self, client: TestClient, admin_headers: dict):
        response = client.post("/api/v1/chat", json={"question": "test"}, headers=admin_headers)
        assert response.status_code == 403

    def test_admin_cannot_use_session_apis(self, client: TestClient, admin_headers: dict):
        resp = client.get("/api/v1/chat/sessions", headers=admin_headers)
        assert resp.status_code == 403

        resp = client.post("/api/v1/chat/sessions", json={"title": "test"}, headers=admin_headers)
        assert resp.status_code == 403

    def test_admin_chat_preview_works(self, client: TestClient, admin_headers: dict):
        response = client.post(
            "/api/v1/admin/chat-preview",
            json={"question": "测试"},
            headers=admin_headers,
        )
        assert response.status_code != 403

    def test_normal_user_cannot_use_admin_chat_preview(self, client: TestClient, user_a_headers: dict):
        response = client.post(
            "/api/v1/admin/chat-preview",
            json={"question": "test"},
            headers=user_a_headers,
        )
        assert response.status_code == 403

    def test_unauthorized_responds_with_401(self, client: TestClient):
        resp = client.get("/api/v1/chat/sessions")
        assert resp.status_code == 401

        resp = client.post("/api/v1/chat", json={"question": "test"})
        assert resp.status_code == 401


# ============================================================================
# 错误响应规范测试
# ============================================================================

class TestErrorResponses:
    """错误响应规范测试。"""

    def test_404_response_does_not_leak_info(
        self, client: TestClient, user_a: User, user_a_headers: dict, user_b_headers: dict,
    ):
        """404 响应不应泄露资源是否存在的信息。"""
        resp = client.post("/api/v1/chat/sessions", json={"title": "隐私"}, headers=user_a_headers)
        assert resp.status_code == 200
        session_id = resp.json()["session"]["id"]

        # B 访问存在的会话（不属于 B）→ 404
        resp1 = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=user_b_headers)
        assert resp1.status_code == 404

        # B 访问不存在的会话 → 404
        resp2 = client.get("/api/v1/chat/sessions/99999/messages", headers=user_b_headers)
        assert resp2.status_code == 404

    def test_401_response_format(self, client: TestClient):
        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 401

    def test_403_response_does_not_leak_internals(self, client: TestClient, user_a_headers: dict):
        response = client.get("/api/v1/admin/users", headers=user_a_headers)
        assert response.status_code == 403
        detail = str(response.json().get("detail", ""))
        assert "SQL" not in detail
        assert "traceback" not in detail.lower()


# ============================================================================
# Repository 层测试
# ============================================================================

class TestRepositoryOwnership:
    """Repository 层所有权验证测试。"""

    def test_get_message_by_id_for_user_enforces_ownership(
        self, db_session: Session, user_a: User, user_b: User
    ):
        from backend.app.repositories import chat_repository

        session_a = chat_repository.create_session(db_session, user_a.id, title="A的会话")
        msg = chat_repository.create_message(db_session, session_a.id, role="user", content="A的消息")
        db_session.commit()

        # A 可以获取
        assert chat_repository.get_message_by_id_for_user(db_session, msg.id, user_a.id) is not None
        # B 不能获取
        assert chat_repository.get_message_by_id_for_user(db_session, msg.id, user_b.id) is None

    def test_delete_message_for_user_enforces_ownership(
        self, db_session: Session, user_a: User, user_b: User
    ):
        from backend.app.repositories import chat_repository

        session_a = chat_repository.create_session(db_session, user_a.id, title="A的会话")
        msg = chat_repository.create_message(db_session, session_a.id, role="user", content="A的消息")
        db_session.commit()

        # B 不能删除
        assert chat_repository.delete_message_for_user(db_session, msg.id, user_b.id) is False
        # A 可以删除
        assert chat_repository.delete_message_for_user(db_session, msg.id, user_a.id) is True

    def test_clear_session_messages_for_user_enforces_ownership(
        self, db_session: Session, user_a: User, user_b: User
    ):
        from backend.app.repositories import chat_repository

        session_a = chat_repository.create_session(db_session, user_a.id, title="A的会话")
        chat_repository.create_message(db_session, session_a.id, role="user", content="A的消息")
        db_session.commit()

        # B 不能清空
        assert chat_repository.clear_session_messages_for_user(db_session, session_a.id, user_b.id) is None
        # A 可以清空
        assert chat_repository.clear_session_messages_for_user(db_session, session_a.id, user_a.id) == 1

    def test_get_message_count_for_user_enforces_ownership(
        self, db_session: Session, user_a: User, user_b: User
    ):
        from backend.app.repositories import chat_repository

        session_a = chat_repository.create_session(db_session, user_a.id, title="A的会话")
        chat_repository.create_message(db_session, session_a.id, role="user", content="A的消息")
        db_session.commit()

        # B 不能获取
        assert chat_repository.get_message_count_for_user(db_session, session_a.id, user_b.id) is None
        # A 可以获取
        assert chat_repository.get_message_count_for_user(db_session, session_a.id, user_a.id) == 1

    def test_get_session_by_id_requires_correct_user(
        self, db_session: Session, user_a: User, user_b: User
    ):
        from backend.app.repositories import chat_repository

        session_a = chat_repository.create_session(db_session, user_a.id, title="A的会话")
        db_session.commit()

        assert chat_repository.get_session_by_id(db_session, session_a.id, user_a.id) is not None
        assert chat_repository.get_session_by_id(db_session, session_a.id, user_b.id) is None
        assert chat_repository.get_session_by_id(db_session, 99999, user_a.id) is None
