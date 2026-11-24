import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.wishlist.schemas import PreferencesOut, WishlistItemOut


class ConstrainedParticipant(BaseModel):
    participant_id: uuid.UUID
    name: str
    options: int


class DrawValidationOut(BaseModel):
    possible: bool
    participant_count: int
    min_participants: int
    message: str
    most_constrained: list[ConstrainedParticipant]


class DrawOut(BaseModel):
    """Resultado do sorteio para o organizador: nunca contém pares."""

    draw_id: uuid.UUID
    version: int
    executed_at: datetime
    participant_count: int


class GiftStatusIn(BaseModel):
    purchased: bool


class GiftStatusOut(BaseModel):
    purchased: bool


class GiftProgressOut(BaseModel):
    """Só números agregados: nunca diz quem comprou para quem."""

    purchased: int
    total: int


class MyMatchOut(BaseModel):
    participant_id: uuid.UUID
    name: str
    avatar_url: str | None
    shirt_size: str | None
    shoe_size: str | None
    wishlist: list[WishlistItemOut]
    preferences: PreferencesOut
    gift_purchased: bool


class MySantaOut(BaseModel):
    """Revelação no dia do evento: só quem tirou o próprio usuário."""

    participant_id: uuid.UUID
    name: str
    avatar_url: str | None
