import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import EmailToken, EmailTokenPurpose, RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, token: RefreshToken) -> None:
        self.session.add(token)
        await self.session.flush()

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        return await self.session.scalar(stmt)

    async def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )


class EmailTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, token: EmailToken) -> None:
        self.session.add(token)
        await self.session.flush()

    async def get_by_hash_for_update(
        self, token_hash: str, purpose: EmailTokenPurpose
    ) -> EmailToken | None:
        stmt = (
            select(EmailToken)
            .where(EmailToken.token_hash == token_hash, EmailToken.purpose == purpose)
            .with_for_update()
        )
        return await self.session.scalar(stmt)

    async def invalidate_pending(
        self, user_id: uuid.UUID, purpose: EmailTokenPurpose, now: datetime
    ) -> None:
        await self.session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user_id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
