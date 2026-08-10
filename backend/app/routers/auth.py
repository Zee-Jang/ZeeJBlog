from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.email_codes import consume_code, create_and_send_code
from app.models import InviteCode, User, UserRole, VerifyPurpose
from app.schemas import (
    ChangePasswordIn,
    MessageOk,
    RegisterIn,
    ResetPasswordIn,
    SendCodeIn,
    TokenOut,
    UserOut,
)
from app.security import limit_auth
from app.services import to_user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _code_sent_detail(code: str) -> str:
    # 仅显式开启 MAIL_DEV_MODE 时回传验证码；未配 SMTP 时只提示看终端
    if settings.mail_dev_mode:
        return f"验证码已发送（开发模式）：{code}"
    if not settings.smtp_ready:
        return "验证码已生成（未配置邮件服务，请查看后端终端日志）"
    return "验证码已发送，请查收邮箱"


def _validate_invite(invite: InviteCode | None) -> InviteCode:
    if not invite or not invite.is_active:
        raise HTTPException(status_code=400, detail="邀请码无效")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="邀请码已过期")
    if invite.use_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已用完")
    return invite


@router.post("/send-register-code", response_model=MessageOk)
def send_register_code(
    payload: SendCodeIn,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageOk:
    limit_auth(request, limit=8, window_seconds=60)
    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="该邮箱已注册，请直接登录或找回密码")
    code = create_and_send_code(db, email, VerifyPurpose.register)
    return MessageOk(detail=_code_sent_detail(code))


@router.post("/send-reset-code", response_model=MessageOk)
def send_reset_code(
    payload: SendCodeIn,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageOk:
    limit_auth(request, limit=8, window_seconds=60)
    email = payload.email.lower().strip()
    # 统一文案，避免通过响应差异枚举邮箱；开发模式验证码只打终端
    generic = MessageOk(detail="若邮箱已注册，验证码已发送")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        return generic
    create_and_send_code(db, email, VerifyPurpose.reset_password)
    return generic


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    limit_auth(request, limit=5, window_seconds=60)

    invite = (
        db.query(InviteCode)
        .filter(InviteCode.code == payload.invite_code.strip().upper())
        .first()
    )
    invite = _validate_invite(invite)
    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    consume_code(db, email, VerifyPurpose.register, payload.email_code, commit=False)

    nickname = payload.nickname.strip()
    from app.moderation import assert_nickname_ok

    nickname = assert_nickname_ok(nickname)
    # 原子占用邀请次数，避免 SQLite 下并发超卖
    from sqlalchemy import text as sa_text

    occupied = db.execute(
        sa_text(
            """
            UPDATE invite_codes
            SET use_count = use_count + 1
            WHERE id = :id
              AND is_active = 1
              AND use_count < max_uses
              AND (expires_at IS NULL OR expires_at >= :now)
            """
        ),
        {"id": invite.id, "now": datetime.utcnow()},
    )
    if occupied.rowcount != 1:
        raise HTTPException(status_code=400, detail="邀请码已用完或无效")
    db.refresh(invite)

    invite_code = invite.code
    from app.bot_quota import apply_default_bot_quota, notify_bot_quota, notify_welcome

    user = User(
        email=email,
        name=nickname,
        nickname=nickname,
        password_hash=hash_password(payload.password),
        role=UserRole.visitor,
        token_version=1,
        is_active=True,
        registered_invite_code=invite_code,
    )
    apply_default_bot_quota(user)
    db.add(user)
    db.flush()

    notify_welcome(db, user)
    notify_bot_quota(db, user, reason="welcome")
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=to_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    limit_auth(request, limit=8, window_seconds=60)
    user = db.query(User).filter(User.email == form_data.username.lower().strip()).first()
    if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    from app.bot import is_bot_user

    if is_bot_user(user):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=to_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(current_user)


@router.post("/reset-password", response_model=MessageOk)
def reset_password(
    payload: ResetPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageOk:
    limit_auth(request, limit=5, window_seconds=60)
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    ok = MessageOk(detail="若邮箱有效，密码已重置，请使用新密码登录")
    # 未注册 / 已停用：走与错误验证码相同的失败路径，避免枚举
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    consume_code(db, email, VerifyPurpose.reset_password, payload.email_code, commit=False)
    if verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    user.password_hash = hash_password(payload.password)
    user.token_version += 1
    db.commit()
    return ok


@router.post("/change-password", response_model=MessageOk)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageOk:
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1
    db.commit()
    return MessageOk(detail="密码已修改，请重新登录")


@router.post("/logout", response_model=MessageOk)
def logout(current_user: User = Depends(get_current_user)) -> MessageOk:
    # JWT 无状态：前端删 token 即可；接口保留便于统一调用
    _ = current_user
    return MessageOk(detail="已退出")
