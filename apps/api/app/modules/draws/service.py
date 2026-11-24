import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnprocessableError
from app.core.ids import uuid7
from app.core.redis import get_redis
from app.modules.draws import crypto, engine
from app.modules.draws.models import Draw, DrawAssignment
from app.modules.draws.repository import DrawRepository
from app.modules.draws.schemas import (
    ConstrainedParticipant,
    DrawOut,
    DrawValidationOut,
    GiftProgressOut,
    GiftStatusOut,
    MyMatchOut,
)
from app.modules.groups.models import Group, GroupStatus
from app.modules.groups.service import GroupAccess, Membership, ensure_transition, transition
from app.modules.participants.models import Participant
from app.modules.participants.repository import ParticipantRepository
from app.modules.rules.repository import RulesRepository
from app.modules.users.models import User
from app.modules.wishlist.repository import WishlistRepository
from app.modules.wishlist.schemas import PreferencesOut, WishlistItemOut

# Atenção: nada neste módulo pode logar ou devolver pares de outras pessoas.
logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL_SECONDS = 24 * 3600
IMPOSSIBLE_MESSAGE = (
    "Com as restrições atuais não existe sorteio possível. Revise os círculos/pares bloqueados."
)


class DrawService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = GroupAccess(session)
        self.participants = ParticipantRepository(session)
        self.rules = RulesRepository(session)
        self.draws = DrawRepository(session)
        self.wishlist = WishlistRepository(session)

    async def validate(self, group_id: uuid.UUID, user: User) -> DrawValidationOut:
        membership = await self.access.organizer(group_id, user)
        people, rules = await self._rules(membership.group)
        feasibility = engine.check_feasibility(rules)
        count = len(people)
        if count < engine.MIN_PARTICIPANTS:
            message = f"São necessárias pelo menos {engine.MIN_PARTICIPANTS} pessoas para sortear."
        elif feasibility.possible:
            message = "Tudo certo! O sorteio é possível com as regras atuais."
        else:
            message = IMPOSSIBLE_MESSAGE
        return DrawValidationOut(
            possible=feasibility.possible,
            participant_count=count,
            min_participants=engine.MIN_PARTICIPANTS,
            message=message,
            most_constrained=self._constrained(feasibility.most_constrained, people),
        )

    async def execute(
        self, group_id: uuid.UUID, user: User, idempotency_key: str | None
    ) -> DrawOut:
        idem_key = self._idempotency_redis_key(group_id, user, idempotency_key)
        if idem_key and (cached := await get_redis().get(idem_key)):
            return DrawOut.model_validate_json(cached)

        # Trava a linha do grupo: dois "Sortear" simultâneos não geram dois sorteios.
        membership = await self.access.organizer(group_id, user, for_update=True)
        group = membership.group
        if group.status in (GroupStatus.DRAWN, GroupStatus.FINISHED):
            if idem_key and (cached := await get_redis().get(idem_key)):
                return DrawOut.model_validate_json(cached)
            raise ConflictError("O sorteio deste grupo já foi feito.", code="already_drawn")
        ensure_transition(group, GroupStatus.DRAWN)

        people, rules = await self._rules(group)
        try:
            assignment = engine.draw(rules, prefer_single_cycle=group.prefer_single_cycle)
        except engine.NotEnoughParticipantsError as exc:
            raise UnprocessableError(
                f"São necessárias pelo menos {engine.MIN_PARTICIPANTS} pessoas para sortear.",
                code="not_enough_participants",
            ) from exc
        except engine.ImpossibleDrawError as exc:
            raise UnprocessableError(
                IMPOSSIBLE_MESSAGE,
                code="draw_impossible",
                details={
                    "most_constrained": [
                        c.model_dump(mode="json")
                        for c in self._constrained(exc.most_constrained, people)
                    ]
                },
            ) from exc

        draw_id = uuid7()
        draw = Draw(
            id=draw_id,
            group_id=group.id,
            version=await self.draws.next_version(group.id),
            executed_by=user.id,
            executed_at=datetime.now(UTC),
            seed_hash=crypto.assignment_digest(draw_id, assignment),
        )
        assignments = [
            DrawAssignment(
                draw_id=draw_id,
                giver_participant_id=giver,
                receiver_encrypted=crypto.encrypt_receiver(receiver),
                receiver_lookup_hash=crypto.receiver_lookup_hash(draw_id, receiver),
            )
            for giver, receiver in assignment.items()
        ]
        await self.draws.add(draw, assignments)
        transition(group, GroupStatus.DRAWN)
        await self.session.commit()

        result = DrawOut(
            draw_id=draw.id,
            version=draw.version,
            executed_at=draw.executed_at,
            participant_count=len(people),
        )
        if idem_key:
            await get_redis().set(idem_key, result.model_dump_json(), ex=IDEMPOTENCY_TTL_SECONDS)
        logger.info(
            "draw_executed",
            extra={"group_id": str(group.id), "version": draw.version, "size": len(people)},
        )
        return result

    async def my_match(self, group_id: uuid.UUID, user: User) -> MyMatchOut:
        _membership, mine = await self._my_assignment(group_id, user)
        receiver_id = crypto.decrypt_receiver(mine.receiver_encrypted)
        receiver = await self.participants.get_by_id(receiver_id)
        if receiver is None:  # pragma: no cover - FK garante a existência
            raise ConflictError(
                "Não foi possível carregar seu amigo secreto.", code="match_missing"
            )
        items = await self.wishlist.list_items(receiver.id)
        prefs = await self.wishlist.get_preferences(receiver.id)
        return MyMatchOut(
            participant_id=receiver.id,
            name=receiver.user.name,
            avatar_url=receiver.user.avatar_url,
            shirt_size=receiver.user.shirt_size,
            shoe_size=receiver.user.shoe_size,
            wishlist=[WishlistItemOut.model_validate(i) for i in items],
            preferences=PreferencesOut(
                dislikes=prefs.dislikes if prefs else None, notes=prefs.notes if prefs else None
            ),
            gift_purchased=mine.gift_purchased_at is not None,
        )

    async def set_gift_purchased(
        self, group_id: uuid.UUID, user: User, purchased: bool
    ) -> GiftStatusOut:
        membership, mine = await self._my_assignment(group_id, user)
        if membership.group.status is GroupStatus.FINISHED:
            raise ConflictError(
                "O grupo foi encerrado e está somente leitura.", code="group_finished"
            )
        if purchased and mine.gift_purchased_at is None:
            mine.gift_purchased_at = datetime.now(UTC)
        elif not purchased:
            mine.gift_purchased_at = None
        await self.session.commit()
        return GiftStatusOut(purchased=mine.gift_purchased_at is not None)

    async def gift_progress(self, group_id: uuid.UUID, user: User) -> GiftProgressOut:
        membership = await self.access.organizer(group_id, user)
        if membership.group.status not in (GroupStatus.DRAWN, GroupStatus.FINISHED):
            raise ConflictError("O sorteio ainda não foi feito.", code="draw_not_done")
        draw = await self.draws.latest(group_id)
        purchased, total = await self.draws.gift_progress(draw.id) if draw else (0, 0)
        return GiftProgressOut(purchased=purchased, total=total)

    async def _my_assignment(
        self, group_id: uuid.UUID, user: User
    ) -> tuple[Membership, DrawAssignment]:
        membership = await self.access.member(group_id, user)
        if membership.group.status not in (GroupStatus.DRAWN, GroupStatus.FINISHED):
            raise ConflictError("O sorteio ainda não foi feito.", code="draw_not_done")
        draw = await self.draws.latest(group_id)
        mine = (
            await self.draws.assignment_for_giver(draw.id, membership.participant.id)
            if draw
            else None
        )
        if mine is None:
            raise ConflictError("Você não participou deste sorteio.", code="not_in_draw")
        return membership, mine

    async def _rules(
        self, group: Group
    ) -> tuple[dict[uuid.UUID, Participant], engine.DrawRules[uuid.UUID]]:
        people = {p.id: p for p in await self.participants.list_active(group.id)}
        circles = await self.rules.list_circles(group.id)
        pairs = await self.rules.list_pairs(group.id)
        rules = engine.DrawRules(
            participants=list(people),
            circles=[[m.participant_id for m in c.members] for c in circles],
            blocked_pairs=[
                engine.BlockedPair(
                    p.giver_participant_id, p.receiver_participant_id, p.bidirectional
                )
                for p in pairs
            ],
        )
        return people, rules

    @staticmethod
    def _constrained(
        items: list[tuple[uuid.UUID, int]], people: dict[uuid.UUID, Participant]
    ) -> list[ConstrainedParticipant]:
        return [
            ConstrainedParticipant(participant_id=pid, name=people[pid].user.name, options=n)
            for pid, n in items
        ]

    @staticmethod
    def _idempotency_redis_key(group_id: uuid.UUID, user: User, key: str | None) -> str | None:
        if not key:
            return None
        digest = hashlib.sha256(key.encode()).hexdigest()
        return f"idem:draw:{group_id}:{user.id}:{digest}"
