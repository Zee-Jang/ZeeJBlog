from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import display_name, get_current_user
from app.bot import (
    clear_thread_messages,
    generate_bot_reply,
    get_or_create_bot_thread,
    is_bot_user,
)
from app.bot_quota import (
    assert_can_clear_bot,
    assert_can_send_to_bot,
    refund_bot_message,
    try_consume_bot_message,
    try_consume_bot_round_on_clear,
)
from app.database import get_db
from app.models import (
    ChatMessage,
    ChatThread,
    MessageStatus,
    ThreadStatus,
    User,
)
from app.schemas import MessageCreate, MessageOk, MessageOut, MessageReplyOut, ThreadOut
from app.services import is_admin, is_blocked, mute_active, pair_ids

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _peer_id(thread: ChatThread, me_id: int) -> int:
    return thread.user_b_id if thread.user_a_id == me_id else thread.user_a_id


def _assert_member(thread: ChatThread | None, me: User) -> ChatThread:
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")
    if me.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    if thread.status != ThreadStatus.active:
        raise HTTPException(status_code=400, detail="会话已关闭")
    return thread


def _reply_out(msg: ChatMessage) -> MessageReplyOut | None:
    if not msg.reply_to_id:
        return None
    ref = msg.reply_to
    recalled = bool(ref and ref.recalled_at is not None)
    # 原消息被清空时仍用发送时快照
    if ref is None or ref.deleted_at is not None:
        content = (msg.reply_content_snapshot or "").strip()
        name = (msg.reply_sender_name or "").strip() or "用户"
        return MessageReplyOut(
            id=msg.reply_to_id,
            sender_name=name,
            content="" if not content else content,
            recalled=False,
        )
    if recalled:
        return MessageReplyOut(
            id=ref.id,
            sender_name=display_name(ref.sender) if ref.sender else (msg.reply_sender_name or ""),
            content="",
            recalled=True,
        )
    content = (ref.content or msg.reply_content_snapshot or "").strip()
    name = (
        display_name(ref.sender)
        if ref.sender
        else (msg.reply_sender_name or "")
    )
    return MessageReplyOut(id=ref.id, sender_name=name, content=content, recalled=False)


def _msg_out(msg: ChatMessage, me: User) -> MessageOut:
    recalled = msg.recalled_at is not None
    return MessageOut(
        id=msg.id,
        thread_id=msg.thread_id,
        sender_id=msg.sender_id,
        sender_name=display_name(msg.sender) if msg.sender else "",
        sender_avatar_url=msg.sender.avatar_url if msg.sender else None,
        content="" if recalled or msg.deleted_at else msg.content,
        status=msg.status,
        created_at=msg.created_at,
        read_at=msg.read_at,
        is_mine=msg.sender_id == me.id,
        recalled=recalled,
        recalled_at=msg.recalled_at,
        reply_to=_reply_out(msg),
    )


def _thread_out(db: Session, thread: ChatThread, me: User) -> ThreadOut:
    peer_id = _peer_id(thread, me.id)
    peer = db.get(User, peer_id)
    messages = list(thread.messages or [])
    unread = sum(
        1
        for m in messages
        if m.sender_id != me.id
        and m.status == MessageStatus.sent
        and m.deleted_at is None
        and m.recalled_at is None
    )
    last = next(
        (
            m.content
            for m in reversed(messages)
            if not m.deleted_at and not m.recalled_at
        ),
        None,
    )
    return ThreadOut(
        id=thread.id,
        peer_id=peer_id,
        peer_name=display_name(peer) if peer else "用户",
        status=thread.status,
        updated_at=thread.updated_at,
        unread_count=unread,
        last_message=last,
        peer_active=bool(peer and peer.is_active),
        peer_is_bot=is_bot_user(peer),
        peer_is_admin=bool(peer and is_admin(peer)),
    )


@router.get("/threads", response_model=list[ThreadOut])
def list_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ThreadOut]:
    threads = (
        db.query(ChatThread)
        .options(joinedload(ChatThread.messages))
        .filter(
            (ChatThread.user_a_id == current_user.id) | (ChatThread.user_b_id == current_user.id)
        )
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    out: list[ThreadOut] = []
    for t in threads:
        item = _thread_out(db, t, current_user)
        if item.peer_active:
            out.append(item)
    return out


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
def list_messages(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageOut]:
    thread = _assert_member(db.get(ChatThread, thread_id), current_user)
    peer_id = _peer_id(thread, current_user.id)
    if is_blocked(db, current_user.id, peer_id):
        raise HTTPException(status_code=403, detail="双方存在拉黑关系")

    now = datetime.utcnow()
    for msg in (
        db.query(ChatMessage)
        .filter(
            ChatMessage.thread_id == thread.id,
            ChatMessage.sender_id != current_user.id,
            ChatMessage.status == MessageStatus.sent,
            ChatMessage.deleted_at.is_(None),
            ChatMessage.recalled_at.is_(None),
        )
        .all()
    ):
        msg.status = MessageStatus.read
        msg.read_at = now
    db.commit()

    # 含已撤回：前端显示「xxx撤回了一条消息」；清空会话的 deleted_at 仍不返回
    messages = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(ChatMessage.thread_id == thread.id, ChatMessage.deleted_at.is_(None))
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [_msg_out(m, current_user) for m in messages]


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    thread_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOut:
    if mute_active(current_user):
        raise HTTPException(status_code=403, detail="你已被禁言，暂时无法发送私信")
    thread = _assert_member(db.get(ChatThread, thread_id), current_user)
    peer_id = _peer_id(thread, current_user.id)
    if is_blocked(db, current_user.id, peer_id):
        raise HTTPException(status_code=403, detail="无法发送消息")
    peer = db.get(User, peer_id)
    if not peer or not peer.is_active:
        raise HTTPException(status_code=400, detail="对方账号不可用")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息不能为空")

    if is_bot_user(peer) and not is_bot_user(current_user):
        assert_can_send_to_bot(current_user)

    reply_to_id = None
    reply_sender_name = None
    reply_content_snapshot = None
    if payload.reply_to_id is not None:
        ref = (
            db.query(ChatMessage)
            .options(joinedload(ChatMessage.sender))
            .filter(ChatMessage.id == payload.reply_to_id)
            .first()
        )
        if (
            not ref
            or ref.thread_id != thread.id
            or ref.deleted_at is not None
        ):
            raise HTTPException(status_code=400, detail="引用的消息不存在")
        reply_to_id = ref.id
        reply_sender_name = display_name(ref.sender) if ref.sender else "用户"
        if ref.recalled_at is None:
            reply_content_snapshot = (ref.content or "").strip()[:500]
        else:
            reply_content_snapshot = ""

    msg = ChatMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        content=content,
        status=MessageStatus.sent,
        reply_to_id=reply_to_id,
        reply_sender_name=reply_sender_name,
        reply_content_snapshot=reply_content_snapshot,
    )
    thread.updated_at = datetime.utcnow()
    db.add(msg)
    talking_bot = is_bot_user(peer) and not is_bot_user(current_user)
    if talking_bot:
        try_consume_bot_message(db, current_user)
    db.commit()

    if talking_bot:
        bot_msg = None
        try:
            bot_msg = await generate_bot_reply(db, thread=thread, bot=peer, human=current_user)
        except Exception:
            bot_msg = None
        if bot_msg is None:
            # 连友好回复都写不进库：退回额度，避免白扣
            try:
                refund_bot_message(db, current_user)
                db.commit()
            except Exception:
                db.rollback()

    msg = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(ChatMessage.id == msg.id)
        .one()
    )
    return _msg_out(msg, current_user)


@router.post("/messages/{message_id}/recall", response_model=MessageOut)
def recall_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOut:
    """撤回自己发送的消息：软标记 recalled_at，正文仍保留在库中。"""
    msg = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.sender), joinedload(ChatMessage.thread))
        .filter(ChatMessage.id == message_id)
        .first()
    )
    if not msg or msg.deleted_at is not None:
        raise HTTPException(status_code=404, detail="消息不存在")
    thread = msg.thread
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="无权操作该消息")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能撤回自己发送的消息")
    if msg.recalled_at is not None:
        return _msg_out(msg, current_user)

    now = datetime.utcnow()
    msg.recalled_at = now
    thread.updated_at = now
    db.commit()
    msg = (
        db.query(ChatMessage)
        .options(
            joinedload(ChatMessage.sender),
            joinedload(ChatMessage.reply_to).joinedload(ChatMessage.sender),
        )
        .filter(ChatMessage.id == msg.id)
        .one()
    )
    return _msg_out(msg, current_user)


@router.post("/open-bot", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def open_bot_thread(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThreadOut:
    """任意登录用户可直接开启与站内机器人的会话。"""
    snap_limit = int(getattr(current_user, "bot_rounds_limit", 0) or 0)
    if snap_limit <= 0:
        raise HTTPException(status_code=403, detail="你暂无 Zeej Bot 使用权限")
    try:
        thread = get_or_create_bot_thread(db, current_user)
    except ValueError:
        raise HTTPException(status_code=400, detail="无法与机器人开启会话") from None
    db.commit()
    thread = (
        db.query(ChatThread)
        .options(joinedload(ChatThread.messages))
        .filter(ChatThread.id == thread.id)
        .one()
    )
    return _thread_out(db, thread, current_user)


@router.post("/threads/{thread_id}/clear", response_model=MessageOk)
def clear_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    """清空会话记录（软删除）。与 Bot 会话时会消耗 1 轮额度。"""
    thread = db.get(ChatThread, thread_id)
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    peer = db.get(User, _peer_id(thread, current_user.id))
    if is_bot_user(peer):
        will_consume = int(getattr(current_user, "bot_msgs_this_round", 0) or 0) > 0
        assert_can_clear_bot(current_user, consume_round=will_consume)
        n = clear_thread_messages(db, thread)
        consumed = try_consume_bot_round_on_clear(db, current_user)
        db.commit()
        if consumed:
            return MessageOk(detail=f"已清除 {n} 条消息（消耗 1 轮额度）")
        return MessageOk(detail=f"已清除 {n} 条消息")
    n = clear_thread_messages(db, thread)
    db.commit()
    return MessageOk(detail=f"已清除 {n} 条消息")


@router.post("/open/{user_id}", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def open_thread(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThreadOut:
    """站长可直接开启与任意用户的会话；与机器人会话对所有人开放。"""
    peer = db.get(User, user_id)
    if not peer or not peer.is_active:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能与自己开启会话")

    if is_bot_user(peer):
        snap_limit = int(getattr(current_user, "bot_rounds_limit", 0) or 0)
        if snap_limit <= 0:
            raise HTTPException(status_code=403, detail="你暂无 Zeej Bot 使用权限")
        thread = get_or_create_bot_thread(db, current_user)
        db.commit()
        thread = (
            db.query(ChatThread)
            .options(joinedload(ChatThread.messages))
            .filter(ChatThread.id == thread.id)
            .one()
        )
        return _thread_out(db, thread, current_user)

    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅站长可直接开启会话")
    if is_blocked(db, current_user.id, peer.id):
        raise HTTPException(status_code=403, detail="双方存在拉黑关系")

    a, b = pair_ids(current_user.id, peer.id)
    thread = (
        db.query(ChatThread)
        .options(joinedload(ChatThread.messages))
        .filter(ChatThread.user_a_id == a, ChatThread.user_b_id == b)
        .first()
    )
    if not thread:
        thread = ChatThread(user_a_id=a, user_b_id=b, status=ThreadStatus.active)
        db.add(thread)
        db.commit()
        thread = (
            db.query(ChatThread)
            .options(joinedload(ChatThread.messages))
            .filter(ChatThread.id == thread.id)
            .one()
        )
    else:
        thread.status = ThreadStatus.active
        thread.updated_at = datetime.utcnow()
        db.commit()
        thread = (
            db.query(ChatThread)
            .options(joinedload(ChatThread.messages))
            .filter(ChatThread.id == thread.id)
            .one()
        )

    return _thread_out(db, thread, current_user)


@router.post("/threads/{thread_id}/read", response_model=MessageOk)
def mark_read(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    thread = _assert_member(db.get(ChatThread, thread_id), current_user)
    now = datetime.utcnow()
    for msg in (
        db.query(ChatMessage)
        .filter(
            ChatMessage.thread_id == thread.id,
            ChatMessage.sender_id != current_user.id,
            ChatMessage.status == MessageStatus.sent,
            ChatMessage.deleted_at.is_(None),
            ChatMessage.recalled_at.is_(None),
        )
        .all()
    ):
        msg.status = MessageStatus.read
        msg.read_at = now
    db.commit()
    return MessageOk(detail="已读")


@router.post("/threads/{thread_id}/close", response_model=MessageOk)
def close_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    thread = db.get(ChatThread, thread_id)
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    thread.status = ThreadStatus.closed
    db.commit()
    return MessageOk(detail="会话已关闭")
