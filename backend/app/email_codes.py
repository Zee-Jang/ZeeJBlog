import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import get_settings
from app.mailer import send_email
from app.models import EmailVerification, VerifyPurpose

settings = get_settings()


def _gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_and_send_code(db: Session, email: str, purpose: VerifyPurpose) -> str:
    email = email.lower().strip()
    now = datetime.utcnow()

    latest = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == purpose,
            EmailVerification.used_at.is_(None),
        )
        .order_by(EmailVerification.created_at.desc())
        .first()
    )
    if latest and latest.created_at:
        try:
            elapsed = (now - latest.created_at.replace(tzinfo=None)).total_seconds()
        except TypeError:
            elapsed = settings.verify_resend_seconds
        if elapsed < settings.verify_resend_seconds:
            raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    hour_ago = now - timedelta(hours=1)
    hourly = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == purpose,
            EmailVerification.created_at >= hour_ago,
        )
        .count()
    )
    if hourly >= settings.verify_email_hourly_limit:
        raise HTTPException(status_code=429, detail="该邮箱发送次数已达上限，请稍后再试")

    code = _gen_code()
    row = EmailVerification(
        email=email,
        purpose=purpose,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=settings.verify_code_ttl_minutes),
    )
    db.add(row)
    db.commit()

    if purpose == VerifyPurpose.register:
        subject = "注册 Zeej Blog 的邮箱验证码"
        body = (
            "你好，你正在注册 Zeej Blog。\n\n"
            f"你的验证码是：\n\n{code}\n\n"
            f"验证码有效期为 {settings.verify_code_ttl_minutes} 分钟，请勿将验证码告诉他人。\n"
            "如果不是本人操作，请忽略此邮件。"
        )
    elif purpose == VerifyPurpose.reset_password:
        subject = "Zeej Blog 密码重置验证码"
        body = (
            "你好，你正在重置 Zeej Blog 的登录密码。\n\n"
            f"你的验证码是：\n\n{code}\n\n"
            f"验证码有效期为 {settings.verify_code_ttl_minutes} 分钟。\n"
            "如果不是本人操作，请立即检查账号安全。"
        )
    else:
        subject = "Zeej Blog 邮箱验证码"
        body = f"你的验证码是：{code}\n有效期 {settings.verify_code_ttl_minutes} 分钟。"

    try:
        send_email(email, subject, body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"邮件发送失败：{exc}") from exc
    return code


def consume_code(
    db: Session,
    email: str,
    purpose: VerifyPurpose,
    code: str,
    *,
    commit: bool = True,
) -> None:
    email = email.lower().strip()
    now = datetime.utcnow()
    row = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == purpose,
            EmailVerification.used_at.is_(None),
        )
        .order_by(EmailVerification.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    if row.expires_at < now:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if row.attempt_count >= settings.verify_max_attempts:
        raise HTTPException(status_code=429, detail="验证失败次数过多，请重新获取验证码")

    if not verify_password(code.strip(), row.code_hash):
        row.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误")

    row.used_at = now
    if commit:
        db.commit()
    else:
        db.flush()
