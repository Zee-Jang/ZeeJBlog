from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import SiteSetting, User

router = APIRouter(prefix="/api/site", tags=["site"])

HOME_LEAD_KEY = "home_lead"
HOME_LEAD_LOCALES = ("zh-CN", "zh-TW", "en", "ja")

DEFAULT_HOME_LEADS: dict[str, str] = {
    "zh-CN": (
        "汉语使用者 · AI 爱好者 · 不爱敲代码 · 不爱刷算法。"
        "这里是 Zeej 的碎碎念、项目橱窗，与成员交流。"
    ),
    "zh-TW": (
        "漢語使用者 · AI 愛好者 · 不愛敲代碼 · 不愛刷算法。"
        "這裡是 Zeej 的碎碎念、項目櫥窗，與成員交流。"
    ),
    "en": (
        "Chinese speaker · AI enthusiast · not into grinding code · not into grinding algorithms. "
        "Here are Zeej’s musings, project showcase, and chats with members."
    ),
    "ja": (
        "中国語話者 · AI好き · コードを書くのは苦手 · アルゴリズム練磨も苦手。"
        "ここは Zeej のつぶやき、プロジェクト展示、メンバー交流の場です。"
    ),
}

# 兼容旧代码
DEFAULT_HOME_LEAD = DEFAULT_HOME_LEADS["zh-CN"]


class HomeOut(BaseModel):
    home_lead: str
    locale: str = "zh-CN"
    bot_user_id: int | None = None
    bot_name: str = ""


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(SiteSetting, key)
    if not row:
        return default
    return row.value or default


def set_setting(db: Session, key: str, value: str) -> SiteSetting:
    row = db.get(SiteSetting, key)
    if row is None:
        for obj in db.new:
            if isinstance(obj, SiteSetting) and obj.key == key:
                row = obj
                break
    if row is None:
        row = SiteSetting(key=key, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    return row


def parse_home_leads(raw: str | None) -> dict[str, str]:
    text = (raw or "").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                out = {
                    loc: str(data.get(loc) or "").strip()[:800] for loc in HOME_LEAD_LOCALES
                }
                if any(out.values()):
                    return out
        except json.JSONDecodeError:
            pass
    # 旧版单语字符串 → 视为简体，其余用默认翻译补齐
    out = {loc: "" for loc in HOME_LEAD_LOCALES}
    out["zh-CN"] = text[:800] if text else DEFAULT_HOME_LEADS["zh-CN"]
    for loc in HOME_LEAD_LOCALES:
        if loc != "zh-CN" and not out[loc]:
            out[loc] = DEFAULT_HOME_LEADS[loc]
    return out


def serialize_home_leads(leads: dict[str, str]) -> str:
    cleaned = {
        loc: str(leads.get(loc) or "").strip()[:800] for loc in HOME_LEAD_LOCALES
    }
    if not any(cleaned.values()):
        cleaned = dict(DEFAULT_HOME_LEADS)
    return json.dumps(cleaned, ensure_ascii=False)


def get_home_leads(db: Session, *, persist_upgrade: bool = False) -> dict[str, str]:
    raw = get_setting(db, HOME_LEAD_KEY, "")
    if not raw.strip():
        leads = dict(DEFAULT_HOME_LEADS)
        set_setting(db, HOME_LEAD_KEY, serialize_home_leads(leads))
        return leads
    leads = parse_home_leads(raw)
    # 旧版单语字符串升成多语言 JSON，便于各语言独立编辑
    if persist_upgrade and not raw.strip().startswith("{"):
        set_setting(db, HOME_LEAD_KEY, serialize_home_leads(leads))
    return leads


def ensure_home_lead(db: Session, locale: str = "zh-CN") -> str:
    leads = get_home_leads(db)
    loc = locale if locale in HOME_LEAD_LOCALES else "zh-CN"
    return (
        leads.get(loc)
        or leads.get("zh-CN")
        or DEFAULT_HOME_LEADS.get(loc)
        or DEFAULT_HOME_LEAD
    ).strip()


def set_home_leads(db: Session, leads: dict[str, str]) -> dict[str, str]:
    cleaned = {
        loc: str(leads.get(loc) or "").strip()[:800] for loc in HOME_LEAD_LOCALES
    }
    if not cleaned["zh-CN"]:
        cleaned["zh-CN"] = DEFAULT_HOME_LEADS["zh-CN"]
    for loc in HOME_LEAD_LOCALES:
        if loc != "zh-CN" and not cleaned[loc]:
            cleaned[loc] = DEFAULT_HOME_LEADS[loc]
    set_setting(db, HOME_LEAD_KEY, serialize_home_leads(cleaned))
    return cleaned


@router.get("/home", response_model=HomeOut)
def home_public(
    locale: str = Query(default="zh-CN"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> HomeOut:
    from app.bot import ensure_bot_user

    bot = ensure_bot_user(db)
    loc = locale if locale in HOME_LEAD_LOCALES else "zh-CN"
    lead = ensure_home_lead(db, loc)
    db.commit()
    return HomeOut(
        home_lead=lead,
        locale=loc,
        bot_user_id=bot.id,
        bot_name=bot.nickname or bot.name or "Zeej Bot",
    )
