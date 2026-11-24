import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.core.pagination import Page, PageParams
from app.modules.groups.models import Group, GroupStatus, GroupTheme
from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import (
    GroupCreate,
    GroupOut,
    GroupSummaryOut,
    GroupUpdate,
    InvitePreviewOut,
    JoinOut,
    ThemeOut,
    UserBrief,
)
from app.modules.participants.models import Participant, ParticipantRole
from app.modules.participants.repository import ParticipantRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[GroupStatus, frozenset[GroupStatus]] = {
    GroupStatus.DRAFT: frozenset({GroupStatus.OPEN}),
    GroupStatus.OPEN: frozenset({GroupStatus.CLOSED, GroupStatus.DRAWN}),
    GroupStatus.CLOSED: frozenset({GroupStatus.OPEN, GroupStatus.DRAWN}),
    GroupStatus.DRAWN: frozenset({GroupStatus.FINISHED}),
    GroupStatus.FINISHED: frozenset(),
}

_TRANSITION_ERRORS = {
    GroupStatus.OPEN: "Só é possível abrir inscrições de um grupo em rascunho ou fechado.",
    GroupStatus.CLOSED: "Só é possível fechar inscrições de um grupo com inscrições abertas.",
    GroupStatus.DRAWN: "O sorteio só pode ser feito com o grupo aberto ou fechado.",
    GroupStatus.FINISHED: "Só é possível encerrar um grupo depois do sorteio.",
}

# Campos que congelam depois do sorteio (afetam regras/participantes).
_FROZEN_AFTER_DRAW = {"max_participants", "prefer_single_cycle", "draw_scheduled_at"}

INVITE_CODE_BYTES = 9  # token_urlsafe(9) -> 12 caracteres


def generate_invite_code() -> str:
    return secrets.token_urlsafe(INVITE_CODE_BYTES)


def ensure_transition(group: Group, target: GroupStatus) -> None:
    """Único ponto que valida mudanças de status do grupo."""
    if target not in ALLOWED_TRANSITIONS[group.status]:
        raise ConflictError(_TRANSITION_ERRORS[target], code="invalid_status_transition")


def transition(group: Group, target: GroupStatus) -> None:
    ensure_transition(group, target)
    group.status = target


def ensure_not_frozen(group: Group) -> None:
    if group.status in (GroupStatus.DRAWN, GroupStatus.FINISHED):
        raise ConflictError(
            "O sorteio já foi feito: participantes e regras não podem mais ser alterados.",
            code="group_frozen",
        )


@dataclass(frozen=True)
class Membership:
    group: Group
    participant: Participant

    def require_organizer(self) -> None:
        if not self.participant.is_organizer:
            raise ForbiddenError("Só a organização pode fazer isso.", code="organizer_only")

    def require_owner(self) -> None:
        if not self.participant.is_owner:
            raise ForbiddenError("Só quem criou o grupo pode fazer isso.", code="owner_only")


class GroupNotFoundError(NotFoundError):
    code = "group_not_found"
    message = "Grupo não encontrado."


class GroupAccess:
    """Autorização por grupo: quem não participa recebe 404 (não revela que o grupo existe)."""

    def __init__(self, session: AsyncSession) -> None:
        self.groups = GroupRepository(session)
        self.participants = ParticipantRepository(session)

    async def member(
        self, group_id: uuid.UUID, user: User, *, for_update: bool = False
    ) -> Membership:
        group = await self.groups.get(group_id, for_update=for_update)
        if group is None:
            raise GroupNotFoundError()
        participant = await self.participants.get_by_user(group.id, user.id)
        if participant is None or not participant.is_active:
            raise GroupNotFoundError()
        return Membership(group, participant)

    async def organizer(
        self, group_id: uuid.UUID, user: User, *, for_update: bool = False
    ) -> Membership:
        membership = await self.member(group_id, user, for_update=for_update)
        membership.require_organizer()
        return membership

    async def owner(
        self, group_id: uuid.UUID, user: User, *, for_update: bool = False
    ) -> Membership:
        membership = await self.member(group_id, user, for_update=for_update)
        membership.require_owner()
        return membership


class GroupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.groups = GroupRepository(session)
        self.participants = ParticipantRepository(session)
        self.access = GroupAccess(session)

    async def list_themes(self) -> list[ThemeOut]:
        return [ThemeOut.model_validate(t) for t in await self.groups.list_themes()]

    async def create(self, data: GroupCreate, owner: User) -> GroupOut:
        theme = await self._theme(data.theme_slug)
        self._validate_event_dates(data, previous=None)
        values = data.model_dump(exclude={"theme_slug"}, exclude_none=True)
        if "event_maps_url" in values:
            values["event_maps_url"] = str(values["event_maps_url"])
        group = Group(
            **values,
            owner_id=owner.id,
            theme_id=theme.id,
            status=GroupStatus.DRAFT,
            invite_code=await self._unique_invite_code(),
        )
        await self.groups.add(group)
        await self.participants.add(
            Participant(group_id=group.id, user_id=owner.id, role=ParticipantRole.OWNER)
        )
        await self.session.commit()
        logger.info("group_created", extra={"group_id": str(group.id)})
        return await self.get(group.id, owner)

    async def list_mine(self, user: User, page: PageParams) -> Page[GroupSummaryOut]:
        rows = await self.groups.list_for_user(user.id, cursor=page.cursor, limit=page.limit + 1)
        items = [
            GroupSummaryOut(
                id=group.id,
                title=group.title,
                display_name=group.display_name,
                theme=ThemeOut.model_validate(group.theme),
                event_at=group.event_at,
                status=group.status,
                my_role=role,
                participant_count=count,
            )
            for group, role, count in rows[: page.limit]
        ]
        next_cursor = str(items[-1].id) if len(rows) > page.limit else None
        return Page(items=items, next_cursor=next_cursor)

    async def get(self, group_id: uuid.UUID, user: User) -> GroupOut:
        membership = await self.access.member(group_id, user)
        return await self._to_out(membership)

    async def update(self, group_id: uuid.UUID, user: User, data: GroupUpdate) -> GroupOut:
        membership = await self.access.organizer(group_id, user, for_update=True)
        group = membership.group
        changes = data.model_dump(exclude_unset=True)
        if group.status is GroupStatus.FINISHED:
            raise ConflictError(
                "O grupo foi encerrado e está somente leitura.", code="group_finished"
            )
        if group.status is GroupStatus.DRAWN and _FROZEN_AFTER_DRAW & changes.keys():
            ensure_not_frozen(group)
        for required in ("title", "theme_slug", "max_participants", "prefer_single_cycle"):
            if required in changes and changes[required] is None:
                raise UnprocessableError("Este campo não pode ficar vazio.", code="field_required")

        self._validate_event_dates(data, previous=group)
        if "theme_slug" in changes:
            group.theme = await self._theme(changes.pop("theme_slug"))
        if changes.get("event_maps_url") is not None:
            changes["event_maps_url"] = str(changes["event_maps_url"])
        if "max_participants" in changes:
            active = await self.participants.count_active(group.id)
            if changes["max_participants"] < active:
                raise ConflictError(
                    f"O grupo já tem {active} participantes.", code="max_participants_too_low"
                )
        for field, value in changes.items():
            setattr(group, field, value)
        self._validate_ranges(group)
        await self.session.commit()
        return await self.get(group.id, user)

    async def change_status(self, group_id: uuid.UUID, user: User, target: GroupStatus) -> GroupOut:
        if target is GroupStatus.DRAWN:  # só o sorteio leva a DRAWN
            raise ConflictError(_TRANSITION_ERRORS[target], code="invalid_status_transition")
        membership = await self.access.organizer(group_id, user, for_update=True)
        transition(membership.group, target)
        await self.session.commit()
        logger.info("group_status_changed", extra={"group_id": str(group_id), "to": target})
        return await self.get(group_id, user)

    async def regenerate_invite_code(self, group_id: uuid.UUID, user: User) -> GroupOut:
        membership = await self.access.organizer(group_id, user, for_update=True)
        if membership.group.status is GroupStatus.FINISHED:
            raise ConflictError("O grupo foi encerrado.", code="group_finished")
        membership.group.invite_code = await self._unique_invite_code()
        await self.session.commit()
        return await self.get(group_id, user)

    # --- Convites ---

    async def invite_preview(self, code: str) -> InvitePreviewOut:
        group = await self._group_by_code(code)
        count = await self.participants.count_active(group.id)
        reason = self._join_blocker(group, count)
        return InvitePreviewOut(
            title=group.title,
            display_name=group.display_name,
            theme=ThemeOut.model_validate(group.theme),
            event_at=group.event_at,
            event_location=group.event_location,
            min_value_cents=group.min_value_cents,
            max_value_cents=group.max_value_cents,
            organizer_name=group.owner.name,
            participant_count=count,
            can_join=reason is None,
            reason=reason,
        )

    async def join(self, code: str, user: User) -> JoinOut:
        # Trava o grupo para respeitar max_participants mesmo com entradas simultâneas.
        group = await self._group_by_code(code, for_update=True)
        existing = await self.participants.get_by_user(group.id, user.id)
        if existing is not None and existing.is_active:
            return JoinOut(group_id=group.id, already_member=True)
        reason = self._join_blocker(group, await self.participants.count_active(group.id))
        if reason is not None:
            raise ConflictError(reason, code="join_not_allowed")
        if existing is not None:
            existing.left_at = None
            existing.joined_at = datetime.now(UTC)
        else:
            await self.participants.add(Participant(group_id=group.id, user_id=user.id))
        await self.session.commit()
        logger.info("group_joined", extra={"group_id": str(group.id)})
        return JoinOut(group_id=group.id, already_member=False)

    # --- Internos ---

    async def _group_by_code(self, code: str, *, for_update: bool = False) -> Group:
        group = await self.groups.get_by_invite_code(code, for_update=for_update)
        if group is None:
            raise NotFoundError("Convite inválido ou expirado.", code="invite_not_found")
        return group

    @staticmethod
    def _join_blocker(group: Group, active_count: int) -> str | None:
        if group.status is GroupStatus.DRAFT:
            return "O organizador ainda não abriu as inscrições."
        if group.status is not GroupStatus.OPEN:
            return "As inscrições deste grupo estão encerradas."
        if group.join_deadline_at and group.join_deadline_at <= datetime.now(UTC):
            return "O prazo de inscrição terminou."
        if active_count >= group.max_participants:
            return "O grupo atingiu o limite de participantes."
        return None

    async def _theme(self, slug: str) -> GroupTheme:
        theme = await self.groups.get_theme_by_slug(slug)
        if theme is None:
            raise UnprocessableError("Tema inválido.", code="invalid_theme")
        return theme

    async def _unique_invite_code(self) -> str:
        while True:
            code = generate_invite_code()
            if not await self.groups.invite_code_exists(code):
                return code

    @staticmethod
    def _validate_event_dates(data: GroupCreate | GroupUpdate, previous: Group | None) -> None:
        now = datetime.now(UTC)
        changed = data.model_fields_set
        if "event_at" in changed and data.event_at and data.event_at <= now:
            raise UnprocessableError("A data do evento precisa ser no futuro.", code="invalid_date")
        if (
            "wishlist_deadline_at" in changed
            and data.wishlist_deadline_at
            and data.wishlist_deadline_at <= now
        ):
            raise UnprocessableError("O prazo da lista precisa ser no futuro.", code="invalid_date")
        if (
            "draw_scheduled_at" in changed
            and data.draw_scheduled_at
            and data.draw_scheduled_at <= now
        ):
            raise UnprocessableError(
                "O sorteio automático precisa ser no futuro.", code="invalid_date"
            )
        if "join_deadline_at" in changed and data.join_deadline_at and data.join_deadline_at <= now:
            raise UnprocessableError(
                "O prazo de inscrição precisa ser no futuro.", code="invalid_date"
            )

    @staticmethod
    def _validate_ranges(group: Group) -> None:
        lo, hi = group.min_value_cents, group.max_value_cents
        if lo is not None and hi is not None and hi < lo:
            raise UnprocessableError(
                "O valor máximo deve ser maior ou igual ao mínimo.", code="invalid_values"
            )
        if group.event_at and group.join_deadline_at and group.join_deadline_at > group.event_at:
            raise UnprocessableError(
                "O prazo de inscrição deve ser antes do evento.", code="invalid_date"
            )
        if group.event_at and group.draw_scheduled_at and group.draw_scheduled_at > group.event_at:
            raise UnprocessableError(
                "O sorteio automático deve ser antes do evento.", code="invalid_date"
            )
        if (
            group.event_at
            and group.wishlist_deadline_at
            and group.wishlist_deadline_at > group.event_at
        ):
            raise UnprocessableError(
                "O prazo da lista de desejos deve ser antes do evento.", code="invalid_date"
            )

    async def _to_out(self, membership: Membership) -> GroupOut:
        group, me = membership.group, membership.participant
        return GroupOut(
            id=group.id,
            title=group.title,
            display_name=group.display_name,
            custom_name=group.custom_name,
            description=group.description,
            theme=ThemeOut.model_validate(group.theme),
            min_value_cents=group.min_value_cents,
            max_value_cents=group.max_value_cents,
            event_at=group.event_at,
            event_location=group.event_location,
            event_maps_url=group.event_maps_url,
            join_deadline_at=group.join_deadline_at,
            wishlist_deadline_at=group.wishlist_deadline_at,
            draw_scheduled_at=group.draw_scheduled_at,
            status=group.status,
            invite_code=group.invite_code,
            max_participants=group.max_participants,
            prefer_single_cycle=group.prefer_single_cycle,
            owner=UserBrief(
                id=group.owner.id, name=group.owner.name, avatar_url=group.owner.avatar_url
            ),
            my_role=me.role,
            my_participant_id=me.id,
            participant_count=await self.participants.count_active(group.id),
            created_at=group.created_at,
        )
