import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("zeej.mail")


def send_email(to_email: str, subject: str, body: str) -> None:
    """开发模式只打印到终端；正式模式走 SMTP。二者互斥，避免开发模式又去连 SMTP。"""
    settings = get_settings()
    if settings.mail_dev_mode or not settings.smtp_ready:
        logger.warning(
            "[MAIL DEV] to=%s subject=%s\n%s",
            to_email,
            subject,
            body,
        )
        print(
            f"\n===== MAIL DEV =====\nto: {to_email}\nsubject: {subject}\n{body}\n====================\n"
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    if settings.smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
