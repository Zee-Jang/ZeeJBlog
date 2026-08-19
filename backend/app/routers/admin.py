from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import display_name, require_admin
from app.database import get_db
from app.models import (
    ChatMessage,
    ChatThread,
    InviteCode,
    NotificationType,
    ThreadStatus,
    User,
    UserRole,
)
from app.schemas import MessageOk, PublicUserOut, UtcDateTimeOpt
from app.services import (
    clear_mute_notifications,
    mute_active,
    push_notification,
    push_unmute_notification,
    upsert_mute_notification,
)
from app.routers.site import (
    DEFAULT_HOME_LEAD,
    DEFAULT_HOME_LEADS,
    get_home_leads,
    set_home_leads,
    set_setting,
)
from app.timeutil import EAST_ASIA, UTC

router = APIRouter(prefix="/api/admin", tags=["admin"])

MUTE_REASONS = {
    "content_violation": "内容违规",
    "spam": "垃圾信息 / 骚扰广告",
    "harassment": "人身攻击 / 骚扰",
    "other": "其他",
}


class MuteIn(BaseModel):
    reason: str = Field(default="content_violation", max_length=40)
    reason_detail: str = Field(default="", max_length=300)
    duration_hours: int | None = Field(
        default=24,
        description="禁言时长（小时）。null 表示永久（10 年）。已禁言时为加时。",
    )


class AdminNotifyIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=500)
    # null / 省略 = 群发给所有活跃用户；指定 id = 单发
    user_id: int | None = None


class SiteSettingsOut(BaseModel):
    home_lead: str = ""
    home_leads: dict[str, str] = Field(default_factory=dict)


class SiteSettingsIn(BaseModel):
    home_lead: str | None = Field(default=None, max_length=800)
    home_leads: dict[str, str] | None = None


class AdminUserOut(PublicUserOut):
    email: str | None = None
    role: UserRole
    is_active: bool
    muted_until: UtcDateTimeOpt = None
    mute_reason: str = ""
    created_at: UtcDateTimeOpt = None
    last_login_at: UtcDateTimeOpt = None
    mute_remaining_days: int | None = None
    bot_preset: str = "normal"
    bot_rounds_limit: int = 10
    bot_rounds_used: int = 0
    bot_rounds_remaining: int = 10
    bot_msgs_per_round: int = 100
    bot_msgs_this_round: int = 0
    bot_msgs_remaining: int = 100
    is_bot: bool = False


class AdminUserDetailOut(AdminUserOut):
    registered_invite_code: str = ""
    inviter_nickname: str | None = None
    inviter_id: int | None = None
    message_count: int = 0
    password_note: str = "密码已加密保存，站长无法查看明文"
    previous_email: str | None = None
    previous_nickname: str | None = None


class RestoreUserIn(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    nickname: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=6, max_length=128)


class RestoreChatIn(BaseModel):
    user_a_id: int
    user_b_id: int


class AdminThreadOut(BaseModel):
    thread_id: int
    peer_id: int
    peer_nickname: str
    peer_active: bool
    message_count: int
    hidden_count: int
    status: ThreadStatus


class RestoreChatOut(BaseModel):
    detail: str
    restored: int
    thread_id: int


class BotPermissionIn(BaseModel):
    preset: str = Field(description="none | normal | limited")


class BotProfileIn(BaseModel):
    nickname: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=500)


class BotPromptIn(BaseModel):
    system_prompt: str = Field(default="", max_length=100000)
    mode: str = Field(default="replace", description="replace | append")


class BotDocIn(BaseModel):
    name: str = Field(default="notes.txt", max_length=120)
    content: str = Field(default="", max_length=50000)


def _remaining_days(until: datetime | None, now: datetime | None = None) -> int | None:
    if not until:
        return None
    now = now or datetime.utcnow()
    if until <= now:
        return 0
    # ceil days
    secs = (until - now).total_seconds()
    return max(1, int((secs + 86399) // 86400))


def _to_list_item(u: User) -> AdminUserOut:
    from app.bot import is_bot_user
    from app.bot_quota import bot_quota_snapshot

    muted = mute_active(u)
    snap = bot_quota_snapshot(u)
    return AdminUserOut(
        id=u.id,
        nickname=u.nickname or u.name,
        avatar_url=u.avatar_url,
        bio=u.bio or "",
        allow_message_requests=u.allow_message_requests,
        created_at=u.created_at,
        email=u.email,
        is_muted=muted,
        role=u.role,
        is_active=u.is_active,
        muted_until=u.muted_until if muted else None,
        mute_reason=(u.mute_reason or "") if muted else "",
        last_login_at=u.last_login_at,
        mute_remaining_days=_remaining_days(u.muted_until) if muted else None,
        bot_preset=snap["preset"],
        bot_rounds_limit=snap["rounds_limit"],
        bot_rounds_used=snap["rounds_used"],
        bot_rounds_remaining=snap["rounds_remaining"],
        bot_msgs_per_round=snap["msgs_per_round"],
        bot_msgs_this_round=snap["msgs_this_round"],
        bot_msgs_remaining=snap["msgs_remaining"],
        is_bot=is_bot_user(u),
    )


def _inviter_info(db: Session, code: str) -> tuple[str | None, int | None]:
    if not code:
        return None, None
    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if not invite or not invite.created_by_id:
        return None, None
    creator = db.get(User, invite.created_by_id)
    if not creator:
        return None, invite.created_by_id
    return display_name(creator), creator.id


@router.get("/users", response_model=list[AdminUserOut])
def list_all_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminUserOut]:
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [_to_list_item(u) for u in rows]


@router.get("/users/{user_id}", response_model=AdminUserDetailOut)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AdminUserDetailOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    base = _to_list_item(user)
    code = (user.registered_invite_code or "").strip()
    inviter_name, inviter_id = _inviter_info(db, code)
    msg_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.sender_id == user.id, ChatMessage.deleted_at.is_(None))
        .count()
    )
    return AdminUserDetailOut(
        **base.model_dump(),
        registered_invite_code=code,
        inviter_nickname=inviter_name,
        inviter_id=inviter_id,
        message_count=msg_count,
        password_note="密码已加密保存，站长无法查看明文",
        previous_email=user.previous_email,
        previous_nickname=user.previous_nickname,
    )


@router.get("/users/{user_id}/messages/export")
def export_user_messages(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PlainTextResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    rows = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.sender))
        .filter(ChatMessage.sender_id == user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    lines = [
        f"# messages by {display_name(user)} (id={user.id})",
        f"# exported_at={datetime.now(UTC).astimezone(EAST_ASIA).isoformat()}",
        f"# count={len(rows)}",
        "",
    ]
    for m in rows:
        stamp = ""
        if m.created_at:
            stamp = m.created_at.replace(tzinfo=UTC).astimezone(EAST_ASIA).strftime("%Y-%m-%d %H:%M:%S")
        deleted = ""
        if m.recalled_at:
            deleted = " [recalled]"
        elif m.deleted_at:
            deleted = " [deleted]"
        content = (m.content or "").replace("\r\n", "\n")
        lines.append(f"[{stamp}] thread={m.thread_id} status={m.status}{deleted}")
        lines.append(content)
        lines.append("---")
    body = "\n".join(lines) + "\n"
    filename = f"messages-user-{user.id}.txt"
    return PlainTextResponse(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/users/{user_id}/mute", response_model=MessageOk)
def mute_user(
    user_id: int,
    payload: MuteIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能禁言站长")
    from app.bot import is_bot_user

    if is_bot_user(user):
        raise HTTPException(status_code=400, detail="不能禁言 Bot 账号")
    reason_key = payload.reason if payload.reason in MUTE_REASONS else "other"
    reason_label = MUTE_REASONS[reason_key]
    detail = (payload.reason_detail or "").strip()
    hours = payload.duration_hours
    now = datetime.utcnow()
    already = bool(user.muted_until and user.muted_until > now)

    if hours is None or hours <= 0:
        until = now + timedelta(days=3650)
        action_text = "已更新为永久禁言" if already else "你已被站长禁言（永久）"
    else:
        base = user.muted_until if already else now
        until = base + timedelta(hours=hours)
        if hours < 24:
            add_text = f"{hours} 小时"
        elif hours % 24 == 0:
            add_text = f"{hours // 24} 天"
        else:
            add_text = f"{hours} 小时"
        action_text = f"禁言已续时 +{add_text}" if already else f"你已被站长禁言（{add_text}）"
    reason_text = f"{reason_label}" + (f"：{detail}" if detail else "")
    user.muted_until = until
    user.mute_reason = reason_text[:120]
    until_local = until.replace(tzinfo=UTC).astimezone(EAST_ASIA)
    until_text = f"{until_local.year}年{until_local.month}月{until_local.day}日 {until_local.strftime('%H:%M')}"
    content = (
        f"{action_text}。"
        f"原因：{reason_text}。"
        f"{until_text}解除。"
        f"禁言期间无法发送私信。"
    )
    upsert_mute_notification(
        db,
        user_id=user.id,
        content=content,
        related_id=admin.id,
    )
    db.commit()
    return MessageOk(
        detail=(
            f"已续时，预计 {until_text} 解除（已通知用户）"
            if already
            else f"已禁言，预计 {until_text} 解除（已通知用户）"
        )
    )


@router.post("/users/{user_id}/unmute", response_model=MessageOk)
def unmute_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not mute_active(user):
        user.muted_until = None
        user.mute_reason = ""
        db.commit()
        return MessageOk(detail="该用户当前未被禁言")
    user.muted_until = None
    user.mute_reason = ""
    push_unmute_notification(db, user_id=user.id, related_id=admin.id)
    db.commit()
    return MessageOk(detail="已解除禁言（已通知用户）")


@router.delete("/users/{user_id}", response_model=MessageOk)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    """软删除用户：不删聊天/帖子等关联数据。

    - 改写邮箱释放占用，便于同一邮箱重新注册成「新账号」
    - is_active=False + 抬升 token_version，旧登录立刻失效
    - 登录按原邮箱查不到行，与「邮箱或密码错误」表现一致
    - 脱敏昵称/头像等，历史会话里只看到已删除壳，看不到原资料
    """
    _ = admin
    from secrets import token_urlsafe

    from app.auth import hash_password
    from app.bot import is_bot_user

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能删除站长账号")
    if is_bot_user(user):
        raise HTTPException(status_code=400, detail="不能删除 Bot 账号")
    if not user.is_active and (user.email or "").startswith("deleted+"):
        return MessageOk(detail="用户已删除")

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # 备份原邮箱/昵称，便于站长恢复
    if user.email and not (user.email or "").startswith("deleted+"):
        user.previous_email = user.email
    nick = (user.nickname or user.name or "").strip()
    if nick and nick != "已删除用户":
        user.previous_nickname = nick[:30]
    # 释放真实邮箱；聊天 sender_id 仍指向本行，消息原文保留
    user.email = f"deleted+{user.id}.{stamp}@invalid.local"
    user.is_active = False
    user.allow_message_requests = False
    user.nickname = "已删除用户"
    user.name = "已删除用户"
    user.avatar_url = None
    user.bio = ""
    user.show_email = False
    user.muted_until = None
    user.mute_reason = ""
    user.password_hash = hash_password(token_urlsafe(48))
    user.token_version = (user.token_version or 1) + 1
    db.query(InviteCode).filter(InviteCode.created_by_id == user.id).update(
        {"is_active": False},
        synchronize_session=False,
    )
    clear_mute_notifications(db, user_id=user.id)
    db.commit()
    return MessageOk(detail="用户已删除（资料已脱敏，聊天等记录仍保留；原邮箱可重新注册）")


@router.post("/users/{user_id}/restore", response_model=MessageOk)
def restore_user(
    user_id: int,
    payload: RestoreUserIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    """恢复软删除用户：写回邮箱、昵称，设置新密码，重新允许登录。"""
    _ = admin
    from app.auth import hash_password
    from app.bot import is_bot_user

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="站长账号无需恢复")
    if is_bot_user(user):
        raise HTTPException(status_code=400, detail="不能操作 Bot 账号")
    if user.is_active:
        return MessageOk(detail="用户已是正常状态")

    email = (payload.email or user.previous_email or "").strip().lower()
    if not email or email.startswith("deleted+") or "@invalid.local" in email:
        raise HTTPException(status_code=400, detail="请填写要恢复使用的邮箱")
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    taken = (
        db.query(User)
        .filter(User.email == email, User.id != user.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该邮箱已被其他账号占用，请换一个邮箱")

    nick = (payload.nickname or user.previous_nickname or "").strip()
    if not nick:
        nick = email.split("@", 1)[0][:30] or f"user{user.id}"
    nick = nick[:30]

    user.email = email
    user.nickname = nick
    user.name = nick
    user.is_active = True
    user.allow_message_requests = True
    user.password_hash = hash_password(payload.password)
    user.token_version = (user.token_version or 1) + 1
    user.previous_email = None
    user.previous_nickname = None
    db.commit()
    return MessageOk(detail=f"已恢复账号「{nick}」，可用新密码登录")


@router.get("/users/{user_id}/threads", response_model=list[AdminThreadOut])
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminThreadOut]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    threads = (
        db.query(ChatThread)
        .filter((ChatThread.user_a_id == user_id) | (ChatThread.user_b_id == user_id))
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    out: list[AdminThreadOut] = []
    for th in threads:
        peer_id = th.user_b_id if th.user_a_id == user_id else th.user_a_id
        peer = db.get(User, peer_id)
        msgs = db.query(ChatMessage).filter(ChatMessage.thread_id == th.id).all()
        hidden = sum(1 for m in msgs if m.deleted_at is not None or m.recalled_at is not None)
        out.append(
            AdminThreadOut(
                thread_id=th.id,
                peer_id=peer_id,
                peer_nickname=display_name(peer) if peer else f"#{peer_id}",
                peer_active=bool(peer and peer.is_active),
                message_count=len(msgs),
                hidden_count=hidden,
                status=th.status,
            )
        )
    return out


@router.post("/chat/restore-messages", response_model=RestoreChatOut)
def restore_chat_messages(
    payload: RestoreChatIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RestoreChatOut:
    """恢复两人会话中全部被清空/撤回的消息，重新显示在聊天界面。"""
    _ = admin
    if payload.user_a_id == payload.user_b_id:
        raise HTTPException(status_code=400, detail="请选择两个不同的用户")
    a = db.get(User, payload.user_a_id)
    b = db.get(User, payload.user_b_id)
    if not a or not b:
        raise HTTPException(status_code=404, detail="用户不存在")

    lo, hi = sorted((payload.user_a_id, payload.user_b_id))
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.user_a_id == lo, ChatThread.user_b_id == hi)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="这两人之间没有聊天记录")

    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.thread_id == thread.id,
            or_(ChatMessage.deleted_at.isnot(None), ChatMessage.recalled_at.isnot(None)),
        )
        .all()
    )
    for m in rows:
        m.deleted_at = None
        m.recalled_at = None
    thread.status = ThreadStatus.active
    thread.updated_at = datetime.utcnow()
    db.commit()
    return RestoreChatOut(
        detail=f"已恢复 {len(rows)} 条消息（{display_name(a)} ↔ {display_name(b)}）",
        restored=len(rows),
        thread_id=thread.id,
    )


@router.post("/notifications", response_model=MessageOk)
def send_admin_notification(
    payload: AdminNotifyIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    title = payload.title.strip()
    content = (payload.content or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="请填写通知标题")

    if payload.user_id is not None:
        user = db.get(User, payload.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=404, detail="用户不存在或已停用")
        push_notification(
            db,
            user_id=user.id,
            type=NotificationType.admin_notice,
            title=title,
            content=content,
            related_id=admin.id,
        )
        db.commit()
        return MessageOk(detail=f"已向「{display_name(user)}」发送通知")

    targets = (
        db.query(User)
        .filter(User.is_active.is_(True))
        .order_by(User.id.asc())
        .all()
    )
    if not targets:
        raise HTTPException(status_code=400, detail="没有可发送的活跃用户")
    for user in targets:
        push_notification(
            db,
            user_id=user.id,
            type=NotificationType.admin_notice,
            title=title,
            content=content,
            related_id=admin.id,
        )
    db.commit()
    return MessageOk(detail=f"已群发通知给 {len(targets)} 人")


@router.get("/site", response_model=SiteSettingsOut)
def get_site_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> SiteSettingsOut:
    leads = get_home_leads(db, persist_upgrade=True)
    db.commit()
    return SiteSettingsOut(home_lead=leads.get("zh-CN", ""), home_leads=leads)


@router.put("/site", response_model=SiteSettingsOut)
def update_site_settings(
    payload: SiteSettingsIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> SiteSettingsOut:
    if payload.home_leads is not None:
        leads = set_home_leads(db, payload.home_leads)
    else:
        # 兼容旧前端只传 home_lead：更新简体，其它语言若空则补默认
        current = get_home_leads(db)
        zh = (payload.home_lead or "").strip() or DEFAULT_HOME_LEAD
        current["zh-CN"] = zh[:800]
        for loc, text in DEFAULT_HOME_LEADS.items():
            if loc != "zh-CN" and not (current.get(loc) or "").strip():
                current[loc] = text
        leads = set_home_leads(db, current)
    db.commit()
    return SiteSettingsOut(home_lead=leads.get("zh-CN", ""), home_leads=leads)


# ---------- Zeej Bot 站务管理 ----------


@router.get("/bot")
def get_bot_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from app.bot import ensure_bot_user
    from app.bot_prompt import (
        BOT_BIO_KEY,
        BOT_NAME_KEY,
        build_full_system_prompt,
        ensure_bot_prompt,
        get_bot_docs,
    )
    from app.routers.site import get_setting

    bot = ensure_bot_user(db)
    prompt = ensure_bot_prompt(db)
    db.commit()
    return {
        "id": bot.id,
        "nickname": bot.nickname or bot.name,
        "bio": bot.bio or "",
        "avatar_url": bot.avatar_url,
        "system_prompt": prompt,
        "full_prompt_preview": build_full_system_prompt(db)[:4000],
        "docs": get_bot_docs(db),
        "stored_name": get_setting(db, BOT_NAME_KEY, ""),
        "stored_bio": get_setting(db, BOT_BIO_KEY, ""),
    }


@router.put("/bot/profile", response_model=MessageOk)
def update_bot_profile(
    payload: BotProfileIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageOk:
    from app.bot import ensure_bot_user
    from app.bot_prompt import BOT_BIO_KEY, BOT_NAME_KEY

    bot = ensure_bot_user(db)
    if payload.nickname is not None:
        import re as _re

        from app import moderation as mod

        raw = (payload.nickname or "").strip()[:30]
        if not raw:
            raise HTTPException(status_code=400, detail="名称不能为空")
        for w in mod._EN_SWEARS:
            if _re.search(rf"(?<![a-z0-9]){_re.escape(w)}(?![a-z0-9])", raw.lower()):
                raise HTTPException(status_code=400, detail="名称包含不当用语")
        for w in mod._CN_SWEARS:
            if w in raw:
                raise HTTPException(status_code=400, detail="名称包含不当用语")
        bot.nickname = raw
        bot.name = raw
        set_setting(db, BOT_NAME_KEY, raw)
    if payload.bio is not None:
        bio = (payload.bio or "").strip()[:500]
        bot.bio = bio
        set_setting(db, BOT_BIO_KEY, bio)
    db.commit()
    return MessageOk(detail="Bot 资料已更新")


@router.post("/bot/avatar", response_model=MessageOk)
async def upload_bot_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageOk:
    from app.avatar_store import AVATAR_DIR, ALLOWED, compress_avatar_bytes, ensure_dirs
    from app.bot import ensure_bot_user

    bot = ensure_bot_user(db)
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED:
        raise HTTPException(status_code=400, detail="请上传图片文件（JPG / PNG / WebP）")
    raw = await file.read()
    if not raw or len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片无效或过大")
    try:
        compressed = compress_avatar_bytes(raw, ctype)
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析图片") from None
    ensure_dirs()
    for old in AVATAR_DIR.glob(f"u{bot.id}*"):
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass
    name = f"u{bot.id}.jpg"
    path = AVATAR_DIR / name
    path.write_bytes(compressed)
    bot.avatar_url = f"/uploads/avatars/{name}?v={path.stat().st_mtime_ns}"
    db.commit()
    return MessageOk(detail="Bot 头像已更新")


@router.put("/bot/prompt", response_model=MessageOk)
def update_bot_prompt(
    payload: BotPromptIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageOk:
    from app.bot_prompt import BOT_PROMPT_KEY, ensure_bot_prompt

    ensure_bot_prompt(db)
    text = (payload.system_prompt or "").strip()
    mode = (payload.mode or "replace").strip().lower()
    if mode == "append":
        cur = ensure_bot_prompt(db)
        text = (cur.rstrip() + "\n\n" + text).strip() if text else cur
    if not text:
        raise HTTPException(status_code=400, detail="提示词不能为空")
    set_setting(db, BOT_PROMPT_KEY, text[:100000])
    db.commit()
    return MessageOk(detail="底层提示词已更新")


@router.post("/bot/docs", response_model=MessageOk)
def add_bot_doc(
    payload: BotDocIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageOk:
    from app.bot_prompt import get_bot_docs, set_bot_docs

    docs = get_bot_docs(db)
    if len(docs) >= 20:
        raise HTTPException(status_code=400, detail="补充文档最多 20 个，请先删除旧文档")
    name = (payload.name or "notes.txt").strip()[:120] or "notes.txt"
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="文档内容不能为空")
    docs.append({"name": name, "content": content[:50000]})
    set_bot_docs(db, docs)
    db.commit()
    return MessageOk(detail=f"已添加文档「{name}」")


@router.delete("/bot/docs/{index}", response_model=MessageOk)
def delete_bot_doc(
    index: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageOk:
    from app.bot_prompt import get_bot_docs, set_bot_docs

    docs = get_bot_docs(db)
    if index < 0 or index >= len(docs):
        raise HTTPException(status_code=404, detail="文档不存在")
    removed = docs.pop(index)
    set_bot_docs(db, docs)
    db.commit()
    return MessageOk(detail=f"已删除「{removed.get('name', 'doc')}」")


@router.post("/users/{user_id}/bot-permission", response_model=MessageOk)
def set_user_bot_permission(
    user_id: int,
    payload: BotPermissionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOk:
    from app.bot import is_bot_user
    from app.bot_quota import apply_bot_preset, notify_bot_quota

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="用户不存在")
    if is_bot_user(user) or user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能为 Bot / 站长设置该权限")
    preset = apply_bot_preset(user, payload.preset, reset_usage=True)
    notify_bot_quota(db, user, reason="admin")
    db.commit()
    labels = {"none": "无权限", "normal": "正常（10轮×100条）", "limited": "受限（3轮×100条）"}
    return MessageOk(detail=f"已将「{display_name(user)}」Bot 权限设为：{labels.get(preset, preset)}")
