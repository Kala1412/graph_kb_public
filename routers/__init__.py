from fastapi import APIRouter

from database import AsyncSessionLocal
from routers.agent import agent_router
from routers.audit import audit
from routers.auth import auth
from routers.dashboard import dashboard
from routers.forum import forum
from routers.knowledge import knowledge
from routers.medical_profiles import medical_profiles
from routers.users import users

router = APIRouter()
router.include_router(users)
router.include_router(auth)
router.include_router(knowledge)
router.include_router(forum)
router.include_router(medical_profiles)
router.include_router(agent_router)
router.include_router(dashboard)
router.include_router(audit)


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
