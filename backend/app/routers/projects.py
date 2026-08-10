import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import display_name, get_current_user, require_admin
from app.database import get_db
from app.models import Project, User
from app.remote_repo import fetch_repo_preview
from app.schemas import ProjectCreate, ProjectImportIn, ProjectImportPreview, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title.strip().lower()).strip("-")
    base = base[:40] or "project"
    return f"{base}-{int(datetime.utcnow().timestamp())}"


def _stack_str(stack: list[str] | None) -> str:
    items: list[str] = []
    for raw in stack or []:
        s = (raw or "").strip()
        if s and s not in items:
            items.append(s)
        if len(items) >= 12:
            break
    return ", ".join(items)


def _to_out(p: Project) -> ProjectOut:
    stack = [s.strip() for s in (p.stack or "").split(",") if s.strip()]
    return ProjectOut(
        id=p.id,
        slug=p.slug,
        title=p.title,
        summary=p.summary,
        stack=stack,
        status=p.status,
        demo_url=p.demo_url,
        github_url=p.github_url,
        readme=p.readme or "",
        note=p.note or "",
        owner_id=p.owner_id,
        owner_name=display_name(p.owner) if p.owner else "",
        sort_order=p.sort_order,
        created_at=p.created_at,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProjectOut]:
    items = (
        db.query(Project)
        .options(joinedload(Project.owner))
        .order_by(Project.sort_order.asc(), Project.id.desc())
        .all()
    )
    return [_to_out(p) for p in items]


@router.post("/import-preview", response_model=ProjectImportPreview)
async def import_preview(
    payload: ProjectImportIn,
    _: User = Depends(require_admin),
) -> ProjectImportPreview:
    preview = await fetch_repo_preview(payload.url)
    return ProjectImportPreview(
        title=preview.title,
        summary=preview.summary,
        github_url=preview.github_url,
        readme=preview.readme,
        demo_url=preview.demo_url,
        stack=preview.stack,
        source=preview.source,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProjectOut:
    project = Project(
        slug=_slugify(payload.title),
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        github_url=(payload.github_url or "").strip() or None,
        readme=(payload.readme or "").strip(),
        demo_url=(payload.demo_url or "").strip() or None,
        status=payload.status.strip() or "building",
        owner_id=admin.id,
        note="",
        stack=_stack_str(payload.stack),
        sort_order=100,
    )
    db.add(project)
    db.commit()
    project = (
        db.query(Project)
        .options(joinedload(Project.owner))
        .filter(Project.id == project.id)
        .one()
    )
    return _to_out(project)


@router.get("/{slug}", response_model=ProjectOut)
def get_project(
    slug: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ProjectOut:
    item = (
        db.query(Project)
        .options(joinedload(Project.owner))
        .filter(Project.slug == slug)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _to_out(item)
