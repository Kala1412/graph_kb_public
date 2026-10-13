import datetime
from enum import Enum
from pydantic import BaseModel

"""用户相关"""
class UserRole(str, Enum):
    admin = "admin"
    user = "user"

class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"

class UserBase(BaseModel):
    username: str
    email: str | None = None

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.user
    status: UserStatus = UserStatus.active

class UserResponse(UserBase):
    id: int
    role: UserRole
    avatar_url: str | None = None
    status: UserStatus = UserStatus.active
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    id: int
    username: str | None = None
    email: str | None = None
    password: str | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class UserMeResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: UserRole
    avatar_url: str | None = None
    status: UserStatus = UserStatus.active

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    username: str | None = None
    email: str | None = None

class UserProfileUpdateResponse(BaseModel):
    user: UserMeResponse
    require_relogin: bool = False


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class AvatarUploadResponse(BaseModel):
    avatar_url: str


class MedicalProfileRecordType(str, Enum):
    allergy = "allergy"
    disease = "disease"
    symptom = "symptom"
    history = "history"
    constitution = "constitution"
    medication = "medication"
    other = "other"


class MedicalProfileRecordSource(str, Enum):
    manual = "manual"
    chat_import = "chat_import"
    migration = "migration"


class MedicalProfileRecordCreate(BaseModel):
    user_id: int | None = None
    record_type: MedicalProfileRecordType = MedicalProfileRecordType.other
    content: str
    source: MedicalProfileRecordSource = MedicalProfileRecordSource.manual


class MedicalProfileRecordUpdate(BaseModel):
    record_type: MedicalProfileRecordType | None = None
    content: str | None = None
    source: MedicalProfileRecordSource | None = None


class MedicalProfileRecordResponse(BaseModel):
    id: int
    user_id: int
    record_type: MedicalProfileRecordType
    content: str
    source: MedicalProfileRecordSource
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class MedicalProfileRecordListResponse(BaseModel):
    items: list[MedicalProfileRecordResponse]
    total: int


class ForumStatus(str, Enum):
    active = "active"
    hidden = "hidden"
    deleted = "deleted"


class ForumLikeTargetType(str, Enum):
    post = "post"
    comment = "comment"


class ForumAuthorResponse(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class ForumCategoryBase(BaseModel):
    name: str
    description: str | None = None
    sort_order: int = 0


class ForumCategoryCreate(ForumCategoryBase):
    is_enabled: bool = True


class ForumCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_enabled: bool | None = None


class ForumCategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    sort_order: int
    is_enabled: bool
    created_at: datetime.datetime


class ForumCategoryListResponse(BaseModel):
    items: list[ForumCategoryResponse]
    total: int


class ForumPostCreate(BaseModel):
    category_id: int
    title: str
    content: str


class ForumPostStatusUpdate(BaseModel):
    status: ForumStatus


class ForumCommentCreate(BaseModel):
    content: str
    parent_comment_id: int | None = None


class ForumCommentStatusUpdate(BaseModel):
    status: ForumStatus


class ForumPostListItemResponse(BaseModel):
    id: int
    category: ForumCategoryResponse
    author: ForumAuthorResponse
    title: str
    content: str
    status: ForumStatus
    view_count: int
    comment_count: int
    like_count: int
    liked_by_me: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ForumPostListResponse(BaseModel):
    items: list[ForumPostListItemResponse]
    total: int
    page: int
    page_size: int


class ForumCommentResponse(BaseModel):
    id: int
    post_id: int
    author: ForumAuthorResponse
    parent_comment_id: int | None = None
    content: str
    status: ForumStatus
    like_count: int
    liked_by_me: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime
    replies: list["ForumCommentResponse"] = []


class ForumCommentListResponse(BaseModel):
    items: list[ForumCommentResponse]
    total: int


class ForumPostDetailResponse(BaseModel):
    id: int
    category: ForumCategoryResponse
    author: ForumAuthorResponse
    title: str
    content: str
    status: ForumStatus
    view_count: int
    comment_count: int
    like_count: int
    liked_by_me: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ForumLikeResponse(BaseModel):
    target_type: ForumLikeTargetType
    target_id: int
    like_count: int
    liked_by_me: bool = True

"""知识库相关"""
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None

class MessageResponse(BaseModel):
    role: str
    content: str
    references: list | None = None
    graph_path: list | None = None
    # 结构化图片附件；前端通过该字段渲染聊天消息中的图片，不从 content 反解析。
    attachments: list | None = None
    created_at: datetime.datetime
    class Config: from_attributes = True

class SessionResponse(BaseModel):
    id: str
    title: str
    user_id: int | None = None
    kb_id: int | None = None
    created_at: datetime.datetime
    class Config: from_attributes = True


"""审计日志相关"""
class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None = None
    actor_username: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    resource_name: str | None = None
    status: str
    detail: dict | None = None
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


ForumCommentResponse.model_rebuild()
