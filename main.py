import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models
from database import async_engine
from routers import router
from utils.rag_utils.lightrag_engine import lightrag_engine

load_dotenv()


async def _patch_sqlite_schema(conn):
    """
    启动期轻量补丁：给 SQLite 旧库补齐新增列。
    说明：SQLAlchemy 的 create_all 只负责建表，不会为已有表自动补列。
    """
    result = await conn.exec_driver_sql("PRAGMA table_info(chat_messages)")
    columns = {row[1] for row in result.fetchall()}
    if "attachments_json" not in columns:
        await conn.exec_driver_sql("ALTER TABLE chat_messages ADD COLUMN attachments_json TEXT")
        print("✅ 已补齐 chat_messages.attachments_json 列")


async def _migrate_legacy_medical_profiles(conn):
    legacy_table = await conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_medical_profiles'"
    )
    if not legacy_table.fetchone():
        return

    result = await conn.exec_driver_sql(
        """
        SELECT user_id, medical_facts
        FROM user_medical_profiles
        WHERE medical_facts IS NOT NULL AND TRIM(medical_facts) <> ''
        """
    )

    migrated_users = 0
    for user_id, medical_facts in result.fetchall():
        exists_result = await conn.exec_driver_sql(
            """
            SELECT COUNT(1)
            FROM user_medical_profile_records
            WHERE user_id = ? AND source = 'migration'
            """,
            (user_id,),
        )
        if (exists_result.scalar() or 0) > 0:
            continue

        facts = [
            part.strip()
            for part in re.split(r"[；;\n\r]+", str(medical_facts or ""))
            if part and part.strip()
        ]
        if not facts:
            continue

        for fact in facts:
            await conn.exec_driver_sql(
                """
                INSERT INTO user_medical_profile_records
                (user_id, record_type, content, source, created_at, updated_at)
                VALUES (?, 'other', ?, 'migration', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (user_id, fact),
            )
        migrated_users += 1

    if migrated_users:
        print(f"✅ 已迁移 {migrated_users} 个用户的旧病症状况记录")


async def _seed_forum_categories(conn):
    result = await conn.exec_driver_sql("SELECT COUNT(1) FROM forum_categories")
    count = result.scalar() or 0
    if count > 0:
        return

    defaults = [
        ("临床问答", "围绕疾病诊断、治疗方案与随访经验展开讨论", 10),
        ("知识整理", "对知识库内容进行补充、校正与归纳", 20),
        ("案例交流", "结合具体病例或场景分享检索与分析思路", 30),
        ("系统反馈", "讨论平台使用体验、问题反馈与功能建议", 40),
    ]
    for name, description, sort_order in defaults:
        await conn.exec_driver_sql(
            """
            INSERT INTO forum_categories (name, description, sort_order, is_enabled, created_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            """,
            (name, description, sort_order),
        )
    print("✅ 已初始化讨论区默认分类")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        await _patch_sqlite_schema(conn)
        await _migrate_legacy_medical_profiles(conn)
        await _seed_forum_categories(conn)
        print("数据库表检查/创建完成")

    await lightrag_engine.initialize()
    print("✅ LightRAG 初始化完成（Neo4j + Milvus）")

    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import sys
    import uvicorn

    reload_flag = not bool(sys.gettrace())
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload_flag)
