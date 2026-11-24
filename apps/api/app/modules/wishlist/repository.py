import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wishlist.models import ParticipantPreferences, WishlistItem


class WishlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_items(self, participant_id: uuid.UUID) -> list[WishlistItem]:
        stmt = (
            select(WishlistItem)
            .where(WishlistItem.participant_id == participant_id)
            .order_by(WishlistItem.priority, WishlistItem.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def count_items(self, participant_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(WishlistItem.participant_id == participant_id)
        return int(await self.session.scalar(stmt) or 0)

    async def get_item(self, participant_id: uuid.UUID, item_id: uuid.UUID) -> WishlistItem | None:
        stmt = select(WishlistItem).where(
            WishlistItem.id == item_id, WishlistItem.participant_id == participant_id
        )
        return await self.session.scalar(stmt)

    async def add_item(self, item: WishlistItem) -> WishlistItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete_item(self, item: WishlistItem) -> None:
        await self.session.delete(item)

    async def get_preferences(self, participant_id: uuid.UUID) -> ParticipantPreferences | None:
        return await self.session.get(ParticipantPreferences, participant_id)

    async def add_preferences(self, prefs: ParticipantPreferences) -> None:
        self.session.add(prefs)
        await self.session.flush()
