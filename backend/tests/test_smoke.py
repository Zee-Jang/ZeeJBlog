from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.migrate import migrate_schema
from app.models import ChatThread, ThreadStatus, User, UserRole


ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "TestAdmin123"


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ensure_visitor() -> tuple[str, str]:
    email = "visitor@example.com"
    password = "Visitor123"
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                name="Visitor",
                nickname="Visitor",
                password_hash=hash_password(password),
                role=UserRole.visitor,
                is_active=True,
                token_version=1,
            )
            db.add(user)
            db.commit()
    return email, password


def _create_thread(user_a_email: str, user_b_email: str) -> int:
    with SessionLocal() as db:
        user_a = db.query(User).filter(User.email == user_a_email).one()
        user_b = db.query(User).filter(User.email == user_b_email).one()
        lo, hi = sorted((user_a.id, user_b.id))
        thread = (
            db.query(ChatThread)
            .filter(ChatThread.user_a_id == lo, ChatThread.user_b_id == hi)
            .first()
        )
        if not thread:
            thread = ChatThread(
                user_a_id=lo,
                user_b_id=hi,
                status=ThreadStatus.active,
            )
            db.add(thread)
            db.commit()
            db.refresh(thread)
        return thread.id


def test_health_and_auth_boundary(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "site": "zeej"}

    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_migration_is_idempotent(client: TestClient) -> None:
    # Startup already migrated once. Repeating the migration must be safe.
    migrate_schema()
    migrate_schema()
    assert client.get("/api/health").status_code == 200


def test_admin_can_hide_post_from_visitor(client: TestClient) -> None:
    admin_headers = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    visitor_email, visitor_password = _ensure_visitor()
    visitor_headers = _login(client, visitor_email, visitor_password)

    created = client.post(
        "/api/posts",
        headers=admin_headers,
        json={
            "kind": "muse",
            "title": "Takeover smoke test",
            "body": "This row exists only in the temporary test database.",
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]

    hidden = client.post(f"/api/posts/{post_id}/hide", headers=admin_headers)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["is_hidden"] is True

    visitor_posts = client.get("/api/posts", headers=visitor_headers)
    assert visitor_posts.status_code == 200, visitor_posts.text
    assert post_id not in {post["id"] for post in visitor_posts.json()}

    admin_posts = client.get("/api/posts", headers=admin_headers)
    assert admin_posts.status_code == 200, admin_posts.text
    assert post_id in {post["id"] for post in admin_posts.json()}


def test_recalled_message_keeps_quote_but_hides_original_content(client: TestClient) -> None:
    admin_headers = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    visitor_email, visitor_password = _ensure_visitor()
    visitor_headers = _login(client, visitor_email, visitor_password)
    thread_id = _create_thread(ADMIN_EMAIL, visitor_email)

    original = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        headers=visitor_headers,
        json={"content": "original message"},
    )
    assert original.status_code == 201, original.text
    original_id = original.json()["id"]

    reply = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        headers=visitor_headers,
        json={"content": "reply message", "reply_to_id": original_id},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["reply_to"]["content"] == "original message"

    recalled = client.post(
        f"/api/chat/messages/{original_id}/recall",
        headers=visitor_headers,
    )
    assert recalled.status_code == 200, recalled.text
    assert recalled.json()["recalled"] is True

    messages = client.get(
        f"/api/chat/threads/{thread_id}/messages",
        headers=admin_headers,
    )
    assert messages.status_code == 200, messages.text
    by_id = {message["id"]: message for message in messages.json()}
    assert by_id[original_id]["recalled"] is True
    quoted = by_id[reply.json()["id"]]["reply_to"]
    assert quoted["id"] == original_id
    assert quoted["recalled"] is True
    assert quoted["content"] == ""

    forbidden = client.post(
        f"/api/chat/messages/{reply.json()['id']}/recall",
        headers=admin_headers,
    )
    assert forbidden.status_code == 403


def test_admin_can_soft_delete_and_restore_user(client: TestClient) -> None:
    admin_headers = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    visitor_email, visitor_password = _ensure_visitor()
    visitor_headers = _login(client, visitor_email, visitor_password)
    with SessionLocal() as db:
        visitor_id = db.query(User).filter(User.email == visitor_email).one().id

    deleted = client.delete(
        f"/api/admin/users/{visitor_id}",
        headers=admin_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/auth/me", headers=visitor_headers).status_code == 401

    weak_password = client.post(
        f"/api/admin/users/{visitor_id}/restore",
        headers=admin_headers,
        json={"password": "short"},
    )
    assert weak_password.status_code == 422

    invalid_email = client.post(
        f"/api/admin/users/{visitor_id}/restore",
        headers=admin_headers,
        json={"email": "not-an-email", "password": "Restored123"},
    )
    assert invalid_email.status_code == 422

    restored = client.post(
        f"/api/admin/users/{visitor_id}/restore",
        headers=admin_headers,
        json={"password": "Restored123"},
    )
    assert restored.status_code == 200, restored.text

    restored_headers = _login(client, visitor_email, "Restored123")
    profile = client.get("/api/auth/me", headers=restored_headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["email"] == visitor_email
