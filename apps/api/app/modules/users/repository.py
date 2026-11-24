import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return await self.session.scalar(stmt)

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        return await self.session.scalar(select(User).where(User.google_sub == google_sub))

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
