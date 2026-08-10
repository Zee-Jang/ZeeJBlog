from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

# backend/app -> backend/uploads/avatars
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
AVATAR_DIR = UPLOAD_ROOT / "avatars"

MAX_EDGE = 512
MAX_BYTES = 300 * 1024
ALLOWED = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}


def ensure_dirs() -> None:
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)


def compress_avatar_bytes(raw: bytes, content_type: str | None = None) -> bytes:
    """Resize + JPEG compress to roughly a few hundred KB."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    w, h = img.size
    scale = min(1.0, MAX_EDGE / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)

    quality = 85
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    data = out.getvalue()
    while len(data) > MAX_BYTES and quality > 45:
        quality -= 8
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        data = out.getvalue()

    edge = MAX_EDGE
    while len(data) > MAX_BYTES and edge > 160:
        edge = int(edge * 0.8)
        w, h = img.size
        scale = min(1.0, edge / max(w, h))
        smaller = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        smaller.save(out, format="JPEG", quality=72, optimize=True)
        data = out.getvalue()
        img = smaller

    return data
