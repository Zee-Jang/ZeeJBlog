from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Notification, NotificationType, User, UserBlock
from app.schemas import MessageOk, NotificationOut, ReportCreate
from app.models import Report

router = APIRouter(tags=["social"])

# 交流（私信 / 申请）只走「交流」角标，不进通知中心
_EXCLUDED_NOTIF_TYPES = (
    NotificationType.new_message,
    NotificationType.chat_request,
    NotificationType.chat_accepted,
    NotificationType.chat_rejected,
)


@router.get("/api/notifications", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationOut]:
    rows = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.type.notin_(_EXCLUDED_NOTIF_TYPES),
        )
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        NotificationOut(
            id=n.id,
            type=n.type,
            title=n.title,
            content=n.content,
            related_id=n.related_id,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in rows
    ]


@router.post("/api/notifications/{notification_id}/read", response_model=MessageOk)
def read_one(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    row = db.get(Notification, notification_id)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="通知不存在")
    row.is_read = True
    db.commit()
    return MessageOk(detail="已读")


@router.post("/api/notifications/read-all", response_model=MessageOk)
def read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return MessageOk(detail="全部已读")


@router.get("/api/blocks", response_model=list[int])
def list_blocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[int]:
    rows = db.query(UserBlock).filter(UserBlock.blocker_id == current_user.id).all()
    return [r.blocked_id for r in rows]


@router.post("/api/blocks/{user_id}", response_model=MessageOk)
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能拉黑自己")
    exists = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == current_user.id, UserBlock.blocked_id == user_id)
        .first()
    )
    if not exists:
        db.add(UserBlock(blocker_id=current_user.id, blocked_id=user_id))
        db.commit()
    return MessageOk(detail="已拉黑")


@router.delete("/api/blocks/{user_id}", response_model=MessageOk)
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    row = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == current_user.id, UserBlock.blocked_id == user_id)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
    return MessageOk(detail="已取消拉黑")


@router.post("/api/reports", response_model=MessageOk)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    if not payload.target_user_id and not payload.target_message_id:
        raise HTTPException(status_code=400, detail="请指定举报对象")
    db.add(
        Report(
            reporter_id=current_user.id,
            target_user_id=payload.target_user_id,
            target_message_id=payload.target_message_id,
            reason=payload.reason.strip(),
        )
    )
    db.commit()
    return MessageOk(detail="举报已提交")
