from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import verify_csrf
from app.modules.auth.router import router as auth_router
from app.modules.draws.router import router as draws_router
from app.modules.groups.router import router as groups_router
from app.modules.participants.router import router as participants_router
from app.modules.rules.router import router as rules_router
from app.modules.users.router import router as users_router
from app.modules.wishlist.router import router as wishlist_router

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_csrf)])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
api_router.include_router(participants_router)
api_router.include_router(wishlist_router)
api_router.include_router(rules_router)
api_router.include_router(draws_router)
