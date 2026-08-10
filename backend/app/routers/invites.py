import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import InviteCode, User
from app.schemas import UtcDateTime, UtcDateTimeOpt
from app.services import account_age_days, invite_quota_for, is_admin

router = APIRouter(prefix="/api/invites", tags=["invites"])

ALPHABET = string.ascii_uppercase + string.digits


def _quota_used(db: Session, user_id: int) -> int:
    """占用额度的邀请：仍有效且未过期（不含已撤销 / 已过期）。"""
    now = datetime.utcnow()
    return (
        db.query(InviteCode)
        .filter(
            InviteCode.created_by_id == user_id,
            InviteCode.is_active.is_(True),
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at >= now),
        )
        .count()
    )


class InviteCreateIn(BaseModel):
    """管理员批量（仅 admin）。"""
    count: int = Field(default=1, ge=1, le=100)
    max_uses: int = Field(default=1, ge=1, le=1000)
    note: str = Field(default="", max_length=200)
    expires_days: int | None = Field(default=30, ge=1, le=365)


class InviteOneIn(BaseModel):
    note: str = Field(default="", max_length=200)
    expires_days: int | None = Field(default=30, ge=1, le=365)


class InviteOut(BaseModel):
    id: int
    code: str
    max_uses: int
    use_count: int
    note: str
    is_active: bool
    created_at: UtcDateTime
    expires_at: UtcDateTimeOpt
    remaining: int
    invite_url: str = ""
    share_text: str = ""


class InviteBatchOut(BaseModel):
    codes: list[InviteOut]


class InviteQuotaOut(BaseModel):
    used: int
    limit: int
    remaining: int
    account_age_days: int
    unlock_30_in_days: int


def _gen_code(prefix: str = "ZEEJ") -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{prefix}-{body}"


def _share(code: str, base_url: str | None = None) -> tuple[str, str]:
    # 前端可再替换 origin；后端给相对路径提示
    path = f"/register?invite={code}"
    url = f"{(base_url or '').rstrip('')}{path}" if base_url else path
    text = (
        f"Welcome to Zeej\n"
        f"邀请你加入 Zeej 邀请制小站。\n"
        f"注册链接：{url}\n"
        f"邀请码：{code}\n"
        f"（打开链接后填写邀请码与邮箱验证码即可注册）"
    )
    return url, text


def _to_out(item: InviteCode, origin: str = "") -> InviteOut:
    remaining = max(0, item.max_uses - item.use_count) if item.is_active else 0
    if item.expires_at and item.expires_at < datetime.utcnow():
        remaining = 0
    url, text = _share(item.code, origin)
    return InviteOut(
        id=item.id,
        code=item.code,
        max_uses=item.max_uses,
        use_count=item.use_count,
        note=item.note or "",
        is_active=item.is_active,
        created_at=item.created_at,
        expires_at=item.expires_at,
        remaining=remaining,
        invite_url=url,
        share_text=text,
    )


def _create_one(
    db: Session,
    *,
    creator: User,
    note: str = "",
    expires_days: int | None = 30,
    max_uses: int = 1,
) -> InviteCode:
    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
    code = _gen_code()
    while db.query(InviteCode).filter(InviteCode.code == code).first():
        code = _gen_code()
    item = InviteCode(
        code=code,
        max_uses=max_uses,
        note=(note or "").strip()[:200],
        expires_at=expires_at,
        is_active=True,
        created_by_id=creator.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/quota", response_model=InviteQuotaOut)
def my_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteQuotaOut:
    used = _quota_used(db, current_user.id)
    limit = invite_quota_for(current_user)
    age = account_age_days(current_user)
    unlock = 0 if age >= 10 or is_admin(current_user) else max(0, 10 - age)
    return InviteQuotaOut(
        used=used,
        limit=limit,
        remaining=max(0, limit - used),
        account_age_days=age,
        unlock_30_in_days=unlock,
    )


@router.get("/mine", response_model=list[InviteOut])
def my_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InviteOut]:
    rows = (
        db.query(InviteCode)
        .filter(InviteCode.created_by_id == current_user.id)
        .order_by(InviteCode.created_at.desc())
        .all()
    )
    return [_to_out(i) for i in rows]


@router.post("/one", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def create_one_invite(
    payload: InviteOneIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteOut:
    """每位用户一次只生成一条邀请（含链接与文案），不可批量。"""
    used = _quota_used(db, current_user.id)
    limit = invite_quota_for(current_user)
    if used >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"邀请额度已用完（{used}/{limit}）。注册满 10 天后可提升至 30。",
        )
    item = _create_one(
        db,
        creator=current_user,
        note=payload.note,
        expires_days=payload.expires_days,
        max_uses=1,
    )
    return _to_out(item)


@router.get("", response_model=list[InviteOut])
def list_invites(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    only_active: bool = Query(default=False),
) -> list[InviteOut]:
    q = db.query(InviteCode).order_by(InviteCode.created_at.desc())
    if only_active:
        q = q.filter(InviteCode.is_active.is_(True))
    return [_to_out(i) for i in q.all()]


@router.post("", response_model=InviteBatchOut, status_code=status.HTTP_201_CREATED)
def create_invites_batch(
    payload: InviteCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> InviteBatchOut:
    """仅站长可批量生成。"""
    created: list[InviteCode] = []
    for _ in range(payload.count):
        item = _create_one(
            db,
            creator=admin,
            note=payload.note,
            expires_days=payload.expires_days,
            max_uses=payload.max_uses,
        )
        created.append(item)
    return InviteBatchOut(codes=[_to_out(i) for i in created])


@router.post("/{invite_id}/revoke", response_model=InviteOut)
def revoke_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteOut:
    item = db.get(InviteCode, invite_id)
    if not item:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if not is_admin(current_user) and item.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权作废该邀请码")
    item.is_active = False
    db.commit()
    db.refresh(item)
    return _to_out(item)
