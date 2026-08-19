from sqlalchemy import inspect, text

from app.database import Base, engine


def _has_column(table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def migrate_schema() -> None:
    """SQLite 轻量迁移：补列；聊天表若仍是旧 visitor 结构则重建。"""
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    user_cols = [
        ("nickname", "ALTER TABLE users ADD COLUMN nickname VARCHAR(30) DEFAULT ''"),
        ("avatar_url", "ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"),
        ("bio", "ALTER TABLE users ADD COLUMN bio VARCHAR(500) DEFAULT ''"),
        ("is_active", "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"),
        ("allow_message_requests", "ALTER TABLE users ADD COLUMN allow_message_requests BOOLEAN DEFAULT 1"),
        ("show_email", "ALTER TABLE users ADD COLUMN show_email BOOLEAN DEFAULT 0"),
        ("show_join_date", "ALTER TABLE users ADD COLUMN show_join_date BOOLEAN DEFAULT 1"),
        ("token_version", "ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1"),
        ("last_login_at", "ALTER TABLE users ADD COLUMN last_login_at DATETIME"),
        ("updated_at", "ALTER TABLE users ADD COLUMN updated_at DATETIME"),
        ("muted_until", "ALTER TABLE users ADD COLUMN muted_until DATETIME"),
        ("mute_reason", "ALTER TABLE users ADD COLUMN mute_reason VARCHAR(120) DEFAULT ''"),
        ("registered_invite_code", "ALTER TABLE users ADD COLUMN registered_invite_code VARCHAR(64) DEFAULT ''"),
        ("bot_rounds_limit", "ALTER TABLE users ADD COLUMN bot_rounds_limit INTEGER DEFAULT 10"),
        ("bot_rounds_used", "ALTER TABLE users ADD COLUMN bot_rounds_used INTEGER DEFAULT 0"),
        ("bot_msgs_per_round", "ALTER TABLE users ADD COLUMN bot_msgs_per_round INTEGER DEFAULT 100"),
        ("bot_msgs_this_round", "ALTER TABLE users ADD COLUMN bot_msgs_this_round INTEGER DEFAULT 0"),
        ("previous_email", "ALTER TABLE users ADD COLUMN previous_email VARCHAR(255)"),
        ("previous_nickname", "ALTER TABLE users ADD COLUMN previous_nickname VARCHAR(30)"),
    ]
    if "users" in tables:
        with engine.begin() as conn:
            for name, sql in user_cols:
                if not _has_column("users", name):
                    conn.execute(text(sql))
            # 把旧 name 同步到 nickname
            conn.execute(
                text(
                    "UPDATE users SET nickname = name "
                    "WHERE (nickname IS NULL OR nickname = '') AND name IS NOT NULL"
                )
            )

    invite_cols = [
        ("note", "ALTER TABLE invite_codes ADD COLUMN note VARCHAR(200) DEFAULT ''"),
        ("is_active", "ALTER TABLE invite_codes ADD COLUMN is_active BOOLEAN DEFAULT 1"),
        ("expires_at", "ALTER TABLE invite_codes ADD COLUMN expires_at DATETIME"),
        ("created_by_id", "ALTER TABLE invite_codes ADD COLUMN created_by_id INTEGER"),
    ]
    if "invite_codes" in tables:
        with engine.begin() as conn:
            for name, sql in invite_cols:
                if not _has_column("invite_codes", name):
                    conn.execute(text(sql))

    # 旧聊天结构（visitor_id）无法兼容 peer 私聊，开发期直接重建
    if "chat_threads" in tables and _has_column("chat_threads", "visitor_id"):
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS chat_messages"))
            conn.execute(text("DROP TABLE IF EXISTS chat_threads"))
        Base.metadata.create_all(bind=engine)

    if "chat_messages" in tables and not _has_column("chat_messages", "deleted_at"):
        # 可能刚重建过；再检查一次
        if "chat_messages" in inspect(engine).get_table_names() and not _has_column(
            "chat_messages", "deleted_at"
        ):
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN deleted_at DATETIME"))

    if "chat_messages" in inspect(engine).get_table_names() and not _has_column(
        "chat_messages", "recalled_at"
    ):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN recalled_at DATETIME"))

    if "chat_messages" in inspect(engine).get_table_names():
        with engine.begin() as conn:
            if not _has_column("chat_messages", "reply_to_id"):
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN reply_to_id INTEGER"))
            if not _has_column("chat_messages", "reply_sender_name"):
                conn.execute(
                    text("ALTER TABLE chat_messages ADD COLUMN reply_sender_name VARCHAR(100)")
                )
            if not _has_column("chat_messages", "reply_content_snapshot"):
                conn.execute(
                    text(
                        "ALTER TABLE chat_messages ADD COLUMN reply_content_snapshot VARCHAR(500)"
                    )
                )

    project_cols = [
        ("github_url", "ALTER TABLE projects ADD COLUMN github_url VARCHAR(500)"),
        ("readme", "ALTER TABLE projects ADD COLUMN readme TEXT DEFAULT ''"),
        ("owner_id", "ALTER TABLE projects ADD COLUMN owner_id INTEGER"),
        ("created_at", "ALTER TABLE projects ADD COLUMN created_at DATETIME"),
    ]
    if "projects" in inspect(engine).get_table_names():
        with engine.begin() as conn:
            for name, sql in project_cols:
                if not _has_column("projects", name):
                    conn.execute(text(sql))

    if "posts" in inspect(engine).get_table_names():
        with engine.begin() as conn:
            if not _has_column("posts", "on_home"):
                conn.execute(text("ALTER TABLE posts ADD COLUMN on_home BOOLEAN DEFAULT 0"))
            if not _has_column("posts", "is_hidden"):
                conn.execute(text("ALTER TABLE posts ADD COLUMN is_hidden BOOLEAN DEFAULT 0"))
