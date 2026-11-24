import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

# "match": conversa com quem eu tirei. "santa": conversa com quem me tirou (anônima).
Thread = Literal["match", "santa"]

MessageBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class ChatMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: MessageBody


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    from_me: bool
    body: str
    created_at: datetime


class ChatThreadSummary(BaseModel):
    thread: Thread
    title: str
    unread: int
    last_message: ChatMessageOut | None


class ChatMessagePage(BaseModel):
    items: list[ChatMessageOut]
    next_cursor: str | None
