from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notification, NotificationType, User, UserBlock, UserRole


def is_blocked(db: Session, a_id: int, b_id: int) -> bool:
    return (
        db.query(UserBlock)
        .filter(
            ((UserBlock.blocker_id == a_id) & (UserBlock.blocked_id == b_id))
            | ((UserBlock.blocker_id == b_id) & (UserBlock.blocked_id == a_id))
        )
        .first()
        is not None
    )


def push_notification(
    db: Session,
    *,
    user_id: int,
    type: NotificationType,
    title: str,
    content: str = "",
    related_id: int | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=type,
            title=title[:120],
            content=(content or "")[:500],
            related_id=related_id,
            created_at=datetime.utcnow(),
        )
    )


MUTE_NOTIF_TITLE = "账户禁言通知"
UNMUTE_NOTIF_TITLE = "禁言已解除"


def _mute_title_rows(db: Session, user_id: int) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == NotificationType.moderation,
            Notification.title == MUTE_NOTIF_TITLE,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )


def upsert_mute_notification(
    db: Session,
    *,
    user_id: int,
    content: str,
    related_id: int | None = None,
) -> None:
    """再次禁言/加时时更新当前禁言通知；不删除历史「已解除」记录。"""
    rows = _mute_title_rows(db, user_id)
    keep = rows[0] if rows else None
    for r in rows[1:]:
        db.delete(r)
    body = (content or "")[:500]
    if keep:
        keep.title = MUTE_NOTIF_TITLE
        keep.content = body
        keep.related_id = related_id
        keep.is_read = False
        keep.created_at = datetime.utcnow()
    else:
        push_notification(
            db,
            user_id=user_id,
            type=NotificationType.moderation,
            title=MUTE_NOTIF_TITLE,
            content=body,
            related_id=related_id,
        )


def push_unmute_notification(
    db: Session,
    *,
    user_id: int,
    related_id: int | None = None,
) -> None:
    """解除禁言：新增一条通知，保留原禁言通知作为记录。"""
    push_notification(
        db,
        user_id=user_id,
        type=NotificationType.moderation,
        title=UNMUTE_NOTIF_TITLE,
        content="站长已解除对你的禁言，现在可以正常发送私信。",
        related_id=related_id,
    )


def clear_mute_notifications(db: Session, *, user_id: int) -> None:
    """删除禁言相关通知（停用账户等场景用）。"""
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.type == NotificationType.moderation,
        Notification.title.in_([MUTE_NOTIF_TITLE, UNMUTE_NOTIF_TITLE]),
    ).delete(synchronize_session=False)


def pair_ids(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def is_admin(user: User) -> bool:
    return user.role == UserRole.admin


def mute_active(user: User, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(user.muted_until and user.muted_until > now)


def account_age_days(user: User, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if not user.created_at:
        return 0
    return max(0, (now - user.created_at).days)


def invite_quota_for(user: User, now: datetime | None = None) -> int:
    """注册未满 10 天：3；满 10 天起：30。管理员不设上限。"""
    if is_admin(user):
        return 10_000
    return 30 if account_age_days(user, now) >= 10 else 3


def to_user_out(user: User):
    from app.bot_quota import bot_quota_snapshot
    from app.schemas import UserOut

    snap = bot_quota_snapshot(user)
    return UserOut(
        id=user.id,
        email=user.email,
        nickname=user.nickname or user.name,
        name=user.name,
        role=user.role,
        avatar_url=user.avatar_url,
        bio=user.bio or "",
        allow_message_requests=user.allow_message_requests,
        show_email=user.show_email,
        show_join_date=user.show_join_date,
        created_at=user.created_at,
        muted_until=user.muted_until,
        mute_reason=user.mute_reason or "",
        is_muted=mute_active(user),
        bot_preset=snap["preset"],
        bot_enabled=snap["enabled"],
        bot_rounds_limit=snap["rounds_limit"],
        bot_rounds_used=snap["rounds_used"],
        bot_rounds_remaining=snap["rounds_remaining"],
        bot_msgs_per_round=snap["msgs_per_round"],
        bot_msgs_this_round=snap["msgs_this_round"],
        bot_msgs_remaining=snap["msgs_remaining"],
    )


def to_public_user(user: User, viewer: User | None = None):
    from app.bot import is_bot_user
    from app.schemas import PublicUserOut

    email = None
    if user.show_email or (viewer and viewer.id == user.id):
        email = user.email
    created = user.created_at if user.show_join_date else None
    return PublicUserOut(
        id=user.id,
        nickname=user.nickname or user.name,
        avatar_url=user.avatar_url,
        bio=user.bio or "",
        allow_message_requests=user.allow_message_requests,
        created_at=created,
        email=email,
        is_muted=mute_active(user),
        is_bot=is_bot_user(user),
        is_admin=user.role == UserRole.admin,
    )
