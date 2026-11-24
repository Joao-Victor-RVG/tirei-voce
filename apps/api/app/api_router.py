from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import verify_csrf
from app.modules.auth.router import router as auth_router
from app.modules.groups.router import router as groups_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_csrf)])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
