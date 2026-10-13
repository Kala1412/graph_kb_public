import asyncio
import datetime
import json
import math
import os
import time
from sqlalchemy import select, delete, func
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
import mimetypes
from pydantic import BaseModel, Field
import models
from database import AsyncSessionLocal
from models import KnowledgeBase, KnowledgeFile, FileStatus
from utils.rag_utils.lightrag_engine import lightrag_engine
from utils.llm_client import llm_client
from utils.markdown_processor import process_file_to_markdown, save_markdown_to_minio
from utils.neo4j_service import neo4j_service
from utils.rag_engine_init_test import rag_engine
from utils.auth_midware import get_current_user, is_admin, require_kb_access, require_file_access
from utils.minio_client import minio_handler
from utils.audit_logger import log_audit_event
from pathlib import Path
from typing import Literal, Optional

knowledge = APIRouter(prefix="/knowledge", tags=["知识库相关接口"])

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

class QueryRequest(BaseModel):
    kb_id: int
    query: str
    top_k: int = 3
    mode: Literal["local", "global", "hybrid", "naive"] = "hybrid"
    only_context: bool = True

    enable_rerank: Optional[bool] = None

class ChatRequest(BaseModel):
    kb_id: int
    query: str
    top_k: int = 5

class KBUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="知识库名称")
    description: Optional[str] = Field(None,min_length=1,description="知识库描述")

class GraphQueryRequest(BaseModel):
    kb_id: Optional[int] = Field(None, ge=1)
    # 限制返回edge边数量，防止前端渲染卡死，设置默认值和最大值
    limit: int = Field(100, ge=1, le=2000, description="限制返回的edge边数量")


async def process_document_full_pipeline(
        file_id: int,
        kb_id: int,
        minio_bucket: str,
        minio_object: str,
        original_filename: str,
        processing_params: dict,
        force_reindex: bool = False  # 强制重新索引时先删除旧索引，默认为 False
):
    """
        完整的文档处理流程：
        UPLOADED → PARSING → PARSED → INDEXING → INDEXED
    """
    async with AsyncSessionLocal() as db:
        try:
            # ========== 阶段 1：获取文件记录 更新状态为 PARSING ==========
            print(f"\n📝 [Phase 1/3] 获取文件记录 更新状态为 PARSING...")
            file_record = await db.get(KnowledgeFile, file_id)
            if not file_record:
                print(f"❌ 文件记录 {file_id} 未找到")
                return
            file_record.status = FileStatus.PARSING
            file_record.error_message = None
            await db.commit()


            # ========== 阶段 2：PARSING（解析为 Markdown）==========
            print(f"\n📝 [Phase 2/3] PARSING: 解析为Markdown中...")
            file_extension = Path(original_filename).suffix.lower()
            enable_ocr = processing_params.get("enable_ocr", "disable")

            markdown_text, markdown_assets = await process_file_to_markdown(
                minio_bucket=minio_bucket,
                minio_object=minio_object,
                file_extension=file_extension,
                enable_ocr=enable_ocr
            )
            print(f"✅ Markdown 转换成功 ({len(markdown_text)} 字符)")

            # ========== 阶段 2：PARSED（保存 Markdown）==========
            print(f"\n💾 保存 Markdown 到 MinIO 中...")
            markdown_url,markdown_path = await save_markdown_to_minio(
                markdown_content=markdown_text,
                kb_id=kb_id,
                file_id=file_id,
                original_filename=original_filename,
                assets=markdown_assets
            )
            file_record.status = FileStatus.PARSED
            file_record.markdown_minio_url = markdown_url
            file_record.markdown_minio_path = markdown_path
            await db.commit()
            print(f"✅ Markdown 已保存: {markdown_url}")

            # ========== 阶段 3：INDEXING（LightRAG 索引）==========
            print(f"\n🔍 [Phase 3/3] INDEXING: 文件索引中...")
            file_record.status = FileStatus.INDEXING
            await db.commit()

            await lightrag_engine.insert_document(
                markdown_text=markdown_text,
                file_id=str(file_id),
                kb_id=kb_id,
                force_reindex=force_reindex  # 强制重新索引参数
            )

            # ========== 完成：INDEXED ==========
            file_record.status = FileStatus.INDEXED
            await db.commit()

            print(f"\n🎉 文档 {file_id} 在知识库 {kb_id} 中索引完成!")
            print(f"   - 原始文件 URL: {file_record.minio_url}")
            print(f"   - Markdown URL: {markdown_url}")
            print(f"   - 文件状态: {FileStatus.INDEXED}")

        except Exception as e:
            # 错误处理：根据当前阶段设置不同的错误状态
            print(f"\n❌ 处理错误: {e}")

            if file_record.status in [FileStatus.UPLOADED, FileStatus.PARSING]:
                file_record.status = FileStatus.ERROR_PARSING
            elif file_record.status == FileStatus.INDEXING:
                file_record.status = FileStatus.ERROR_INDEXING

            file_record.error_message = str(e)
            await db.commit()



@knowledge.post("/create")
async def create_kb(
        name: str = Form(...),
        description: str = Form(None),
        current_user =  Depends(get_current_user),
        db: AsyncSessionLocal = Depends(get_db),
        request: Request = None,
):
    try:
        new_kb = KnowledgeBase(name=name, description=description, owner_id=current_user.id)
        db.add(new_kb)
        await db.commit()
        await db.refresh(new_kb)

        await log_audit_event(
            action="kb.create",
            actor=current_user,
            resource_type="kb",
            resource_id=str(new_kb.id),
            resource_name=new_kb.name,
            status="success",
            detail={"description": description},
            request=request,
        )

        return {
            "status": "success",
            "kb_id": new_kb.id,
            "name": new_kb.name,
        }
    except Exception as exc:
        await log_audit_event(
            action="kb.create",
            actor=current_user,
            resource_type="kb",
            resource_id=None,
            resource_name=name,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


async def process_doc_task(file_record_id: int, minio_bucket: str, minio_object: str):
    """
    后台任务：MinIO下载 -> Docling解析 -> LightRAG入库（向量+图谱）
    """
    # 【关键修改1】使用异步 Session 工厂，并且用 async with 管理上下文
    async with AsyncSessionLocal() as db:
        temp_file_path = None
        try:
            print(f"Task started for FileID: {file_record_id}")

            stmt = select(KnowledgeFile).where(KnowledgeFile.id == file_record_id)
            result = await db.execute(stmt)
            db_file = result.scalars().first()

            if not db_file:
                print(f"File record {file_record_id} not found!")
                return

            db_file.status = "parsing"
            await db.commit()

            import tempfile
            suffix = os.path.splitext(minio_object)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                temp_file_path = tmp_file.name

            print(f"📥 Downloading from MinIO: {minio_bucket}/{minio_object}")
            minio_handler.client.fget_object(minio_bucket, minio_object,temp_file_path)

            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()

            print(f"📄 Parsing PDF with Docling: {db_file.filename}")
            result = converter.convert(temp_file_path)
            markdown_text = result.document.export_to_markdown()
            print(f"✅ Markdown generated: {len(markdown_text)} characters")


            db_file.status = "indexing"
            await db.commit()

            await lightrag_engine.insert_document(
                markdown_text=markdown_text,
                file_id=str(db_file.id),
                kb_id=db_file.kb_id
            )

            db_file.status = "success"
            await db.commit()

            print(f"🎉 File {db_file.id} indexed into LightRAG (Neo4j + Milvus)")

        except Exception as e:
            print(f"❌ Error processing file: {e}")
            import traceback
            traceback.print_exc()

            if db_file:
                db_file.status = "failed"
                await db.commit()

        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
@knowledge.delete("/delete/{kb_id}")
async def delete_kb(
        kb_id: int,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user),
        request: Request = None,
):

    kb = await require_kb_access(kb_id, db, current_user)

    try:
        # 2. 清理核心索引数据 (Milvus 向量 + Neo4j 图谱 + 本地缓存)
        await lightrag_engine.delete_knowledge_base(kb_id)

        # 3. 删除 MinIO 中该知识库相关的文件（包括原始文件和 Markdown 文件）
        minio_handler.delete_kb_directory(kb_id)

        # 4. 删除数据库记录（KnowledgeBase 和 KnowledgeFile）
        # 先删除属于该知识库的所有文件记录
        stmt = delete(KnowledgeFile).where(KnowledgeFile.kb_id == kb_id)
        await db.execute(stmt)
        await db.delete(kb)

        await db.commit()

        await log_audit_event(
            action="kb.delete",
            actor=current_user,
            resource_type="kb",
            resource_id=str(kb_id),
            resource_name=kb.name,
            status="success",
            detail={},
            request=request,
        )

        return {
            "status": "success",
            "message": f"知识库:{kb.name} ID: {kb_id} 及其所有关联数据已彻底删除"
        }
    except Exception as e:
        await log_audit_event(
            action="kb.delete",
            actor=current_user,
            resource_type="kb",
            resource_id=str(kb_id),
            resource_name=kb.name if kb else None,
            status="failed",
            detail={"error": str(e)},
            request=request,
        )
        await db.rollback()
        print(f"❌ Delete KB error: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@knowledge.put("/update/{kb_id}")
async def update_knowledge_base(
        kb_id: int,
        update_data: KBUpdate,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user),
        request: Request = None
):
    try:
        kb = await require_kb_access(kb_id, db, current_user)

        # 只允许更新名字，描述等元信息
        updated_fields = []
        if update_data.name:
            kb.name = update_data.name
            updated_fields.append("name")
        if update_data.description:
            kb.description = update_data.description
            updated_fields.append("description")

        await db.commit()
        await db.refresh(kb)

        await log_audit_event(
            action="kb.update",
            actor=current_user,
            resource_type="kb",
            resource_id=str(kb.id),
            resource_name=kb.name,
            status="success",
            detail={"updated_fields": updated_fields},
            request=request,
        )

        return {
            "status": "success",
            "message": f"知识库 {kb.name} 更新接口 - 当前仅支持更新元信息，文件更新请直接上传新文件覆盖"
        }
    except HTTPException as exc:
        await log_audit_event(
            action="kb.update",
            actor=current_user,
            resource_type="kb",
            resource_id=str(kb_id),
            resource_name=None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="kb.update",
            actor=current_user,
            resource_type="kb",
            resource_id=str(kb_id),
            resource_name=None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise



# 上传时按文件 ID 或同名文件判断更新；异名同内容文件尚未做去重。
@knowledge.post("/upload")
async def upload_document(
        background_tasks: BackgroundTasks,
        kb_id: int = Form(...),
        file: UploadFile = File(...),
        enable_ocr: str = Form("disable"),
        # disable: 使用 Docling (默认)
        # deepseek_ocr: 使用 DeepSeek OCR (适合扫描件)
        # mineru: 使用 MinerU API (适合带复杂表格/公式的医疗文献)
        file_id: int | None = Form(None),
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user),
        request: Request = None
):
    kb = None
    target_file_record = None
    force_reindex = False
    mode = "create"
    processing_params = {
        "enable_ocr": enable_ocr,
    }

    try:
        kb = await require_kb_access(kb_id, db, current_user)

        if file_id is not None:
            print(f"🔄 接收到更新请求，目标 file_id={file_id}")

            target_file_record = await db.get(KnowledgeFile, file_id)
            if not target_file_record:
                raise HTTPException(status_code=404, detail=f"指定更新的文件 ID {file_id} 不存在")
            if target_file_record.kb_id != kb_id:
                raise HTTPException(status_code=400, detail="该文件不属于指定的知识库")

            mode = "update"
            force_reindex = True  # 更新必然要强制重索引

            target_file_record.filename = file.filename
            target_file_record.status = FileStatus.UPLOADED
            target_file_record.updated_at = datetime.datetime.utcnow()
            target_file_record.error_message = None
        else:
            # 额外检查：同知识库下是否已有同名文件？（防止误操作）
            stmt = select(KnowledgeFile).where(
                KnowledgeFile.kb_id == kb_id,
                KnowledgeFile.filename == file.filename
            )
            existing_file = (await db.execute(stmt)).scalar_one_or_none()

            if existing_file:
                # 同名上传自动切换为更新模式。
                print(f"⚠️ 发现同名文件 {file.filename} (ID: {existing_file.id})，自动切换为更新模式")
                target_file_record = existing_file
                mode = "overwrite"
                force_reindex = True
                target_file_record.status = FileStatus.UPLOADED
                target_file_record.updated_at = datetime.datetime.utcnow()
            else:
                print(f"🆕 创建新文件记录: {file.filename}")
                mode = "create"
                target_file_record = KnowledgeFile(
                    filename=file.filename,
                    kb_id=kb_id,
                    status=FileStatus.UPLOADED,
                    processing_params=json.dumps(processing_params),
                    minio_url="", minio_path=""
                )
                db.add(target_file_record)
                await db.commit()
                await db.refresh(target_file_record)

        try:
            file_content = await file.read()
            target_file_record.file_size = len(file_content)
            file_extension = Path(file.filename).suffix.lower()

            # 生成带时间戳的文件名（防止重名）
            timestamp = int(time.time() * 1000)
            base_name = Path(file.filename).stem
            minio_filename = f"kb_{kb_id}/original/{base_name}_{timestamp}{file_extension}"
            url = minio_handler.upload_file(
                file_data=file_content,
                file_name=minio_filename,
                content_type=file.content_type or "application/octet-stream"
            )
            target_file_record.minio_url = url
            target_file_record.minio_path = minio_filename
            await db.commit()

        except Exception as e:
            print(f"❌ MinIO Upload Failed: {e}")
            raise HTTPException(status_code=500, detail="文件上传存储失败")

        # 注意：这里我们传递 minio_handler.bucket_name
        background_tasks.add_task(
            process_document_full_pipeline,
            file_id=target_file_record.id,
            kb_id=kb_id,
            minio_bucket=minio_handler.bucket_name,
            minio_object=minio_filename,
            original_filename=file.filename,
            processing_params=processing_params,
            force_reindex=force_reindex,# 如果是更新模式，这里就是 True
        )

        action = "file.upload" if mode == "create" else "file.replace"

        await log_audit_event(
            action=action,
            actor=current_user,
            resource_type="file",
            resource_id=str(target_file_record.id),
            resource_name=file.filename,
            status="success",
            detail={
                "kb_id": kb_id,
                "mode": mode,
                "enable_ocr": enable_ocr,
            },
            request=request,
        )

        return {
            "status":"success",
            "mode": mode,
            "file_id": target_file_record.id,
            "filename": file.filename,
            "current_status": FileStatus.UPLOADED,
            "minio_url": url,
            "processing_params": processing_params,
            "message": f"文件{'更新' if mode != 'create' else '上传'}任务已提交",
        }
    except HTTPException as exc:
        await log_audit_event(
            action="file.upload" if mode == "create" else "file.replace",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id) if file_id else None,
            resource_name=file.filename if file else None,
            status="failed",
            detail={"error": exc.detail, "kb_id": kb_id, "mode": mode},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="file.upload" if mode == "create" else "file.replace",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id) if file_id else None,
            resource_name=file.filename if file else None,
            status="failed",
            detail={"error": str(exc), "kb_id": kb_id, "mode": mode},
            request=request,
        )
        raise

@knowledge.post("/query")
async def query_knowledge_base(
    request: QueryRequest,
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    知识库检索接口（不生成答案，只返回检索结果）

    支持的查询模式：
    - naive: 纯向量检索
    - local: 局部图谱 + 向量
    - global: 全局图谱
    - hybrid: 混合检索（推荐）
    """
    await require_kb_access(request.kb_id, db, current_user)

    try:
        results = await (lightrag_engine.query(
            question=request.query,
            kb_id=request.kb_id,
            mode=request.mode,
            top_k=request.top_k,
            only_context=request.only_context,
            enable_rerank=request.enable_rerank
        ))

        # 兼容结构化返回（手写管线会直接返回 chunks/entities/relationships）
        if isinstance(results, dict):
            results.setdefault("chunks", [])
            results.setdefault("entities", [])
            results.setdefault("relationships", results.get("relations", []))

            if not results.get("context"):
                results["context"] = json.dumps(
                    {
                        "chunks": results["chunks"],
                        "entities": results["entities"],
                        "relationships": results["relationships"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            # 可选：Schema 校验（仅日志提示，不中断）
            allowed_types = None
            entity_types_raw = os.getenv("ENTITY_TYPES")
            if entity_types_raw:
                try:
                    parsed = json.loads(entity_types_raw)
                    if isinstance(parsed, list):
                        allowed_types = set(parsed)
                except Exception:
                    allowed_types = None
            if allowed_types:
                invalid_types = sorted({
                    (e.get("entity_type") or e.get("type"))
                    for e in results["entities"]
                    if (e.get("entity_type") or e.get("type"))
                    and (e.get("entity_type") or e.get("type")) not in allowed_types
                })
                if invalid_types:
                    print(f"⚠️ Schema 检查：发现未在 ENTITY_TYPES 中的实体类型: {invalid_types}")

            if not request.only_context:
                context_texts: list[str] = []
                for chunk in results.get("chunks", []):
                    if not isinstance(chunk, dict):
                        continue
                    content = chunk.get("content") or chunk.get("text") or ""
                    if content:
                        context_texts.append(content)

                if not context_texts and results.get("context"):
                    context_texts = [results["context"]]

                try:
                    answer = await asyncio.to_thread(
                        llm_client.generate_answer,
                        request.query,
                        context_texts,
                    )
                except Exception as exc:
                    print(f"⚠️ LLM 回答生成失败: {exc}")
                    answer = ""

                results["answer"] = answer

        return {
            "status": "success",
            "results": results
        }

    except Exception as e:
        raise HTTPException(500, detail=f"检索失败: {str(e)}")


@knowledge.post("/chat")
async def chat_with_knowledge_base(
        request: ChatRequest,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user)
):
    """RAG 对话接口：使用 LightRAG 混合检索（向量+图谱）"""
    await require_kb_access(request.kb_id, db, current_user)
    print(f"Step 1: Searching KB {request.kb_id} for '{request.query}'...")
    # 注意：这里需要在 thread 中运行，防止阻塞
    chunks = await asyncio.to_thread(
        rag_engine.search,
        request.query,
        request.kb_id,
        request.top_k
    )

    if not chunks:
        return {"answer": "抱歉，知识库中没有找到相关信息。", "sources": []}

    context_texts = [item['content'] for item in chunks]

    print("Step 2: Generating answer with LLM...")
    answer = await asyncio.to_thread(
        llm_client.generate_answer,
        request.query,
        context_texts
    )

    return {
        "status": "success",
        "question": request.query,
        "answer": answer,
        "references": chunks  # 把引用源返回给前端展示，提升可信度
    }

@knowledge.get("/files/{file_id}/status")
async def get_file_status(
    file_id: int,
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    file_record = await require_file_access(file_id, db, current_user)

    processing_params = {}
    if file_record.processing_params:
        try:
            processing_params = json.loads(file_record.processing_params)
        except:
            pass

    return {
        "file_id": file_id,
        "filename": file_record.filename,
        "status": file_record.status,
        "error_message": file_record.error_message,
        "minio_url": file_record.minio_url,
        "markdown_url": file_record.markdown_minio_url,
        "processing_params": processing_params,
        "created_at": file_record.created_at,
        "updated_at": file_record.updated_at
    }


# 获取 Markdown 内容（通过后端代理，避免前端 CORS/直连问题）
@knowledge.get("/files/{file_id}/markdown")
async def get_file_markdown(
    file_id: int,
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    file_record = await require_file_access(file_id, db, current_user)

    if not file_record.markdown_minio_path:
        raise HTTPException(status_code=404, detail="Markdown 尚未生成")

    try:
        obj = minio_handler.client.get_object(
            minio_handler.bucket_name,
            file_record.markdown_minio_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 Markdown 失败: {str(e)}")

    def _stream():
        try:
            for chunk in obj.stream(32 * 1024):
                yield chunk
        finally:
            obj.close()
            obj.release_conn()

    return StreamingResponse(_stream(), media_type="text/markdown; charset=utf-8")


@knowledge.get("/files/{file_id}/assets/{asset_path:path}")
async def get_file_markdown_asset(
    file_id: int,
    asset_path: str,
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    file_record = await require_file_access(file_id, db, current_user)

    if not file_record.markdown_minio_path:
        raise HTTPException(status_code=404, detail="Markdown 尚未生成")

    safe_path = "/".join([p for p in asset_path.replace("\\", "/").split("/") if p not in ("", ".", "..")])
    if not safe_path:
        raise HTTPException(status_code=400, detail="资源路径无效")

    object_name = f"kb_{file_record.kb_id}/markdown/file_{file_id}/assets/{safe_path}"

    try:
        obj = minio_handler.client.get_object(
            minio_handler.bucket_name,
            object_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取资源失败: {str(e)}")

    def _stream():
        try:
            for chunk in obj.stream(32 * 1024):
                yield chunk
        finally:
            obj.close()
            obj.release_conn()

    media_type, _ = mimetypes.guess_type(object_name)
    return StreamingResponse(_stream(), media_type=media_type or "application/octet-stream")


@knowledge.post("/files/{file_id}/retry")
async def retry_file_processing(
        file_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user),
        request: Request = None
):
    """重新处理失败的文件"""
    file_record = None
    try:
        file_record = await require_file_access(file_id, db, current_user)

        # 只允许重试失败的文件
        if file_record.status not in [FileStatus.ERROR_PARSING, FileStatus.ERROR_INDEXING]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry file with status: {file_record.status}"
            )

        file_record.status = FileStatus.UPLOADED
        file_record.error_message = None
        await db.commit()

        processing_params = {}
        if file_record.processing_params:
            try:
                processing_params = json.loads(file_record.processing_params)
            except:
                pass

        background_tasks.add_task(
            process_document_full_pipeline,
            file_id=file_record.id,
            kb_id=file_record.kb_id,
            minio_bucket=minio_handler.bucket_name,
            minio_object=file_record.minio_path,
            original_filename=file_record.filename,
            processing_params=processing_params,
            force_reindex=True,
        )

        await log_audit_event(
            action="file.retry",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename if file_record else None,
            status="success",
            detail={"kb_id": file_record.kb_id if file_record else None},
            request=request,
        )

        return {
            "status": "success",
            "message": "File reprocessing started",
            "file_id": file_id
        }
    except HTTPException as exc:
        await log_audit_event(
            action="file.retry",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename if file_record else None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="file.retry",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename if file_record else None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise

@knowledge.get("/list")
async def list_kbs(
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    user_is_admin = is_admin(current_user)
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.description,
            KnowledgeBase.owner_id,
            models.User.username.label("owner_name"),
            func.count(KnowledgeFile.id).label("file_count"),
        )
        .outerjoin(KnowledgeFile, KnowledgeFile.kb_id == KnowledgeBase.id)
        .outerjoin(models.User, models.User.id == KnowledgeBase.owner_id)
        .group_by(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.description,
            KnowledgeBase.owner_id,
            models.User.username,
        )
        .order_by(KnowledgeBase.id.desc())
    )
    # 用户权限检查
    if not user_is_admin:
        stmt = stmt.where(KnowledgeBase.owner_id == current_user.id)

    res = await db.execute(stmt)
    items = res.all()
    result = []
    for kb in items:
        item = {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "file_count": int(kb.file_count or 0),
        }

        # 仅管理员返回创建者信息，避免普通用户看到不必要字段
        if user_is_admin:
            item["creator"] = {
                "id": kb.owner_id,
                "username": kb.owner_name,
            }
            # 兼容旧前端字段
            item["owner_id"] = kb.owner_id
            item["owner_name"] = kb.owner_name

        result.append(item)
    return result


@knowledge.get("/{kb_id}")
async def get_kb_detail(
        kb_id: int,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user)
):
    user_is_admin = is_admin(current_user)
    kb = await require_kb_access(kb_id, db, current_user)

    # 使用显式查询统计该知识库下的文件数量（异步友好）
    res = await db.execute(select(func.count()).select_from(KnowledgeFile).where(KnowledgeFile.kb_id == kb_id))
    file_count = res.scalar_one() or 0

    result = {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "created_at": kb.created_at,
        "file_count": int(file_count)
    }

    # 仅管理员返回创建者信息
    if user_is_admin:
        owner_user = await db.get(models.User, kb.owner_id)
        result["creator"] = {
            "id": kb.owner_id,
            "username": owner_user.username if owner_user else None,
        }
        # 兼容旧字段（后续可移除）
        result["owner_id"] = kb.owner_id
        result["owner_name"] = owner_user.username if owner_user else None

    return result


@knowledge.get("/{kb_id}/files")
async def get_kb_files(
        kb_id: int,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user)
):
    from sqlalchemy import select

    await require_kb_access(kb_id, db, current_user)

    result = await db.execute(
        select(KnowledgeFile).where(KnowledgeFile.kb_id == kb_id).order_by(KnowledgeFile.created_at.desc())
    )
    files = result.scalars().all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "file_size": f.file_size,
            "status": f.status,
            "error_message": f.error_message,
            "created_at": f.created_at,
            "updated_at": f.updated_at,
            "kb_id": f.kb_id
        }
        for f in files
    ]


@knowledge.delete("/files/{file_id}")
async def delete_kb_file(
        file_id: int,
        db: AsyncSessionLocal = Depends(get_db),
        current_user = Depends(get_current_user),
        request: Request = None
):
    file_record = None
    try:
        file_record = await require_file_access(file_id, db, current_user)

        try:
            await lightrag_engine.delete_document(file_id, file_record.kb_id)
        except Exception as e:
            print(f"Warning: Failed to delete vector/graph data: {e}")

        await db.delete(file_record)
        await db.commit()

        await log_audit_event(
            action="file.delete",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename,
            status="success",
            detail={"kb_id": file_record.kb_id},
            request=request,
        )

        return {"status": "success", "message": "文件已删除"}
    except HTTPException as exc:
        await log_audit_event(
            action="file.delete",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename if file_record else None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="file.delete",
            actor=current_user,
            resource_type="file",
            resource_id=str(file_id),
            resource_name=file_record.filename if file_record else None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@knowledge.post("/queryGraph")
async def get_kb_graph(
    params: GraphQueryRequest,
    db: AsyncSessionLocal = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取知识库对应的图谱可视化数据
    """
    try:
        #情况1：传参有kb_id，直接尝试查询
        if params.kb_id:
            await require_kb_access(params.kb_id, db, current_user)
            graph_data = neo4j_service.get_subgraph(params.kb_id, limit=params.limit)
            return {"status": "success", "data": graph_data}

        # 管理员未指定 kb_id 时查询全部图谱。
        if is_admin(current_user):
            graph_data = neo4j_service.get_subgraph(None, limit=params.limit)
            return {"status": "success", "data": graph_data}

        # 普通用户未指定 kb_id 时仅合并本人的知识库图谱。
        res = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.owner_id == current_user.id)
        )
        kb_ids = res.scalars().all()
        if not kb_ids:
            return {"status": "success", "data": {"nodes": [], "edges": []}}

        limit_per_kb = max(1, math.ceil(params.limit / len(kb_ids)))
        nodes_map = {}
        edges_map = {}
        for kb_id in kb_ids:
            subgraph = neo4j_service.get_subgraph(kb_id, limit=limit_per_kb)
            for node in subgraph.get("nodes", []):
                nodes_map[str(node.get("id"))] = node
            for edge in subgraph.get("edges", []):
                edges_map[str(edge.get("id"))] = edge

        merged = {"nodes": list(nodes_map.values()), "edges": list(edges_map.values())}
        if len(merged["edges"]) > params.limit:
            merged["edges"] = merged["edges"][: params.limit]
        return {"status": "success", "data": merged}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图谱失败: {str(e)}")
