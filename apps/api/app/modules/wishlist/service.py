import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.modules.groups.models import GroupStatus
from app.modules.groups.service import GroupAccess, Membership
from app.modules.users.models import User
from app.modules.wishlist.models import ParticipantPreferences, WishlistItem
from app.modules.wishlist.repository import WishlistRepository
from app.modules.wishlist.schemas import (
    PreferencesIn,
    PreferencesOut,
    WishlistItemCreate,
    WishlistItemOut,
    WishlistItemUpdate,
)

MAX_ITEMS = 30


class WishlistService:
    """Cada participante só lê e edita a própria lista (o amigo secreto vê via my-match)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = GroupAccess(session)
        self.repo = WishlistRepository(session)

    async def list_items(self, group_id: uuid.UUID, user: User) -> list[WishlistItemOut]:
        me = await self.access.member(group_id, user)
        return [
            WishlistItemOut.model_validate(i) for i in await self.repo.list_items(me.participant.id)
        ]

    async def add_item(
        self, group_id: uuid.UUID, user: User, data: WishlistItemCreate
    ) -> WishlistItemOut:
        me = await self._editable(group_id, user)
        if await self.repo.count_items(me.participant.id) >= MAX_ITEMS:
            raise ConflictError(
                f"Sua lista pode ter no máximo {MAX_ITEMS} itens.", code="wishlist_full"
            )
        values = data.model_dump()
        values["url"] = str(data.url) if data.url else None
        item = await self.repo.add_item(WishlistItem(participant_id=me.participant.id, **values))
        await self.session.commit()
        return WishlistItemOut.model_validate(item)

    async def update_item(
        self, group_id: uuid.UUID, item_id: uuid.UUID, user: User, data: WishlistItemUpdate
    ) -> WishlistItemOut:
        me = await self._editable(group_id, user)
        item = await self._item(me, item_id)
        changes = data.model_dump(exclude_unset=True)
        for required in ("title", "priority"):
            if required in changes and changes[required] is None:
                raise UnprocessableError("Este campo não pode ficar vazio.", code="field_required")
        if changes.get("url") is not None:
            changes["url"] = str(changes["url"])
        for field, value in changes.items():
            setattr(item, field, value)
        await self.session.commit()
        await self.session.refresh(item)
        return WishlistItemOut.model_validate(item)

    async def delete_item(self, group_id: uuid.UUID, item_id: uuid.UUID, user: User) -> None:
        me = await self._editable(group_id, user)
        await self.repo.delete_item(await self._item(me, item_id))
        await self.session.commit()

    async def get_preferences(self, group_id: uuid.UUID, user: User) -> PreferencesOut:
        me = await self.access.member(group_id, user)
        prefs = await self.repo.get_preferences(me.participant.id)
        return PreferencesOut(
            dislikes=prefs.dislikes if prefs else None, notes=prefs.notes if prefs else None
        )

    async def put_preferences(
        self, group_id: uuid.UUID, user: User, data: PreferencesIn
    ) -> PreferencesOut:
        me = await self._editable(group_id, user)
        prefs = await self.repo.get_preferences(me.participant.id)
        if prefs is None:
            prefs = ParticipantPreferences(participant_id=me.participant.id)
            await self.repo.add_preferences(prefs)
        prefs.dislikes = data.dislikes or None
        prefs.notes = data.notes or None
        await self.session.commit()
        return PreferencesOut(dislikes=prefs.dislikes, notes=prefs.notes)

    async def _editable(self, group_id: uuid.UUID, user: User) -> Membership:
        me = await self.access.member(group_id, user)
        if me.group.status is GroupStatus.FINISHED:
            raise ConflictError(
                "O grupo foi encerrado e está somente leitura.", code="group_finished"
            )
        return me

    async def _item(self, me: Membership, item_id: uuid.UUID) -> WishlistItem:
        item = await self.repo.get_item(me.participant.id, item_id)
        if item is None:
            raise NotFoundError("Item não encontrado.", code="wishlist_item_not_found")
        return item
