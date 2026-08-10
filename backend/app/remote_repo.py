"""Fetch public repo metadata + README from GitHub / Gitee (HTTPS, no git clone)."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.config import get_settings

_GH_HTTPS = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com[/:](?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.I,
)
_GH_SSH = re.compile(
    r"git@github\.com:(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.I,
)
_GITEE = re.compile(
    r"(?:https?://)?(?:www\.)?gitee\.com[/:](?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.I,
)
_GITEE_SSH = re.compile(
    r"git@gitee\.com:(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.I,
)


@dataclass
class RepoRef:
    host: str  # github | gitee
    owner: str
    repo: str


@dataclass
class RepoPreview:
    title: str
    summary: str
    github_url: str
    readme: str
    demo_url: str | None
    stack: list[str]
    source: str


def parse_remote_url(raw: str) -> RepoRef:
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请粘贴仓库地址")

    for pattern, host in (
        (_GH_SSH, "github"),
        (_GH_HTTPS, "github"),
        (_GITEE_SSH, "gitee"),
        (_GITEE, "gitee"),
    ):
        m = pattern.search(text)
        if m:
            owner = m.group("owner").strip()
            repo = m.group("repo").strip().removesuffix(".git")
            if owner and repo:
                return RepoRef(host=host, owner=owner, repo=repo)

    raise HTTPException(
        status_code=400,
        detail="仅支持 GitHub / Gitee 地址，例如 https://github.com/owner/repo 或 git@github.com:owner/repo.git",
    )


def _headers(host: str) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/json",
        "User-Agent": "Zeej-Blog/1.0",
    }
    if host == "github" and settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    if host == "gitee" and settings.gitee_token:
        # Gitee uses access_token query param more often; header also accepted by some endpoints
        headers["Authorization"] = f"token {settings.gitee_token}"
    return headers


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> dict | None:
    try:
        res = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return None
    if res.status_code == 404:
        return None
    if res.status_code == 403:
        raise HTTPException(
            status_code=502,
            detail="远程仓库接口拒绝访问（可能触发频率限制）。可在 .env 配置 GITHUB_TOKEN / GITEE_TOKEN 后重试。",
        )
    if res.status_code >= 400:
        return None
    try:
        data = res.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


async def _get_text(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> str:
    try:
        res = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return ""
    if res.status_code >= 400:
        return ""
    return res.text or ""


def _decode_github_readme(payload: dict) -> str:
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        return ""
    try:
        return base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
    except Exception:
        return ""


async def fetch_repo_preview(raw_url: str) -> RepoPreview:
    ref = parse_remote_url(raw_url)
    headers = _headers(ref.host)
    timeout = httpx.Timeout(12.0, connect=8.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if ref.host == "github":
            meta = await _get_json(
                client,
                f"https://api.github.com/repos/{ref.owner}/{ref.repo}",
                headers,
            )
            if not meta:
                raise HTTPException(
                    status_code=404,
                    detail="找不到该 GitHub 仓库（需为公开仓库，或检查地址是否正确）",
                )
            title = str(meta.get("name") or ref.repo)
            summary = str(meta.get("description") or "") or title
            html_url = str(meta.get("html_url") or f"https://github.com/{ref.owner}/{ref.repo}")
            demo = str(meta.get("homepage") or "").strip() or None
            stack: list[str] = []
            lang = meta.get("language")
            if isinstance(lang, str) and lang.strip():
                stack.append(lang.strip())
            topics = meta.get("topics")
            if isinstance(topics, list):
                for t in topics:
                    if isinstance(t, str) and t.strip() and t.strip() not in stack:
                        stack.append(t.strip())
            stack = stack[:8]

            readme = ""
            readme_json = await _get_json(
                client,
                f"https://api.github.com/repos/{ref.owner}/{ref.repo}/readme",
                {**headers, "Accept": "application/vnd.github+json"},
            )
            if readme_json:
                readme = _decode_github_readme(readme_json)
            if not readme:
                branch = str(meta.get("default_branch") or "main")
                for name in ("README.md", "readme.md", "README.MD", "README"):
                    text = await _get_text(
                        client,
                        f"https://raw.githubusercontent.com/{ref.owner}/{ref.repo}/{branch}/{name}",
                        {"User-Agent": "Zeej-Blog/1.0"},
                    )
                    if text.strip():
                        readme = text
                        break

            return RepoPreview(
                title=_truncate(title, 120),
                summary=_truncate(summary, 2000) or title,
                github_url=html_url,
                readme=_truncate(readme, 50000),
                demo_url=_truncate(demo, 500) if demo else None,
                stack=stack,
                source="github",
            )

        # Gitee
        settings = get_settings()
        api = f"https://gitee.com/api/v5/repos/{ref.owner}/{ref.repo}"
        if settings.gitee_token:
            api = f"{api}?access_token={settings.gitee_token}"
        meta = await _get_json(client, api, headers)
        if not meta:
            raise HTTPException(
                status_code=404,
                detail="找不到该 Gitee 仓库（需为公开仓库，或检查地址是否正确）",
            )
        title = str(meta.get("name") or ref.repo)
        summary = str(meta.get("description") or "") or title
        html_url = str(meta.get("html_url") or f"https://gitee.com/{ref.owner}/{ref.repo}")
        demo = str(meta.get("homepage") or "").strip() or None
        stack = []
        lang = meta.get("language")
        if isinstance(lang, str) and lang.strip():
            stack.append(lang.strip())

        readme = ""
        branch = str(meta.get("default_branch") or "master")
        readme_api = (
            f"https://gitee.com/api/v5/repos/{ref.owner}/{ref.repo}/readme"
            f"?ref={branch}"
        )
        if settings.gitee_token:
            readme_api += f"&access_token={settings.gitee_token}"
        readme_json = await _get_json(client, readme_api, headers)
        if readme_json:
            # Gitee often returns content already decoded or base64
            content = readme_json.get("content")
            encoding = str(readme_json.get("encoding") or "")
            if isinstance(content, str) and content:
                if encoding == "base64":
                    try:
                        readme = base64.b64decode(content.replace("\n", "")).decode(
                            "utf-8", errors="replace"
                        )
                    except Exception:
                        readme = content
                else:
                    readme = content
        if not readme:
            for name in ("README.md", "readme.md", "README"):
                text = await _get_text(
                    client,
                    f"https://gitee.com/{ref.owner}/{ref.repo}/raw/{branch}/{name}",
                    {"User-Agent": "Zeej-Blog/1.0"},
                )
                if text.strip():
                    readme = text
                    break

        return RepoPreview(
            title=_truncate(title, 120),
            summary=_truncate(summary, 2000) or title,
            github_url=html_url,
            readme=_truncate(readme, 50000),
            demo_url=_truncate(demo, 500) if demo else None,
            stack=stack[:8],
            source="gitee",
        )
