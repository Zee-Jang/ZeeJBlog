from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import display_name, get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import (
    ChatRequest,
    ChatRequestStatus,
    ChatThread,
    Notification,
    NotificationType,
    ThreadStatus,
    User,
)
from app.schemas import ChatRequestCreate, ChatRequestOut, MessageOk
from app.services import is_blocked, mute_active, pair_ids

router = APIRouter(prefix="/api/chat-requests", tags=["chat-requests"])
settings = get_settings()


def _out(row: ChatRequest) -> ChatRequestOut:
    return ChatRequestOut(
        id=row.id,
        sender_id=row.sender_id,
        sender_name=display_name(row.sender) if row.sender else "",
        receiver_id=row.receiver_id,
        receiver_name=display_name(row.receiver) if row.receiver else "",
        message=row.message,
        status=row.status,
        created_at=row.created_at,
        responded_at=row.responded_at,
    )


@router.get("/received", response_model=list[ChatRequestOut])
def received(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatRequestOut]:
    rows = (
        db.query(ChatRequest)
        .options(joinedload(ChatRequest.sender), joinedload(ChatRequest.receiver))
        .filter(ChatRequest.receiver_id == current_user.id)
        .order_by(ChatRequest.created_at.desc())
        .all()
    )
    return [_out(r) for r in rows]


@router.get("/sent", response_model=list[ChatRequestOut])
def sent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatRequestOut]:
    rows = (
        db.query(ChatRequest)
        .options(joinedload(ChatRequest.sender), joinedload(ChatRequest.receiver))
        .filter(ChatRequest.sender_id == current_user.id)
        .order_by(ChatRequest.created_at.desc())
        .all()
    )
    return [_out(r) for r in rows]


@router.post("", response_model=ChatRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ChatRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatRequestOut:
    if mute_active(current_user):
        raise HTTPException(status_code=403, detail="你已被禁言，暂时无法发送交流申请")
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能给自己发聊天申请")
    receiver = db.get(User, payload.receiver_id)
    if not receiver or not receiver.is_active:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not receiver.allow_message_requests:
        raise HTTPException(status_code=400, detail="对方暂不接收聊天申请")
    if is_blocked(db, current_user.id, receiver.id):
        raise HTTPException(status_code=403, detail="无法发送申请")

    pending = (
        db.query(ChatRequest)
        .filter(
            ChatRequest.sender_id == current_user.id,
            ChatRequest.receiver_id == receiver.id,
            ChatRequest.status == ChatRequestStatus.pending,
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=400, detail="已有待处理的申请")

    # 已有会话则不必再申请
    a, b = pair_ids(current_user.id, receiver.id)
    exists_thread = (
        db.query(ChatThread)
        .filter(
            ChatThread.user_a_id == a,
            ChatThread.user_b_id == b,
            ChatThread.status == ThreadStatus.active,
        )
        .first()
    )
    if exists_thread:
        raise HTTPException(status_code=400, detail="你们已经可以聊天了")

    rejected = (
        db.query(ChatRequest)
        .filter(
            ChatRequest.sender_id == current_user.id,
            ChatRequest.receiver_id == receiver.id,
            ChatRequest.status == ChatRequestStatus.rejected,
        )
        .order_by(ChatRequest.responded_at.desc())
        .first()
    )
    if rejected and rejected.responded_at:
        cool = rejected.responded_at + timedelta(hours=settings.chat_reject_cooldown_hours)
        if datetime.utcnow() < cool:
            raise HTTPException(status_code=400, detail="对方拒绝后需等待一段时间再申请")

    row = ChatRequest(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        message=(payload.message or "").strip()[:500],
        status=ChatRequestStatus.pending,
    )
    db.add(row)
    db.flush()
    # 申请出现在「交流」列表，不写站内通知
    db.commit()
    row = (
        db.query(ChatRequest)
        .options(joinedload(ChatRequest.sender), joinedload(ChatRequest.receiver))
        .filter(ChatRequest.id == row.id)
        .one()
    )
    return _out(row)


@router.post("/{request_id}/accept", response_model=ChatRequestOut)
def accept(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatRequestOut:
    row = (
        db.query(ChatRequest)
        .options(joinedload(ChatRequest.sender), joinedload(ChatRequest.receiver))
        .filter(ChatRequest.id == request_id)
        .first()
    )
    if not row or row.receiver_id != current_user.id:
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status != ChatRequestStatus.pending:
        raise HTTPException(status_code=400, detail="申请状态不可用")
    sender = row.sender
    if not sender or not sender.is_active:
        raise HTTPException(status_code=400, detail="对方账号已停用，无法同意该申请")
    if is_blocked(db, current_user.id, row.sender_id):
        raise HTTPException(status_code=403, detail="无法同意该申请")

    row.status = ChatRequestStatus.accepted
    row.responded_at = datetime.utcnow()
    a, b = pair_ids(row.sender_id, row.receiver_id)
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.user_a_id == a, ChatThread.user_b_id == b)
        .first()
    )
    if not thread:
        thread = ChatThread(user_a_id=a, user_b_id=b, status=ThreadStatus.active)
        db.add(thread)
    else:
        thread.status = ThreadStatus.active
    db.flush()
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/{request_id}/reject", response_model=ChatRequestOut)
def reject(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatRequestOut:
    row = (
        db.query(ChatRequest)
        .options(joinedload(ChatRequest.sender), joinedload(ChatRequest.receiver))
        .filter(ChatRequest.id == request_id)
        .first()
    )
    if not row or row.receiver_id != current_user.id:
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status != ChatRequestStatus.pending:
        raise HTTPException(status_code=400, detail="申请状态不可用")
    row.status = ChatRequestStatus.rejected
    row.responded_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/{request_id}/cancel", response_model=MessageOk)
def cancel(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    row = db.get(ChatRequest, request_id)
    if not row or row.sender_id != current_user.id:
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status != ChatRequestStatus.pending:
        raise HTTPException(status_code=400, detail="只能取消待处理申请")
    row.status = ChatRequestStatus.cancelled
    row.responded_at = datetime.utcnow()
    db.query(Notification).filter(
        Notification.user_id == row.receiver_id,
        Notification.type == NotificationType.chat_request,
        Notification.related_id == row.id,
    ).delete(synchronize_session=False)
    db.commit()
    return MessageOk(detail="已取消申请")
