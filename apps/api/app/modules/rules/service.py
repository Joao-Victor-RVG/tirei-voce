import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.modules.groups.service import GroupAccess, Membership, ensure_not_frozen
from app.modules.participants.models import Participant
from app.modules.participants.repository import ParticipantRepository
from app.modules.rules.models import BlockedPair, ExclusionCircle, ExclusionCircleMember
from app.modules.rules.repository import RulesRepository
from app.modules.rules.schemas import (
    BlockedPairCreate,
    BlockedPairOut,
    BlockedPairUpdate,
    CircleCreate,
    CircleMemberOut,
    CircleOut,
    CircleUpdate,
    PairPerson,
)
from app.modules.users.models import User


class RulesService:
    """Restrições do sorteio. Só o organizador vê e edita; congeladas após o sorteio."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = GroupAccess(session)
        self.participants = ParticipantRepository(session)
        self.repo = RulesRepository(session)

    # --- Círculos ---

    async def list_circles(self, group_id: uuid.UUID, user: User) -> list[CircleOut]:
        await self.access.organizer(group_id, user)
        people = await self._people(group_id)
        return [self._circle_out(c, people) for c in await self.repo.list_circles(group_id)]

    async def create_circle(self, group_id: uuid.UUID, user: User, data: CircleCreate) -> CircleOut:
        await self._editable(group_id, user)
        people = await self._people(group_id)
        member_ids = self._validate_members(data.participant_ids, people)
        circle = ExclusionCircle(
            group_id=group_id,
            name=data.name,
            members=[ExclusionCircleMember(participant_id=pid) for pid in member_ids],
        )
        await self.repo.add(circle)
        await self.session.commit()
        return await self._reload_circle(group_id, circle.id, people)

    async def update_circle(
        self, group_id: uuid.UUID, circle_id: uuid.UUID, user: User, data: CircleUpdate
    ) -> CircleOut:
        await self._editable(group_id, user)
        circle = await self._circle(group_id, circle_id)
        people = await self._people(group_id)
        if data.name is not None:
            circle.name = data.name
        if data.participant_ids is not None:
            member_ids = self._validate_members(data.participant_ids, people)
            circle.members = [ExclusionCircleMember(participant_id=pid) for pid in member_ids]
        await self.session.commit()
        return await self._reload_circle(group_id, circle.id, people)

    async def delete_circle(self, group_id: uuid.UUID, circle_id: uuid.UUID, user: User) -> None:
        await self._editable(group_id, user)
        await self.repo.delete(await self._circle(group_id, circle_id))
        await self.session.commit()

    async def add_circle_member(
        self, group_id: uuid.UUID, circle_id: uuid.UUID, participant_id: uuid.UUID, user: User
    ) -> CircleOut:
        await self._editable(group_id, user)
        circle = await self._circle(group_id, circle_id)
        people = await self._people(group_id)
        self._validate_members([participant_id], people, min_size=1)
        if all(m.participant_id != participant_id for m in circle.members):
            circle.members.append(ExclusionCircleMember(participant_id=participant_id))
            await self.session.commit()
        return await self._reload_circle(group_id, circle.id, people)

    async def remove_circle_member(
        self, group_id: uuid.UUID, circle_id: uuid.UUID, participant_id: uuid.UUID, user: User
    ) -> CircleOut:
        await self._editable(group_id, user)
        circle = await self._circle(group_id, circle_id)
        member = next((m for m in circle.members if m.participant_id == participant_id), None)
        if member is None:
            raise NotFoundError("Esta pessoa não está no círculo.", code="circle_member_not_found")
        if len(circle.members) <= 2:
            raise UnprocessableError(
                "Um círculo precisa de pelo menos 2 pessoas. "
                "Exclua o círculo se não precisar mais dele.",
                code="circle_too_small",
            )
        circle.members.remove(member)
        await self.session.commit()
        return await self._reload_circle(group_id, circle.id, await self._people(group_id))

    # --- Pares bloqueados ---

    async def list_pairs(self, group_id: uuid.UUID, user: User) -> list[BlockedPairOut]:
        await self.access.organizer(group_id, user)
        people = await self._people(group_id)
        return [self._pair_out(p, people) for p in await self.repo.list_pairs(group_id)]

    async def create_pair(
        self, group_id: uuid.UUID, user: User, data: BlockedPairCreate
    ) -> BlockedPairOut:
        await self._editable(group_id, user)
        people = await self._people(group_id)
        giver, receiver = data.giver_participant_id, data.receiver_participant_id
        if giver == receiver:
            raise UnprocessableError(
                "Escolha duas pessoas diferentes.", code="invalid_blocked_pair"
            )
        self._validate_members([giver, receiver], people, min_size=2)
        if await self.repo.find_pair(group_id, giver, receiver):
            raise ConflictError("Este par já está bloqueado.", code="blocked_pair_exists")
        pair = BlockedPair(
            group_id=group_id,
            giver_participant_id=giver,
            receiver_participant_id=receiver,
            bidirectional=data.bidirectional,
        )
        await self.repo.add(pair)
        await self.session.commit()
        return self._pair_out(pair, people)

    async def update_pair(
        self, group_id: uuid.UUID, pair_id: uuid.UUID, user: User, data: BlockedPairUpdate
    ) -> BlockedPairOut:
        await self._editable(group_id, user)
        pair = await self._pair(group_id, pair_id)
        pair.bidirectional = data.bidirectional
        await self.session.commit()
        return self._pair_out(pair, await self._people(group_id))

    async def delete_pair(self, group_id: uuid.UUID, pair_id: uuid.UUID, user: User) -> None:
        await self._editable(group_id, user)
        await self.repo.delete(await self._pair(group_id, pair_id))
        await self.session.commit()

    # --- Internos ---

    async def _editable(self, group_id: uuid.UUID, user: User) -> Membership:
        membership = await self.access.organizer(group_id, user, for_update=True)
        ensure_not_frozen(membership.group)
        return membership

    async def _people(self, group_id: uuid.UUID) -> dict[uuid.UUID, Participant]:
        return {p.id: p for p in await self.participants.list_active(group_id)}

    @staticmethod
    def _validate_members(
        ids: Iterable[uuid.UUID], people: dict[uuid.UUID, Participant], *, min_size: int = 2
    ) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(ids))
        if any(pid not in people for pid in unique):
            raise UnprocessableError(
                "Alguma das pessoas escolhidas não participa do grupo.", code="invalid_participant"
            )
        if len(unique) < min_size:
            raise UnprocessableError(
                "Um círculo precisa de pelo menos 2 pessoas.", code="circle_too_small"
            )
        return unique

    async def _circle(self, group_id: uuid.UUID, circle_id: uuid.UUID) -> ExclusionCircle:
        circle = await self.repo.get_circle(group_id, circle_id)
        if circle is None:
            raise NotFoundError("Círculo não encontrado.", code="circle_not_found")
        return circle

    async def _pair(self, group_id: uuid.UUID, pair_id: uuid.UUID) -> BlockedPair:
        pair = await self.repo.get_pair(group_id, pair_id)
        if pair is None:
            raise NotFoundError("Par bloqueado não encontrado.", code="blocked_pair_not_found")
        return pair

    async def _reload_circle(
        self, group_id: uuid.UUID, circle_id: uuid.UUID, people: dict[uuid.UUID, Participant]
    ) -> CircleOut:
        return self._circle_out(await self._circle(group_id, circle_id), people)

    @staticmethod
    def _circle_out(circle: ExclusionCircle, people: dict[uuid.UUID, Participant]) -> CircleOut:
        return CircleOut(
            id=circle.id,
            name=circle.name,
            members=[
                CircleMemberOut(
                    participant_id=m.participant_id, name=people[m.participant_id].user.name
                )
                for m in circle.members
                if m.participant_id in people
            ],
        )

    @staticmethod
    def _pair_out(pair: BlockedPair, people: dict[uuid.UUID, Participant]) -> BlockedPairOut:
        def person(pid: uuid.UUID) -> PairPerson:
            p = people.get(pid)
            return PairPerson(participant_id=pid, name=p.user.name if p else "—")

        return BlockedPairOut(
            id=pair.id,
            giver=person(pair.giver_participant_id),
            receiver=person(pair.receiver_participant_id),
            bidirectional=pair.bidirectional,
        )
