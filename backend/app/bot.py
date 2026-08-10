"""DeepSeek-backed site chatbot helpers."""

from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy.orm import Session, joinedload

from app.auth import hash_password
from app.config import get_settings
from app.models import ChatMessage, ChatThread, MessageStatus, ThreadStatus, User, UserRole
from app.services import pair_ids

BOT_PASSWORD = "BotZeej9x"  # unused login; bot never authenticates via UI


def ensure_bot_user(db: Session) -> User:
    """确保 Bot 账号存在；不覆盖站长已改的昵称/简介/头像。"""
    from app.bot_prompt import BOT_BIO_KEY, BOT_NAME_KEY, ensure_bot_prompt
    from app.routers.site import get_setting

    settings = get_settings()
    email = (settings.bot_email or "bot@zeej.local").strip().lower()
    ensure_bot_prompt(db)
    bot = db.query(User).filter(User.email == email).first()
    default_name = (get_setting(db, BOT_NAME_KEY, "") or settings.bot_name or "Zeej Bot").strip()[
        :30
    ] or "Zeej Bot"
    default_bio = (
        get_setting(db, BOT_BIO_KEY, "") or settings.bot_bio or ""
    ).strip()[:500]
    if not bot:
        bot = User(
            email=email,
            name=default_name,
            nickname=default_name,
            password_hash=hash_password(BOT_PASSWORD),
            role=UserRole.visitor,
            bio=default_bio,
            allow_message_requests=True,
            show_email=False,
            show_join_date=True,
            token_version=1,
            is_active=True,
            bot_rounds_limit=0,
            bot_rounds_used=0,
            bot_msgs_per_round=100,
            bot_msgs_this_round=0,
        )
        db.add(bot)
        db.flush()
        return bot

    bot.is_active = True
    bot.allow_message_requests = True
    bot.muted_until = None
    bot.mute_reason = ""
    bot.bot_rounds_limit = 0
    return bot


def is_bot_user(user: User | None) -> bool:
    if not user:
        return False
    settings = get_settings()
    email = (settings.bot_email or "bot@zeej.local").strip().lower()
    return (user.email or "").strip().lower() == email


def get_or_create_bot_thread(db: Session, user: User) -> ChatThread:
    bot = ensure_bot_user(db)
    if user.id == bot.id:
        raise ValueError("cannot chat with self")
    a, b = pair_ids(user.id, bot.id)
    thread = (
        db.query(ChatThread)
        .options(joinedload(ChatThread.messages))
        .filter(ChatThread.user_a_id == a, ChatThread.user_b_id == b)
        .first()
    )
    if not thread:
        thread = ChatThread(user_a_id=a, user_b_id=b, status=ThreadStatus.active)
        db.add(thread)
        db.flush()
    else:
        thread.status = ThreadStatus.active
        thread.updated_at = datetime.utcnow()
    return thread


def clear_thread_messages(db: Session, thread: ChatThread) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id, ChatMessage.deleted_at.is_(None))
        .all()
    )
    for m in rows:
        m.deleted_at = now
    thread.updated_at = now
    return len(rows)


async def call_deepseek(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    key = (settings.deepseek_api_key or "").strip()
    if not key:
        return "机器人尚未配置 API Key，请稍后再试。"

    base = (settings.deepseek_base_url or "https://api.deepseek.com").rstrip("/")
    model = (settings.deepseek_model or "deepseek-v4-flash").strip()
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # V4 Flash 默认开启 thinking，站内闲聊关闭以降低延迟与费用
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Zeej-Blog-Bot/1.0",
    }
    timeout = httpx.Timeout(60.0, connect=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError:
        return "暂时连不上模型服务，请稍后再试。"
    except Exception:
        return "助手刚才出了点小状况，请稍后再试～"

    if res.status_code >= 400:
        return f"模型调用失败（{res.status_code}），请稍后再试。"

    try:
        data = res.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = (msg.get("content") or "").strip()
        if text:
            return text[:2000]
    except Exception:
        pass
    return "模型没有返回有效内容，请换个说法再试。"


FALLBACK_BOT_REPLY = "助手暂时没法回复，请稍后再试～ 🌿"


def _reload_bot_message(db: Session, msg_id: int) -> ChatMessage:
    return (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.sender))
        .filter(ChatMessage.id == msg_id)
        .one()
    )


async def generate_bot_reply(db: Session, *, thread: ChatThread, bot: User, human: User) -> ChatMessage | None:
    """生成并写入 Bot 回复。模型失败会写成友好文案；仅在无法落库时返回 None。"""
    from app.bot_prompt import build_full_system_prompt

    _ = human
    settings = get_settings()
    limit = max(4, min(80, int(settings.bot_history_limit or 30)))
    try:
        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == thread.id, ChatMessage.deleted_at.is_(None))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        history.reverse()

        llm_messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": build_full_system_prompt(db),
            }
        ]
        for m in history:
            role = "assistant" if m.sender_id == bot.id else "user"
            content = (m.content or "").strip()
            if content:
                llm_messages.append({"role": role, "content": content})

        reply = await call_deepseek(llm_messages)
    except Exception:
        reply = FALLBACK_BOT_REPLY

    reply = (reply or "").strip() or FALLBACK_BOT_REPLY

    try:
        msg = ChatMessage(
            thread_id=thread.id,
            sender_id=bot.id,
            content=reply[:2000],
            status=MessageStatus.sent,
        )
        thread.updated_at = datetime.utcnow()
        db.add(msg)
        db.commit()
    except Exception:
        db.rollback()
        try:
            msg = ChatMessage(
                thread_id=thread.id,
                sender_id=bot.id,
                content=FALLBACK_BOT_REPLY,
                status=MessageStatus.sent,
            )
            thread.updated_at = datetime.utcnow()
            db.add(msg)
            db.commit()
        except Exception:
            db.rollback()
            return None
        try:
            return _reload_bot_message(db, msg.id)
        except Exception:
            return msg

    try:
        return _reload_bot_message(db, msg.id)
    except Exception:
        # 已成功写入，勿再插兜底消息 / 勿触发退款
        return msg
