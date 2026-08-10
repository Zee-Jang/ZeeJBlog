"""Zeej Bot 使用配额：轮次 + 每轮消息数。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import NotificationType, User
from app.services import push_notification

# preset -> (rounds_limit, msgs_per_round)
BOT_PRESETS: dict[str, tuple[int, int]] = {
    "none": (0, 100),
    "normal": (10, 100),
    "limited": (3, 100),
}

DEFAULT_PRESET = "normal"


def apply_bot_preset(user: User, preset: str, *, reset_usage: bool = True) -> str:
    key = (preset or "").strip().lower()
    if key not in BOT_PRESETS:
        raise HTTPException(status_code=400, detail="未知的 Bot 权限档位")
    rounds, msgs = BOT_PRESETS[key]
    user.bot_rounds_limit = rounds
    user.bot_msgs_per_round = msgs
    if reset_usage:
        user.bot_rounds_used = 0
        user.bot_msgs_this_round = 0
    return key


def apply_default_bot_quota(user: User) -> None:
    apply_bot_preset(user, DEFAULT_PRESET, reset_usage=True)


def bot_quota_snapshot(user: User) -> dict:
    limit = int(getattr(user, "bot_rounds_limit", 10) or 0)
    used = int(getattr(user, "bot_rounds_used", 0) or 0)
    per = int(getattr(user, "bot_msgs_per_round", 100) or 100)
    cur = int(getattr(user, "bot_msgs_this_round", 0) or 0)
    remaining_rounds = max(0, limit - used)
    enabled = limit > 0 and remaining_rounds > 0
    remaining_msgs = max(0, per - cur) if enabled else 0
    if limit <= 0:
        preset = "none"
    elif limit <= 3:
        preset = "limited"
    else:
        preset = "normal"
    return {
        "preset": preset,
        "enabled": enabled,
        "rounds_limit": limit,
        "rounds_used": used,
        "rounds_remaining": remaining_rounds,
        "msgs_per_round": per,
        "msgs_this_round": cur,
        "msgs_remaining": remaining_msgs,
    }


def assert_can_send_to_bot(user: User) -> None:
    snap = bot_quota_snapshot(user)
    if snap["rounds_limit"] <= 0:
        raise HTTPException(status_code=403, detail="你暂无 Zeej Bot 使用权限")
    if snap["rounds_remaining"] <= 0:
        raise HTTPException(status_code=403, detail="Bot 对话轮次已用完，请联系站长调整权限")
    if snap["msgs_remaining"] <= 0:
        # 仅剩本轮时再清会把额度清到 0，无法继续聊——勿引导用户去清除
        if snap["rounds_remaining"] <= 1:
            raise HTTPException(
                status_code=403,
                detail="本轮消息已用完，且已是最后一轮额度，请联系站长调整权限",
            )
        raise HTTPException(
            status_code=403,
            detail="本轮消息条数已用完，可「清除本轮」开启新一轮（会消耗一轮额度）",
        )


def try_consume_bot_message(db: Session, user: User) -> None:
    """原子扣减本轮消息额度；失败抛 403。"""
    assert_can_send_to_bot(user)
    result = db.execute(
        text(
            """
            UPDATE users
            SET bot_msgs_this_round = bot_msgs_this_round + 1
            WHERE id = :id
              AND bot_rounds_limit > 0
              AND bot_rounds_used < bot_rounds_limit
              AND bot_msgs_this_round < bot_msgs_per_round
            """
        ),
        {"id": user.id},
    )
    if result.rowcount != 1:
        db.refresh(user)
        assert_can_send_to_bot(user)
        raise HTTPException(status_code=403, detail="Bot 额度不足，请稍后再试")
    db.refresh(user)


def refund_bot_message(db: Session, user: User) -> None:
    """回复彻底失败时退回一条消息额度。"""
    db.execute(
        text(
            """
            UPDATE users
            SET bot_msgs_this_round = CASE
              WHEN bot_msgs_this_round > 0 THEN bot_msgs_this_round - 1
              ELSE 0
            END
            WHERE id = :id
            """
        ),
        {"id": user.id},
    )
    db.refresh(user)


def note_bot_message_sent(user: User) -> None:
    """兼容旧调用；新路径请用 try_consume_bot_message。"""
    user.bot_msgs_this_round = int(user.bot_msgs_this_round or 0) + 1


def assert_can_clear_bot(user: User, *, consume_round: bool) -> None:
    snap = bot_quota_snapshot(user)
    if snap["rounds_limit"] <= 0:
        raise HTTPException(status_code=403, detail="你暂无 Zeej Bot 使用权限")
    if consume_round and snap["rounds_remaining"] <= 0:
        raise HTTPException(status_code=403, detail="Bot 轮次已用完，无法再清除开启新一轮")


def try_consume_bot_round_on_clear(db: Session, user: User) -> bool:
    """若本轮有消息计数则原子消耗 1 轮；返回是否消耗了轮次。"""
    db.refresh(user)
    if int(user.bot_msgs_this_round or 0) <= 0:
        return False
    assert_can_clear_bot(user, consume_round=True)
    result = db.execute(
        text(
            """
            UPDATE users
            SET bot_rounds_used = bot_rounds_used + 1,
                bot_msgs_this_round = 0
            WHERE id = :id
              AND bot_rounds_limit > 0
              AND bot_rounds_used < bot_rounds_limit
              AND bot_msgs_this_round > 0
            """
        ),
        {"id": user.id},
    )
    if result.rowcount != 1:
        db.refresh(user)
        assert_can_clear_bot(user, consume_round=True)
        raise HTTPException(status_code=403, detail="无法消耗轮次，请刷新后重试")
    db.refresh(user)
    return True


def consume_bot_round_on_clear(user: User) -> None:
    """兼容旧调用。"""
    assert_can_clear_bot(user, consume_round=True)
    user.bot_rounds_used = int(user.bot_rounds_used or 0) + 1
    user.bot_msgs_this_round = 0


def notify_bot_quota(db: Session, user: User, *, reason: str = "welcome") -> None:
    snap = bot_quota_snapshot(user)
    if snap["rounds_limit"] <= 0:
        title = "Zeej Bot 权限更新 🤖"
        content = (
            "站长已调整你的 Bot 权限：当前无法使用 Zeej Bot。\n"
            "如有需要，可再联系站长开通～ 🌿"
        )
    else:
        title = "你的 Zeej Bot 额度 ✨"
        content = (
            f"你好呀～ 站长为你设置了 Bot 额度：\n"
            f"🔁 共 {snap['rounds_limit']} 轮对话（清除本轮会消耗 1 轮）\n"
            f"💬 每轮最多 {snap['msgs_per_round']} 条消息\n"
            f"当前剩余 {snap['rounds_remaining']} 轮，本轮还可发 {snap['msgs_remaining']} 条。\n"
            f"去主页点「和 Bot 聊聊」就可以开始啦 😊"
        )
        if reason == "admin":
            content = (
                f"站长刚刚更新了你的 Zeej Bot 权限 🎁\n"
                f"🔁 {snap['rounds_limit']} 轮 · 每轮 {snap['msgs_per_round']} 条\n"
                f"已为你重新计额，当前可用 {snap['rounds_remaining']} 轮。慢慢聊，别着急～ 🌸"
            )
    push_notification(
        db,
        user_id=user.id,
        type=NotificationType.admin_notice,
        title=title,
        content=content,
    )


def notify_welcome(db: Session, user: User) -> None:
    name = (user.nickname or user.name or "朋友").strip()
    push_notification(
        db,
        user_id=user.id,
        type=NotificationType.admin_notice,
        title="欢迎来到 Zeej 🌿",
        content=(
            f"嗨，{name}！欢迎加入邀请制小站 Zeej～ 🎉\n"
            f"这里有碎碎念、项目橱窗，还有和朋友的交流。\n"
            f"慢慢逛，有问题可以找站内 Zeej Bot 聊聊 🤖💛"
        ),
    )
