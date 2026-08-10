"""简单内存限流：按 IP + 路径限制频率。上线后可换成 Redis。"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")
        bucket.append(now)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """仅用直连 IP 做限流。不信任可伪造的 X-Forwarded-For。

    若日后前置可信反代，再改为「仅在 TRUST_PROXY=true 时读取」并校验来源。
    """
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def limit_auth(request: Request, *, limit: int = 8, window_seconds: int = 60) -> None:
    ip = client_ip(request)
    path = request.url.path
    limiter.check(f"{ip}:{path}", limit=limit, window_seconds=window_seconds)
