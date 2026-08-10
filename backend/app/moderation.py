"""昵称 / 资料内容审核：站长名变体 + 脏话短语（不过度限制单字）。"""

from __future__ import annotations

import re

from fastapi import HTTPException

# 站长相关：整词/短语（大小写不敏感），含子串匹配
_RESERVED_PHRASES = [
    "zeej",
    "zealjang",
    "zeeljang",
    "zhiqiang",
    "姚志强",
    "志强",
]

# 英文脏话短语（整词边界）
_EN_SWEARS = [
    "fuck",
    "fucker",
    "fucking",
    "cock",
    "dick",
    "pussy",
    "bitch",
    "shit",
    "asshole",
    "motherfucker",
]

# 中文脏话短语（子串匹配）。不单独封禁「操」「草」单字。
_CN_SWEARS = [
    "鸡巴",
    "肏",
    "尻",
    "屌",
    "操你",
    "操你妈",
    "草你妈",
    "日你妈",
    "傻逼",
    "傻b",
    "煞笔",
    "脑残",
    "去死",
    "贱逼",
    "烂货",
]


def _fold(text: str) -> str:
    return re.sub(r"[\s\-_.·•]+", "", (text or "").strip()).lower()


def nickname_violation(nickname: str) -> str | None:
    raw = (nickname or "").strip()
    if not raw:
        return "昵称不能为空"
    folded = _fold(raw)
    raw_l = raw.lower()

    for phrase in _RESERVED_PHRASES:
        p = _fold(phrase)
        if p and p in folded:
            return "该昵称不可用（包含保留称呼）"
        if phrase in raw:
            return "该昵称不可用（包含保留称呼）"

    for w in _EN_SWEARS:
        if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", raw_l):
            return "昵称包含不当用语，请更换"

    for w in _CN_SWEARS:
        if w in raw or _fold(w) in folded:
            return "昵称包含不当用语，请更换"

    return None


def assert_nickname_ok(nickname: str) -> str:
    nick = re.sub(r"[<>]", "", (nickname or "").strip())
    err = nickname_violation(nick)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if not nick:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    return nick[:30]
