import os.path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(BASE_DIR)
DB_DIR = os.path.join(BASE_DIR,'saves')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)
    print(f"已创建数据库目录: {DB_DIR}")
DB_PATH = os.path.join(DB_DIR,'database.db')

SQL_DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


async_engine = create_async_engine(SQL_DATABASE_URL, connect_args={"check_same_thread": False}, )


AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
