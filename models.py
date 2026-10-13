import datetime
import json

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from database import Base


class FileStatus:
    """文件处理状态常量"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR_PARSING = "error_parsing"
    INDEXING = "indexing"
    INDEXED = "indexed"
    ERROR_INDEXING = "error_indexing"

class UserStatus:
    ACTIVE = "active"
    DISABLED = "disabled"


class MedicalProfileRecordType:
    ALLERGY = "allergy"
    DISEASE = "disease"
    SYMPTOM = "symptom"
    HISTORY = "history"
    CONSTITUTION = "constitution"
    MEDICATION = "medication"
    OTHER = "other"


class MedicalProfileRecordSource:
    MANUAL = "manual"
    CHAT_IMPORT = "chat_import"
    MIGRATION = "migration"


class ForumStatus:
    # 讨论区内容统一状态：
    # - active：普通用户可见；
    # - hidden：仅管理员可见，用于基础治理；
    # - deleted：逻辑删除预留，当前不提供物理删除接口。
    ACTIVE = "active"
    HIDDEN = "hidden"
    DELETED = "deleted"


class ForumLikeTargetType:
    # 点赞对象类型统一收口到一个表，避免帖子点赞和评论点赞拆成两张结构重复的表。
    POST = "post"
    COMMENT = "comment"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer,primary_key=True,index=True)
    username = Column(String,unique=True,index=True)
    email = Column(String)
    role = Column(String, nullable=False, default="user")
    password = Column(String)
    avatar_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default=UserStatus.ACTIVE)

    knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
    forum_posts = relationship("ForumPost", back_populates="author")
    forum_comments = relationship("ForumComment", back_populates="author")
    forum_likes = relationship("ForumLike", back_populates="user")

class KnowledgeBase(Base):
    """知识库表：用于给文件分类"""
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime,default=datetime.datetime.utcnow())

    owner = relationship("User", back_populates="knowledge_bases")
    files = relationship("KnowledgeFile", back_populates="knowledge_base")

class KnowledgeFile(Base):
    """知识文件表：存储上传的文件信息"""
    __tablename__ = "knowledge_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String,nullable=False)

    # 【关键】MinIO 路径字段（原始文件 + Markdown 文件）
    minio_url = Column(String,nullable=False)
    minio_path = Column(String,nullable=False)
    markdown_minio_url = Column(String)
    markdown_minio_path = Column(String)

    file_size = Column(Integer)

    status = Column(String,default=FileStatus.UPLOADED)
    error_message = Column(Text)

    # 【新增】处理参数（存储为JSON字符串）
    processing_params = Column(Text)

    kb_id = Column(Integer,ForeignKey("knowledge_bases.id"))

    created_at = Column(DateTime,default=datetime.datetime.utcnow())
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    knowledge_base = relationship("KnowledgeBase", back_populates="files")

class ChatSession(Base):
    """会话表：一个会话包含多条消息"""
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True)
    title = Column(String(100), default="新对话")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 一个会话对应多条消息，级联删除
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """消息表：存储具体的每一句对话"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String)
    content = Column(Text)
    references_json = Column(Text, nullable=True)
    graph_path_json = Column(Text, nullable=True)
    # 结构化附件（图片）元数据，避免把 URL/对象信息硬拼到 content 里污染语义文本。
    attachments_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    @property
    def references(self):
        if not self.references_json:
            return []
        try:
            return json.loads(self.references_json)
        except Exception:
            return []

    @property
    def graph_path(self):
        if not self.graph_path_json:
            return []
        try:
            return json.loads(self.graph_path_json)
        except Exception:
            return []

    @property
    def attachments(self):
        """
        仅返回结构化附件数组，供前端渲染缩略图/历史回放使用。
        这里不做业务逻辑，仅做 JSON 解析兜底，避免破坏 ORM 读取稳定性。
        """
        if not self.attachments_json:
            return []
        try:
            data = json.loads(self.attachments_json)
            return data if isinstance(data, list) else []
        except Exception:
            return []


class UserMedicalProfile(Base):
    """长期记忆表：存储用户核心医疗画像（如过敏史、慢性病等）"""
    __tablename__ = "user_medical_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    # 抽取出的医疗画像摘要文本，例如："用户患有高血压；对青霉素过敏"
    medical_facts = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", backref="medical_profile")


class UserMedicalProfileRecord(Base):
    """用户病症状况明细表：一位用户可拥有多条独立记录"""
    __tablename__ = "user_medical_profile_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    record_type = Column(String, nullable=False, default=MedicalProfileRecordType.OTHER)
    content = Column(Text, nullable=False)
    source = Column(String, nullable=False, default=MedicalProfileRecordSource.MANUAL)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", backref="medical_profile_records")


class AuditLog(Base):
    """审计日志表：记录关键操作"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_id = Column(Integer, nullable=True)
    actor_username = Column(String, nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    resource_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="success")
    detail = Column(Text)
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ForumCategory(Base):
    __tablename__ = "forum_categories"

    # 分类是“全站社区”维度，不绑定知识库。
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    # sort_order 供前端固定展示顺序使用，管理员可在后台手动调节。
    sort_order = Column(Integer, nullable=False, default=0)
    # SQLite 没有原生布尔型，这里用 0/1 存储，DTO 层再转成 true/false。
    is_enabled = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    posts = relationship("ForumPost", back_populates="category")


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("forum_categories.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    # 帖子状态由管理员治理接口控制，普通用户只能发布，不能直接改状态。
    status = Column(String(20), nullable=False, default=ForumStatus.ACTIVE, index=True)
    # 下面三个都是冗余统计字段，目的是减少列表页的聚合查询成本。
    view_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    author = relationship("User", back_populates="forum_posts")
    category = relationship("ForumCategory", back_populates="posts")
    comments = relationship("ForumComment", back_populates="post")


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # parent_comment_id 允许为空：
    # - 为空表示一级评论；
    # - 有值表示回复某条一级评论。
    # 仅允许一层回复，路由层拦截对回复的再次回复。
    parent_comment_id = Column(Integer, ForeignKey("forum_comments.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default=ForumStatus.ACTIVE, index=True)
    like_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    post = relationship("ForumPost", back_populates="comments")
    author = relationship("User", back_populates="forum_comments")
    parent_comment = relationship("ForumComment", remote_side=[id], backref="replies")


class ForumLike(Base):
    __tablename__ = "forum_likes"
    __table_args__ = (
        # 单用户对同一对象只能点一次赞，这是点赞幂等与计数正确性的核心约束。
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_forum_like_user_target"),
        # 按目标查询点赞状态/计数时会频繁命中这组字段，因此建组合索引。
        Index("ix_forum_likes_target", "target_type", "target_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="forum_likes")
