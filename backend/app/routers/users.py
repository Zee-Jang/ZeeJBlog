import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.avatar_store import AVATAR_DIR, ALLOWED, compress_avatar_bytes, ensure_dirs
from app.database import get_db
from app.models import User, UserRole
from app.schemas import PublicUserOut, UserOut, UserUpdateIn
from app.services import to_public_user, to_user_out

router = APIRouter(prefix="/api/users", tags=["users"])

MAX_UPLOAD_RAW = 12 * 1024 * 1024


@router.get("/me", response_model=UserOut)
def my_profile(current_user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(current_user)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)
    if "nickname" in data and data["nickname"] is not None:
        from app.moderation import assert_nickname_ok

        nick = assert_nickname_ok(data["nickname"])
        current_user.nickname = nick
        current_user.name = current_user.nickname
    if "bio" in data and data["bio"] is not None:
        current_user.bio = data["bio"].strip()[:500]
    if "allow_message_requests" in data and data["allow_message_requests"] is not None:
        current_user.allow_message_requests = data["allow_message_requests"]
    if "show_email" in data and data["show_email"] is not None:
        current_user.show_email = data["show_email"]
    if "show_join_date" in data and data["show_join_date"] is not None:
        current_user.show_join_date = data["show_join_date"]
    db.commit()
    db.refresh(current_user)
    return to_user_out(current_user)


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED:
        raise HTTPException(status_code=400, detail="请上传图片文件（JPG / PNG / WebP）")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > MAX_UPLOAD_RAW:
        raise HTTPException(status_code=400, detail="图片过大，请选择 12MB 以内的文件")

    try:
        compressed = compress_avatar_bytes(raw, ctype)
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析图片，请换一张试试") from None

    ensure_dirs()
    # 覆盖同用户旧文件
    for old in AVATAR_DIR.glob(f"u{current_user.id}_*"):
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass

    name = f"u{current_user.id}.jpg"
    path = AVATAR_DIR / name
    path.write_bytes(compressed)
    # cache-bust query so browsers refresh
    current_user.avatar_url = f"/uploads/avatars/{name}?v={path.stat().st_mtime_ns}"
    db.commit()
    db.refresh(current_user)
    return to_user_out(current_user)


@router.delete("/me/avatar", response_model=UserOut)
def remove_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    ensure_dirs()
    for old in AVATAR_DIR.glob(f"u{current_user.id}*"):
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    return to_user_out(current_user)


@router.get("", response_model=list[PublicUserOut])
def list_users(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PublicUserOut]:
    from app.bot import ensure_bot_user

    bot = ensure_bot_user(db)
    db.commit()

    query = db.query(User).filter(User.is_active.is_(True), User.id != current_user.id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.nickname.ilike(like)) | (User.name.ilike(like)))
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # 机器人 + 掌柜固定出现在成员列表靠前，避免分页挤掉徽章信息
    if not q and page == 1 and bot.id != current_user.id and bot.is_active:
        pinned: list[User] = [bot]
        admins = (
            db.query(User)
            .filter(
                User.is_active.is_(True),
                User.role == UserRole.admin,
                User.id != current_user.id,
                User.id != bot.id,
            )
            .all()
        )
        pinned.extend(admins)
        pinned_ids = {u.id for u in pinned}
        rows = [u for u in rows if u.id not in pinned_ids]
        rows = [*pinned, *rows][:page_size]
    return [to_public_user(u, current_user) for u in rows]


@router.get("/{user_id}", response_model=PublicUserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PublicUserOut:
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="用户不存在")
    return to_public_user(user, current_user)
