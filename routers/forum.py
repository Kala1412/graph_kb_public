from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas_likes_dto as schemas
from utils.audit_logger import log_audit_event
from utils.auth_midware import get_current_user, get_db, is_admin, require_admin

forum = APIRouter(prefix="/forum", tags=["讨论区"])


def _author_payload(user: models.User) -> schemas.ForumAuthorResponse:
    # 统一作者信息出参，避免各个接口手写 author 字段时出现不一致。
    return schemas.ForumAuthorResponse(
        id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
    )


def _category_payload(category: models.ForumCategory) -> schemas.ForumCategoryResponse:
    return schemas.ForumCategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        is_enabled=bool(category.is_enabled),
        created_at=category.created_at,
    )


def _post_payload(
    post: models.ForumPost,
    author: models.User,
    category: models.ForumCategory,
    liked_by_me: bool = False,
) -> schemas.ForumPostListItemResponse:
    # 列表页与详情页都需要 author/category/liked_by_me 这些“拼装字段”，
    # 因此统一在路由层做组装，不把这种展示逻辑下沉到 ORM 模型里。
    return schemas.ForumPostListItemResponse(
        id=post.id,
        category=_category_payload(category),
        author=_author_payload(author),
        title=post.title,
        content=post.content,
        status=post.status,
        view_count=post.view_count,
        comment_count=post.comment_count,
        like_count=post.like_count,
        liked_by_me=liked_by_me,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _post_detail_payload(
    post: models.ForumPost,
    author: models.User,
    category: models.ForumCategory,
    liked_by_me: bool = False,
) -> schemas.ForumPostDetailResponse:
    return schemas.ForumPostDetailResponse(
        id=post.id,
        category=_category_payload(category),
        author=_author_payload(author),
        title=post.title,
        content=post.content,
        status=post.status,
        view_count=post.view_count,
        comment_count=post.comment_count,
        like_count=post.like_count,
        liked_by_me=liked_by_me,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _comment_payload(
    comment: models.ForumComment,
    author: models.User,
    liked_by_me: bool = False,
    replies: list[schemas.ForumCommentResponse] | None = None,
) -> schemas.ForumCommentResponse:
    return schemas.ForumCommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author=_author_payload(author),
        parent_comment_id=comment.parent_comment_id,
        content=comment.content,
        status=comment.status,
        like_count=comment.like_count,
        liked_by_me=liked_by_me,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=replies or [],
    )


async def _get_category_or_404(db: AsyncSession, category_id: int) -> models.ForumCategory:
    category = await db.get(models.ForumCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="讨论分类不存在")
    return category


async def _get_post_or_404(
    db: AsyncSession,
    post_id: int,
    current_user: models.User,
    include_hidden: bool = False,
) -> models.ForumPost:
    # include_hidden=True 主要给管理员治理接口和详情页内部使用。
    # 普通用户最终是否能看 hidden 内容，还要在外层再做一次业务判断。
    post = await db.get(models.ForumPost, post_id)
    if not post or post.status == models.ForumStatus.DELETED:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if not include_hidden and post.status != models.ForumStatus.ACTIVE and not is_admin(current_user):
        raise HTTPException(status_code=404, detail="帖子不存在")
    return post


async def _get_comment_or_404(
    db: AsyncSession,
    comment_id: int,
    current_user: models.User,
    include_hidden: bool = False,
) -> models.ForumComment:
    # 评论与帖子保持相同的状态判定策略，避免治理逻辑不一致。
    comment = await db.get(models.ForumComment, comment_id)
    if not comment or comment.status == models.ForumStatus.DELETED:
        raise HTTPException(status_code=404, detail="评论不存在")
    if not include_hidden and comment.status != models.ForumStatus.ACTIVE and not is_admin(current_user):
        raise HTTPException(status_code=404, detail="评论不存在")
    return comment


async def _liked_target_ids(
    db: AsyncSession,
    user_id: int,
    target_type: str,
    target_ids: list[int],
) -> set[int]:
    # 一次性取回“当前用户对一批对象的点赞状态”，
    # 避免列表页逐条查 liked_by_me 造成 N+1 查询。
    if not target_ids:
        return set()
    result = await db.execute(
        select(models.ForumLike.target_id).where(
            models.ForumLike.user_id == user_id,
            models.ForumLike.target_type == target_type,
            models.ForumLike.target_id.in_(target_ids),
        )
    )
    return set(result.scalars().all())


async def _refresh_post_comment_count(db: AsyncSession, post_id: int) -> None:
    # 评论数只统计 active 评论。
    # 这样管理员隐藏评论后，普通用户看到的 comment_count 和实际列表能保持一致。
    count = (
        await db.execute(
            select(func.count(models.ForumComment.id)).where(
                models.ForumComment.post_id == post_id,
                models.ForumComment.status == models.ForumStatus.ACTIVE,
            )
        )
    ).scalar() or 0
    await db.execute(
        update(models.ForumPost)
        .where(models.ForumPost.id == post_id)
        .values(comment_count=count)
    )


@forum.get("/categories", response_model=schemas.ForumCategoryListResponse)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 普通用户只能看到启用中的分类；
    # 管理员需要看到全部分类，才能在后台做启停切换。
    stmt = select(models.ForumCategory).order_by(
        models.ForumCategory.sort_order.asc(),
        models.ForumCategory.id.asc(),
    )
    if not is_admin(current_user):
        stmt = stmt.where(models.ForumCategory.is_enabled == 1)
    result = await db.execute(stmt)
    items = [_category_payload(item) for item in result.scalars().all()]
    return schemas.ForumCategoryListResponse(items=items, total=len(items))


@forum.get("/posts", response_model=schemas.ForumPostListResponse)
async def list_posts(
    category_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    sort_by: str = Query(default="latest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = (
        select(models.ForumPost, models.User, models.ForumCategory)
        .join(models.User, models.User.id == models.ForumPost.author_id)
        .join(models.ForumCategory, models.ForumCategory.id == models.ForumPost.category_id)
    )
    count_stmt = select(func.count(models.ForumPost.id)).join(
        models.ForumCategory,
        models.ForumCategory.id == models.ForumPost.category_id,
    )

    if not is_admin(current_user):
        stmt = stmt.where(
            models.ForumPost.status == models.ForumStatus.ACTIVE,
            models.ForumCategory.is_enabled == 1,
        )
        count_stmt = count_stmt.where(
            models.ForumPost.status == models.ForumStatus.ACTIVE,
            models.ForumCategory.is_enabled == 1,
        )
    else:
        stmt = stmt.where(models.ForumPost.status != models.ForumStatus.DELETED)
        count_stmt = count_stmt.where(models.ForumPost.status != models.ForumStatus.DELETED)

    if category_id:
        stmt = stmt.where(models.ForumPost.category_id == category_id)
        count_stmt = count_stmt.where(models.ForumPost.category_id == category_id)

    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                models.ForumPost.title.ilike(like),
                models.ForumPost.content.ilike(like),
            )
        )
        count_stmt = count_stmt.where(
            or_(
                models.ForumPost.title.ilike(like),
                models.ForumPost.content.ilike(like),
            )
        )

    if sort_by == "hot":
        # “最热”优先看点赞、评论和浏览，再按发布时间兜底。
        stmt = stmt.order_by(
            models.ForumPost.like_count.desc(),
            models.ForumPost.comment_count.desc(),
            models.ForumPost.view_count.desc(),
            models.ForumPost.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(models.ForumPost.created_at.desc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt)).all()
    liked_ids = await _liked_target_ids(
        db,
        current_user.id,
        models.ForumLikeTargetType.POST,
        [post.id for post, _, _ in rows],
    )

    items = [
        _post_payload(post, author, category, liked_by_me=post.id in liked_ids)
        for post, author, category in rows
    ]
    return schemas.ForumPostListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@forum.post("/posts", response_model=schemas.ForumPostDetailResponse, status_code=201)
async def create_post(
    payload: schemas.ForumPostCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和内容不能为空")

    category = await _get_category_or_404(db, payload.category_id)
    if not category.is_enabled and not is_admin(current_user):
        raise HTTPException(status_code=400, detail="该分类暂不可用")

    post = models.ForumPost(
        author_id=current_user.id,
        category_id=payload.category_id,
        title=title,
        content=content,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    await log_audit_event(
        action="forum.post.create",
        actor=current_user,
        resource_type="forum_post",
        resource_id=str(post.id),
        resource_name=post.title,
        status="success",
        detail={"category_id": payload.category_id},
        request=request,
    )
    return _post_detail_payload(post, current_user, category, liked_by_me=False)


@forum.get("/posts/{post_id}", response_model=schemas.ForumPostDetailResponse)
async def get_post_detail(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 详情页每打开一次都累加浏览数；这里不区分是否重复访问，按简单 PV 模型处理。
    post = await _get_post_or_404(db, post_id, current_user, include_hidden=True)
    if post.status != models.ForumStatus.ACTIVE and not is_admin(current_user):
        raise HTTPException(status_code=404, detail="帖子不存在")

    await db.execute(
        update(models.ForumPost)
        .where(models.ForumPost.id == post.id)
        .values(view_count=models.ForumPost.view_count + 1)
    )
    await db.commit()
    await db.refresh(post)

    author = await db.get(models.User, post.author_id)
    category = await db.get(models.ForumCategory, post.category_id)
    liked_by_me = post.id in await _liked_target_ids(
        db, current_user.id, models.ForumLikeTargetType.POST, [post.id]
    )
    return _post_detail_payload(post, author, category, liked_by_me=liked_by_me)


@forum.post("/posts/{post_id}/like", response_model=schemas.ForumLikeResponse)
async def like_post(
    post_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    post = await _get_post_or_404(db, post_id, current_user)
    # 点赞利用唯一约束兜底：
    # - 首次点赞：flush 成功，计数 +1；
    # - 重复点赞：触发 IntegrityError，回滚后返回当前计数。
    like = models.ForumLike(
        user_id=current_user.id,
        target_type=models.ForumLikeTargetType.POST,
        target_id=post.id,
    )
    db.add(like)
    try:
        await db.flush()
        post.like_count += 1
        await db.commit()
    except IntegrityError:
        await db.rollback()
    await db.refresh(post)

    await log_audit_event(
        action="forum.post.like",
        actor=current_user,
        resource_type="forum_post",
        resource_id=str(post.id),
        resource_name=post.title,
        status="success",
        detail=None,
        request=request,
    )
    return schemas.ForumLikeResponse(
        target_type=schemas.ForumLikeTargetType.post,
        target_id=post.id,
        like_count=post.like_count,
        liked_by_me=True,
    )


@forum.delete("/posts/{post_id}/like", response_model=schemas.ForumLikeResponse)
async def unlike_post(
    post_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    post = await _get_post_or_404(db, post_id, current_user, include_hidden=True)
    # 取消点赞允许幂等：没点过赞也返回成功，只是计数不变。
    like = (
        await db.execute(
            select(models.ForumLike).where(
                models.ForumLike.user_id == current_user.id,
                models.ForumLike.target_type == models.ForumLikeTargetType.POST,
                models.ForumLike.target_id == post.id,
            )
        )
    ).scalar_one_or_none()
    if like:
        await db.delete(like)
        post.like_count = max(0, post.like_count - 1)
        await db.commit()
        await db.refresh(post)

    await log_audit_event(
        action="forum.post.unlike",
        actor=current_user,
        resource_type="forum_post",
        resource_id=str(post.id),
        resource_name=post.title,
        status="success",
        detail=None,
        request=request,
    )
    return schemas.ForumLikeResponse(
        target_type=schemas.ForumLikeTargetType.post,
        target_id=post.id,
        like_count=post.like_count,
        liked_by_me=False,
    )


@forum.get("/posts/{post_id}/comments", response_model=schemas.ForumCommentListResponse)
async def list_comments(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    post = await _get_post_or_404(db, post_id, current_user, include_hidden=True)
    if post.status != models.ForumStatus.ACTIVE and not is_admin(current_user):
        raise HTTPException(status_code=404, detail="帖子不存在")

    stmt = (
        select(models.ForumComment, models.User)
        .join(models.User, models.User.id == models.ForumComment.author_id)
        .where(models.ForumComment.post_id == post_id)
        .order_by(models.ForumComment.created_at.asc(), models.ForumComment.id.asc())
    )
    if not is_admin(current_user):
        stmt = stmt.where(models.ForumComment.status == models.ForumStatus.ACTIVE)
    else:
        stmt = stmt.where(models.ForumComment.status != models.ForumStatus.DELETED)

    rows = (await db.execute(stmt)).all()
    liked_ids = await _liked_target_ids(
        db,
        current_user.id,
        models.ForumLikeTargetType.COMMENT,
        [comment.id for comment, _ in rows],
    )

    children_map: dict[int, list[schemas.ForumCommentResponse]] = defaultdict(list)
    root_items: list[schemas.ForumCommentResponse] = []

    for comment, author in rows:
        item = _comment_payload(comment, author, liked_by_me=comment.id in liked_ids)
        if comment.parent_comment_id:
            children_map[comment.parent_comment_id].append(item)
        else:
            root_items.append(item)

    for item in root_items:
        item.replies = children_map.get(item.id, [])

    return schemas.ForumCommentListResponse(items=root_items, total=len(rows))


@forum.post("/posts/{post_id}/comments", response_model=schemas.ForumCommentResponse, status_code=201)
async def create_comment(
    post_id: int,
    payload: schemas.ForumCommentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    post = await _get_post_or_404(db, post_id, current_user)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")

    parent_comment_id = payload.parent_comment_id
    if parent_comment_id:
        # 这里把一层回复限制放在接口层，避免前端绕过 UI 直接发二级/三级回复。
        parent_comment = await _get_comment_or_404(db, parent_comment_id, current_user, include_hidden=True)
        if parent_comment.status != models.ForumStatus.ACTIVE and not is_admin(current_user):
            raise HTTPException(status_code=404, detail="回复目标不存在")
        if parent_comment.post_id != post_id:
            raise HTTPException(status_code=400, detail="回复目标不属于当前帖子")
        if parent_comment.parent_comment_id:
            raise HTTPException(status_code=400, detail="仅支持一层回复")

    comment = models.ForumComment(
        post_id=post.id,
        author_id=current_user.id,
        parent_comment_id=parent_comment_id,
        content=content,
    )
    db.add(comment)
    await db.flush()
    # 新评论写入后立即回刷 comment_count，保证帖子列表/详情统计同步。
    await _refresh_post_comment_count(db, post.id)
    await db.commit()
    await db.refresh(comment)

    await log_audit_event(
        action="forum.comment.create",
        actor=current_user,
        resource_type="forum_comment",
        resource_id=str(comment.id),
        resource_name=f"post:{post.id}",
        status="success",
        detail={"post_id": post.id, "parent_comment_id": parent_comment_id},
        request=request,
    )
    return _comment_payload(comment, current_user, liked_by_me=False)


@forum.post("/comments/{comment_id}/like", response_model=schemas.ForumLikeResponse)
async def like_comment(
    comment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    comment = await _get_comment_or_404(db, comment_id, current_user)
    # 评论点赞策略与帖子点赞完全一致，保持交互和数据语义统一。
    like = models.ForumLike(
        user_id=current_user.id,
        target_type=models.ForumLikeTargetType.COMMENT,
        target_id=comment.id,
    )
    db.add(like)
    try:
        await db.flush()
        comment.like_count += 1
        await db.commit()
    except IntegrityError:
        await db.rollback()
    await db.refresh(comment)

    await log_audit_event(
        action="forum.comment.like",
        actor=current_user,
        resource_type="forum_comment",
        resource_id=str(comment.id),
        resource_name=f"post:{comment.post_id}",
        status="success",
        detail=None,
        request=request,
    )
    return schemas.ForumLikeResponse(
        target_type=schemas.ForumLikeTargetType.comment,
        target_id=comment.id,
        like_count=comment.like_count,
        liked_by_me=True,
    )


@forum.delete("/comments/{comment_id}/like", response_model=schemas.ForumLikeResponse)
async def unlike_comment(
    comment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    comment = await _get_comment_or_404(db, comment_id, current_user, include_hidden=True)
    like = (
        await db.execute(
            select(models.ForumLike).where(
                models.ForumLike.user_id == current_user.id,
                models.ForumLike.target_type == models.ForumLikeTargetType.COMMENT,
                models.ForumLike.target_id == comment.id,
            )
        )
    ).scalar_one_or_none()
    if like:
        await db.delete(like)
        comment.like_count = max(0, comment.like_count - 1)
        await db.commit()
        await db.refresh(comment)

    await log_audit_event(
        action="forum.comment.unlike",
        actor=current_user,
        resource_type="forum_comment",
        resource_id=str(comment.id),
        resource_name=f"post:{comment.post_id}",
        status="success",
        detail=None,
        request=request,
    )
    return schemas.ForumLikeResponse(
        target_type=schemas.ForumLikeTargetType.comment,
        target_id=comment.id,
        like_count=comment.like_count,
        liked_by_me=False,
    )


@forum.get("/admin/categories", response_model=schemas.ForumCategoryListResponse)
async def admin_list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return await list_categories(db=db, current_user=current_user)


@forum.post("/admin/categories", response_model=schemas.ForumCategoryResponse, status_code=201)
async def admin_create_category(
    payload: schemas.ForumCategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    category = models.ForumCategory(
        name=name,
        description=(payload.description or "").strip() or None,
        sort_order=payload.sort_order,
        is_enabled=1 if payload.is_enabled else 0,
    )
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="分类名称已存在")
    await db.refresh(category)

    await log_audit_event(
        action="forum.category.create",
        actor=current_user,
        resource_type="forum_category",
        resource_id=str(category.id),
        resource_name=category.name,
        status="success",
        detail={"is_enabled": bool(category.is_enabled)},
        request=request,
    )
    return _category_payload(category)


@forum.put("/admin/categories/{category_id}", response_model=schemas.ForumCategoryResponse)
async def admin_update_category(
    category_id: int,
    payload: schemas.ForumCategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    category = await _get_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name.strip()
        if not category.name:
            raise HTTPException(status_code=400, detail="分类名称不能为空")
    if payload.description is not None:
        category.description = payload.description.strip() or None
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_enabled is not None:
        category.is_enabled = 1 if payload.is_enabled else 0

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="分类名称已存在")
    await db.refresh(category)

    await log_audit_event(
        action="forum.category.update",
        actor=current_user,
        resource_type="forum_category",
        resource_id=str(category.id),
        resource_name=category.name,
        status="success",
        detail={"is_enabled": bool(category.is_enabled), "sort_order": category.sort_order},
        request=request,
    )
    return _category_payload(category)


@forum.put("/admin/posts/{post_id}/status", response_model=schemas.ForumPostDetailResponse)
async def admin_update_post_status(
    post_id: int,
    payload: schemas.ForumPostStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    post = await _get_post_or_404(db, post_id, current_user, include_hidden=True)
    # 治理动作只改状态，不改正文，保留原内容便于审计和后续恢复。
    post.status = payload.status.value
    await db.commit()
    await db.refresh(post)

    author = await db.get(models.User, post.author_id)
    category = await db.get(models.ForumCategory, post.category_id)
    await log_audit_event(
        action="forum.post.moderate",
        actor=current_user,
        resource_type="forum_post",
        resource_id=str(post.id),
        resource_name=post.title,
        status="success",
        detail={"status": payload.status.value},
        request=request,
    )
    return _post_detail_payload(post, author, category, liked_by_me=False)


@forum.put("/admin/comments/{comment_id}/status", response_model=schemas.ForumCommentResponse)
async def admin_update_comment_status(
    comment_id: int,
    payload: schemas.ForumCommentStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    comment = await _get_comment_or_404(db, comment_id, current_user, include_hidden=True)
    comment.status = payload.status.value
    # 评论状态变化会影响帖子 comment_count，所以这里必须同步回刷。
    await _refresh_post_comment_count(db, comment.post_id)
    await db.commit()
    await db.refresh(comment)

    author = await db.get(models.User, comment.author_id)
    await log_audit_event(
        action="forum.comment.moderate",
        actor=current_user,
        resource_type="forum_comment",
        resource_id=str(comment.id),
        resource_name=f"post:{comment.post_id}",
        status="success",
        detail={"status": payload.status.value},
        request=request,
    )
    return _comment_payload(comment, author, liked_by_me=False)
