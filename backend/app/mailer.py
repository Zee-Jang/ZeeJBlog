import logging
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from app.config import get_settings

logger = logging.getLogger("zeej.mail")


def send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
    """开发模式只打印到终端；正式模式走 SMTP。未配置 SMTP 时直接失败，避免静默假成功。"""
    settings = get_settings()
    if settings.mail_dev_mode:
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

    if not settings.smtp_ready:
        raise RuntimeError("SMTP 未配置：请设置 SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD / SMTP_FROM")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

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


def build_admin_notice_html(subject: str, body: str, recipient_name: str) -> str:
    """Render a self-contained, escaped HTML email for a host-authored notice."""
    safe_subject = escape(subject.strip())
    safe_name = escape(recipient_name.strip() or "朋友")
    paragraphs = []
    for block in body.strip().split("\n\n"):
        text = escape(block.strip()).replace("\n", "<br>")
        if text:
            paragraphs.append(
                f'<p style="margin:0 0 16px;line-height:1.8;color:#34443d;">{text}</p>'
            )
    content = "".join(paragraphs)
    return f"""<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;padding:0;background:#edf3ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;">
    <div style="padding:36px 16px;">
      <div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #dce6e0;border-radius:22px;overflow:hidden;box-shadow:0 16px 45px rgba(22,56,44,.08);">
        <div style="padding:30px 34px;background:#173e32;color:#fff;">
          <div style="font-size:12px;letter-spacing:.18em;opacity:.72;">A NOTE FROM ZEEJ</div>
          <h1 style="margin:14px 0 0;font-size:28px;line-height:1.35;font-weight:600;">{safe_subject}</h1>
        </div>
        <div style="padding:32px 34px;">
          <p style="margin:0 0 20px;color:#173e32;font-size:16px;">你好，{safe_name}：</p>
          {content}
          <div style="margin-top:28px;padding-top:20px;border-top:1px solid #e5ece8;color:#718078;font-size:13px;line-height:1.7;">
            这封邮件由 Zeej 站务发送。你可以回到站点查看最新内容。<br>
            <a href="https://zeej.me" style="color:#246b55;text-decoration:none;">打开 zeej.me →</a>
          </div>
        </div>
      </div>
      <p style="margin:18px auto 0;text-align:center;color:#8a9891;font-size:12px;">Zeej · an invite-only corner</p>
    </div>
  </body>
</html>"""
