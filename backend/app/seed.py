from datetime import datetime

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.models import InviteCode, Post, PostKind, Project, User, UserRole
from app.routers.site import DEFAULT_HOME_LEADS, HOME_LEAD_KEY, serialize_home_leads, set_setting
from app.schemas import PASSWORD_PATTERN

settings = get_settings()


def _ensure_admin(db: Session) -> User:
    """仅在站长账号不存在时创建；已存在则保证角色/激活，绝不重置密码。"""
    email = (settings.admin_email or "").strip().lower()
    if not email:
        raise RuntimeError("settings.admin_email 未配置")

    admin = db.query(User).filter(User.email == email).first()
    if not admin:
        password = (settings.admin_password or "").strip()
        if not PASSWORD_PATTERN.match(password):
            raise RuntimeError(
                "首次创建站长需要在 backend/.env 设置 ADMIN_PASSWORD"
                "（至少 8 位，且同时包含字母和数字）"
            )
        admin = User(
            email=email,
            name=settings.admin_name or "Zeej",
            nickname=settings.admin_name or "Zeej",
            password_hash=hash_password(password),
            role=UserRole.admin,
            bio="汉语使用者 · AI 爱好者 · 不爱敲代码 · 不爱刷算法",
            allow_message_requests=True,
            token_version=1,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        return admin

    admin.role = UserRole.admin
    admin.is_active = True
    if not admin.nickname:
        admin.nickname = settings.admin_name or "Zeej"
    if not admin.name:
        admin.name = settings.admin_name or admin.nickname
    return admin


def seed_database(db: Session) -> None:
    admin = _ensure_admin(db)

    from app.bot import ensure_bot_user
    from app.bot_prompt import ensure_bot_prompt

    ensure_bot_user(db)
    ensure_bot_prompt(db)

    # 默认不开放公共邀请码；本地可在 .env 设 SEED_DEFAULT_INVITE=true
    if settings.seed_default_invite and settings.default_invite_code:
        invite = (
            db.query(InviteCode)
            .filter(InviteCode.code == settings.default_invite_code.strip().upper())
            .first()
        )
        if not invite:
            db.add(
                InviteCode(
                    code=settings.default_invite_code.strip().upper(),
                    max_uses=50,
                    note="默认邀请码（开发用，上线后请作废）",
                    is_active=True,
                    created_by_id=admin.id,
                )
            )
        elif not invite.created_by_id:
            invite.created_by_id = admin.id

    if db.query(Project).count() == 0:
        db.add_all(
            [
                Project(
                    slug="todolist",
                    title="岸上 Todo",
                    summary="带登录、今天/明天视图、优先级与标签的待办。Vue + FastAPI。",
                    stack="Vue 3,FastAPI,SQLAlchemy,JWT",
                    status="building",
                    demo_url="http://127.0.0.1:5174",
                    github_url="https://github.com/Zee-Jang/TodoList",
                    readme=(
                        "# 岸上 Todo\n\n"
                        "带登录、今天/明天视图、优先级与标签的待办。"
                        "仓库：https://github.com/Zee-Jang/TodoList"
                    ),
                    note="独立项目，代码在 todolist/，与博客分开。",
                    owner_id=admin.id,
                    sort_order=1,
                ),
            ]
        )

    if db.query(Post).filter(Post.kind == PostKind.muse).count() == 0:
        db.add_all(
            [
                Post(
                    author_id=admin.id,
                    kind=PostKind.muse,
                    title="不爱敲代码，但爱把想法做成东西",
                    body="我是汉语使用者，也是 AI 爱好者。算法题刷不动，纯手写代码也提不起劲——但用工具把点子落地，这件事我挺上瘾。",
                    created_at=datetime.utcnow(),
                ),
                Post(
                    author_id=admin.id,
                    kind=PostKind.muse,
                    title="碎碎念是合法的",
                    body="这里没有 KPI。想到什么就写什么。欢迎拿邀请码进来坐坐，别客气。",
                    created_at=datetime.utcnow(),
                ),
            ]
        )

    if db.query(Post).filter(Post.kind == PostKind.diary).count() == 0:
        db.add(
            Post(
                author_id=admin.id,
                kind=PostKind.diary,
                title="站点开机日",
                body="今天把个人站搭起来了：邀请码进门、碎碎念、日记，还有社交聊天申请。先用起来，再慢慢长。",
                created_at=datetime.utcnow(),
            )
        )

    from app.models import SiteSetting

    if not db.get(SiteSetting, HOME_LEAD_KEY):
        set_setting(db, HOME_LEAD_KEY, serialize_home_leads(DEFAULT_HOME_LEADS))

    db.commit()
