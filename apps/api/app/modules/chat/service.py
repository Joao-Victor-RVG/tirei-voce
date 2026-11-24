import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.errors import ConflictError, NotFoundError
from app.modules.chat.models import ChatMessage, SenderRole
from app.modules.chat.repository import ChatRepository
from app.modules.chat.schemas import ChatMessageOut, ChatMessagePage, ChatThreadSummary, Thread
from app.modules.draws import crypto
from app.modules.draws.models import DrawAssignment
from app.modules.draws.repository import DrawRepository
from app.modules.groups.models import GroupStatus
from app.modules.groups.service import GroupAccess, Membership
from app.modules.notifications import events
from app.modules.participants.repository import ParticipantRepository
from app.modules.users.models import User

ANONYMOUS_TITLE = "Seu amigo secreto"


@dataclass(frozen=True)
class ChatThread:
    """Uma das duas conversas do participante, vista do lado dele."""

    thread: Thread
    assignment: DrawAssignment
    my_role: SenderRole

    @property
    def other_role(self) -> SenderRole:
        return SenderRole.RECEIVER if self.my_role is SenderRole.GIVER else SenderRole.GIVER


class ChatService:
    """Chat entre quem dá e quem recebe. Ninguém de fora da dupla (nem a organização) acessa."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = GroupAccess(session)
        self.draws = DrawRepository(session)
        self.participants = ParticipantRepository(session)
        self.repo = ChatRepository(session)

    async def threads(self, group_id: uuid.UUID, user: User) -> list[ChatThreadSummary]:
        membership = await self._drawn_member(group_id, user)
        summaries = []
        for name in ("match", "santa"):
            chat = await self._thread(membership, name)
            last = await self.repo.last(chat.assignment.id)
            summaries.append(
                ChatThreadSummary(
                    thread=chat.thread,
                    title=await self._title(chat),
                    unread=await self.repo.unread(chat.assignment.id, chat.other_role),
                    last_message=self._out(last, chat) if last else None,
                )
            )
        return summaries

    async def messages(
        self,
        group_id: uuid.UUID,
        user: User,
        thread: Thread,
        *,
        before: uuid.UUID | None,
        after: uuid.UUID | None,
        limit: int,
    ) -> ChatMessagePage:
        chat = await self._thread(await self._drawn_member(group_id, user), thread)
        rows = await self.repo.list(chat.assignment.id, before=before, after=after, limit=limit + 1)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit] if after is not None else rows[1:]
        items = [self._out(m, chat) for m in rows]
        next_cursor = str(items[0].id) if has_more and after is None and items else None
        return ChatMessagePage(items=items, next_cursor=next_cursor)

    async def send(
        self, group_id: uuid.UUID, user: User, thread: Thread, body: str
    ) -> ChatMessageOut:
        membership = await self._drawn_member(group_id, user)
        if membership.group.status is GroupStatus.FINISHED:
            raise ConflictError(
                "O grupo foi encerrado: o chat está só para leitura.", code="group_finished"
            )
        await rate_limit.hit("chat:user", str(user.id), limit=30, window_seconds=60)
        chat = await self._thread(membership, thread)
        message = await self.repo.add(
            ChatMessage(assignment_id=chat.assignment.id, sender_role=chat.my_role, body=body)
        )
        await self.session.commit()
        await events.chat_message(chat.assignment.id, chat.other_role.value)
        return self._out(message, chat)

    async def mark_read(self, group_id: uuid.UUID, user: User, thread: Thread) -> None:
        chat = await self._thread(await self._drawn_member(group_id, user), thread)
        await self.repo.mark_read(chat.assignment.id, chat.other_role, datetime.now(UTC))
        await self.session.commit()

    # --- Internos ---

    async def _drawn_member(self, group_id: uuid.UUID, user: User) -> Membership:
        membership = await self.access.member(group_id, user)
        if membership.group.status not in (GroupStatus.DRAWN, GroupStatus.FINISHED):
            raise ConflictError("O chat abre depois do sorteio.", code="draw_not_done")
        return membership

    async def _thread(self, membership: Membership, thread: Thread) -> ChatThread:
        draw = await self.draws.latest(membership.group.id)
        me = membership.participant.id
        assignment = None
        if draw is not None:
            if thread == "match":
                assignment = await self.draws.assignment_for_giver(draw.id, me)
            else:
                lookup = crypto.receiver_lookup_hash(draw.id, me)
                assignment = await self.repo.assignment_by_lookup(draw.id, lookup)
        if assignment is None:
            raise NotFoundError("Conversa não encontrada.", code="chat_not_found")
        role = SenderRole.GIVER if thread == "match" else SenderRole.RECEIVER
        return ChatThread(thread=thread, assignment=assignment, my_role=role)

    async def _title(self, chat: ChatThread) -> str:
        if chat.thread == "santa":
            return ANONYMOUS_TITLE
        receiver = await self.participants.get_by_id(
            crypto.decrypt_receiver(chat.assignment.receiver_encrypted)
        )
        return receiver.user.name if receiver else "Seu amigo"

    @staticmethod
    def _out(message: ChatMessage, chat: ChatThread) -> ChatMessageOut:
        return ChatMessageOut(
            id=message.id,
            from_me=message.sender_role is chat.my_role,
            body=message.body,
            created_at=message.created_at,
        )
