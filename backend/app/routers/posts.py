from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Post, PostKind, User
from app.schemas import PostAppend, PostCreate, PostOut, PostUpdate
from app.timeutil import EAST_ASIA, UTC

router = APIRouter(prefix="/api/posts", tags=["posts"])

BODY_MAX = 50000


def _to_out(post: Post) -> PostOut:
    return PostOut(
        id=post.id,
        kind=post.kind,
        title=post.title,
        body=post.body,
        created_at=post.created_at,
        author_name=(post.author.nickname or post.author.name) if post.author else "Zeej",
        on_home=bool(getattr(post, "on_home", False)),
    )


@router.get("", response_model=list[PostOut])
def list_posts(
    kind: PostKind | None = Query(default=None),
    on_home: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PostOut]:
    query = db.query(Post).options(joinedload(Post.author))
    if kind is not None:
        query = query.filter(Post.kind == kind)
    if on_home is not None:
        query = query.filter(Post.on_home.is_(on_home))
    posts = query.order_by(Post.created_at.desc()).all()
    return [_to_out(p) for p in posts]


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PostOut:
    post = Post(
        author_id=admin.id,
        kind=payload.kind,
        title=payload.title.strip(),
        body=payload.body.strip(),
        on_home=False,
    )
    db.add(post)
    db.commit()
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.id == post.id)
        .one()
    )
    return _to_out(post)


@router.patch("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PostOut:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="内容不存在")
    if payload.kind is not None:
        post.kind = payload.kind
    if payload.title is not None:
        post.title = payload.title.strip()
    if payload.body is not None:
        post.body = payload.body.strip()
    if payload.on_home is not None:
        post.on_home = payload.on_home
    db.commit()
    db.refresh(post)
    return _to_out(post)


@router.post("/{post_id}/home", response_model=PostOut)
def toggle_home(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PostOut:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="内容不存在")
    post.on_home = not bool(post.on_home)
    db.commit()
    db.refresh(post)
    return _to_out(post)


@router.post("/{post_id}/append", response_model=PostOut)
def append_post(
    post_id: int,
    payload: PostAppend,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PostOut:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="内容不存在")
    addition = payload.body.strip()
    stamp = datetime.now(UTC).astimezone(EAST_ASIA).strftime("%Y-%m-%d %H:%M")
    block = f"\n\n—— 追记 · {stamp} ——\n{addition}"
    merged = f"{(post.body or '').rstrip()}{block}"
    if len(merged) > BODY_MAX:
        raise HTTPException(status_code=400, detail="追记后内容过长")
    post.body = merged
    db.commit()
    db.refresh(post)
    return _to_out(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="内容不存在")
    db.delete(post)
    db.commit()
