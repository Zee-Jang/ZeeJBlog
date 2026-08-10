import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from app.models import (
    ChatRequestStatus,
    MessageStatus,
    NotificationType,
    PostKind,
    ThreadStatus,
    UserRole,
)
from app.timeutil import utc_iso

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")

UtcDateTime = Annotated[
    datetime,
    PlainSerializer(lambda v: utc_iso(v), return_type=str, when_used="json-unless-none"),
]
UtcDateTimeOpt = Annotated[
    datetime | None,
    PlainSerializer(lambda v: utc_iso(v), return_type=str | None, when_used="json-unless-none"),
]


def validate_password(value: str) -> str:
    if not PASSWORD_PATTERN.match(value):
        raise ValueError("密码至少 8 位，且同时包含字母和数字")
    return value


class SendCodeIn(BaseModel):
    email: EmailStr


class RegisterIn(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=30)
    password: str
    confirm_password: str
    email_code: str = Field(min_length=4, max_length=10)
    invite_code: str = Field(min_length=4, max_length=64)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str) -> str:
        cleaned = re.sub(r"[<>]", "", value.strip())
        if not cleaned:
            raise ValueError("昵称不能为空")
        return cleaned

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterIn":
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class ResetPasswordIn(BaseModel):
    email: EmailStr
    email_code: str = Field(min_length=4, max_length=10)
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordIn":
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordIn":
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nickname: str
    name: str
    role: UserRole
    avatar_url: str | None = None
    bio: str = ""
    allow_message_requests: bool = True
    show_email: bool = False
    show_join_date: bool = True
    created_at: UtcDateTime
    muted_until: UtcDateTimeOpt = None
    mute_reason: str = ""
    is_muted: bool = False
    bot_preset: str = "normal"
    bot_enabled: bool = True
    bot_rounds_limit: int = 10
    bot_rounds_used: int = 0
    bot_rounds_remaining: int = 10
    bot_msgs_per_round: int = 100
    bot_msgs_this_round: int = 0
    bot_msgs_remaining: int = 100


class PublicUserOut(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None = None
    bio: str = ""
    allow_message_requests: bool = True
    created_at: UtcDateTimeOpt = None
    email: str | None = None
    is_muted: bool = False
    is_bot: bool = False
    is_admin: bool = False


class UserUpdateIn(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=30)
    bio: str | None = Field(default=None, max_length=500)
    allow_message_requests: bool | None = None
    show_email: bool | None = None
    show_join_date: bool | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: PostKind
    title: str
    body: str
    created_at: UtcDateTime
    author_name: str = ""
    on_home: bool = False


class PostCreate(BaseModel):
    kind: PostKind
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50000)


class PostUpdate(BaseModel):
    kind: PostKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=50000)
    on_home: bool | None = None


class PostAppend(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str
    stack: list[str] = Field(default_factory=list)
    status: str
    demo_url: str | None
    github_url: str | None = None
    readme: str = ""
    note: str
    owner_id: int | None = None
    owner_name: str = ""
    sort_order: int
    created_at: UtcDateTimeOpt = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2000)
    github_url: str | None = Field(default=None, max_length=500)
    readme: str = Field(default="", max_length=50000)
    demo_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default="building", max_length=20)
    stack: list[str] = Field(default_factory=list)


class ProjectImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class ProjectImportPreview(BaseModel):
    title: str
    summary: str
    github_url: str
    readme: str = ""
    demo_url: str | None = None
    stack: list[str] = Field(default_factory=list)
    source: str


class MessageOut(BaseModel):
    id: int
    thread_id: int
    sender_id: int
    sender_name: str = ""
    sender_avatar_url: str | None = None
    content: str
    status: MessageStatus
    created_at: UtcDateTime
    read_at: UtcDateTimeOpt
    is_mine: bool = False


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ThreadOut(BaseModel):
    id: int
    peer_id: int
    peer_name: str
    status: ThreadStatus
    updated_at: UtcDateTime
    unread_count: int = 0
    last_message: str | None = None
    peer_active: bool = True
    peer_is_bot: bool = False
    peer_is_admin: bool = False


class ChatRequestCreate(BaseModel):
    receiver_id: int
    message: str = Field(default="", max_length=500)


class ChatRequestOut(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    receiver_id: int
    receiver_name: str
    message: str
    status: ChatRequestStatus
    created_at: UtcDateTime
    responded_at: UtcDateTimeOpt


class NotificationOut(BaseModel):
    id: int
    type: NotificationType
    title: str
    content: str
    related_id: int | None
    is_read: bool
    created_at: UtcDateTime


class ReportCreate(BaseModel):
    target_user_id: int | None = None
    target_message_id: int | None = None
    reason: str = Field(min_length=2, max_length=500)


class MessageOk(BaseModel):
    detail: str
