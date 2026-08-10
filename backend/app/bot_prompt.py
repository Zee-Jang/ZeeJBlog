"""Bot 系统提示词与附加文档（存 SiteSetting）。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.routers.site import get_setting, set_setting

BOT_PROMPT_KEY = "bot_system_prompt"
BOT_DOCS_KEY = "bot_prompt_docs"
BOT_NAME_KEY = "bot_display_name"
BOT_BIO_KEY = "bot_display_bio"

_DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "data" / "zeej_bot_system_prompt.txt"


def default_system_prompt() -> str:
    if _DEFAULT_PROMPT_FILE.exists():
        return _DEFAULT_PROMPT_FILE.read_text(encoding="utf-8").strip()
    return (
        get_settings().bot_system_prompt
        or "你是 Zeej 邀请制小站的站内助手，用简洁自然的中文回复。"
    )


def ensure_bot_prompt(db: Session) -> str:
    cur = get_setting(db, BOT_PROMPT_KEY, "")
    if not cur.strip():
        text = default_system_prompt()
        set_setting(db, BOT_PROMPT_KEY, text)
        return text
    return cur


def get_bot_docs(db: Session) -> list[dict]:
    raw = get_setting(db, BOT_DOCS_KEY, "[]")
    try:
        data = json.loads(raw or "[]")
        if isinstance(data, list):
            return [
                {"name": str(x.get("name") or "doc"), "content": str(x.get("content") or "")}
                for x in data
                if isinstance(x, dict)
            ]
    except json.JSONDecodeError:
        pass
    return []


def set_bot_docs(db: Session, docs: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for d in docs[:20]:
        name = str(d.get("name") or "doc.txt")[:120]
        content = str(d.get("content") or "")[:50000]
        if content.strip():
            cleaned.append({"name": name, "content": content})
    set_setting(db, BOT_DOCS_KEY, json.dumps(cleaned, ensure_ascii=False))
    return cleaned


def build_full_system_prompt(db: Session) -> str:
    base = ensure_bot_prompt(db).strip()
    docs = get_bot_docs(db)
    if not docs:
        return base
    parts = [base, "", "—— 补充资料 ——"]
    for d in docs:
        parts.append(f"【{d['name']}】\n{d['content']}")
    return "\n\n".join(parts)[:120000]
