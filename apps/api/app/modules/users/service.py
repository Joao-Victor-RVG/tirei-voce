from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnprocessableError
from app.modules.users.models import User
from app.modules.users.schemas import MeUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_me(self, user: User, data: MeUpdate) -> User:
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is None:
            raise UnprocessableError("O nome não pode ficar vazio.", code="name_required")
        for field, value in changes.items():
            setattr(user, field, str(value) if field == "avatar_url" and value else value)
        await self.session.commit()
        await self.session.refresh(user)
        return user
