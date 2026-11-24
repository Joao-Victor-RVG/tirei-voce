import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from app.modules.groups.models import GroupStatus
from app.modules.participants.models import ParticipantRole

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
CustomName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Cents = Annotated[int, Field(ge=0, le=100_000_00)]


class ThemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    display_name: str
    emoji: str
    description: str


class _GroupFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custom_name: CustomName | None = None
    description: Description | None = None
    min_value_cents: Cents | None = None
    max_value_cents: Cents | None = None
    event_at: AwareDatetime | None = None
    event_location: Location | None = None
    event_maps_url: HttpUrl | None = None
    join_deadline_at: AwareDatetime | None = None
    wishlist_deadline_at: AwareDatetime | None = None
    draw_scheduled_at: AwareDatetime | None = None
    avoid_previous_pairs: bool | None = None
    max_participants: Annotated[int, Field(ge=3, le=200)] | None = None
    prefer_single_cycle: bool | None = None

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        lo, hi = self.min_value_cents, self.max_value_cents
        if lo is not None and hi is not None and hi < lo:
            raise ValueError("O valor máximo deve ser maior ou igual ao mínimo.")
        if self.event_at and self.join_deadline_at and self.join_deadline_at > self.event_at:
            raise ValueError("O prazo de inscrição deve ser antes do evento.")
        if (
            self.event_at
            and self.wishlist_deadline_at
            and self.wishlist_deadline_at > self.event_at
        ):
            raise ValueError("O prazo da lista de desejos deve ser antes do evento.")
        if self.event_at and self.draw_scheduled_at and self.draw_scheduled_at > self.event_at:
            raise ValueError("O sorteio automático deve ser antes do evento.")
        return self


class GroupCreate(_GroupFields):
    theme_slug: Annotated[str, StringConstraints(max_length=50)]
    title: Title


class GroupUpdate(_GroupFields):
    theme_slug: Annotated[str, StringConstraints(max_length=50)] | None = None
    title: Title | None = None


class UserBrief(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None


class GroupOut(BaseModel):
    id: uuid.UUID
    title: str
    display_name: str
    custom_name: str | None
    description: str | None
    theme: ThemeOut
    min_value_cents: int | None
    max_value_cents: int | None
    event_at: datetime | None
    event_location: str | None
    event_maps_url: str | None
    join_deadline_at: datetime | None
    wishlist_deadline_at: datetime | None
    draw_scheduled_at: datetime | None
    previous_group_id: uuid.UUID | None
    avoid_previous_pairs: bool
    status: GroupStatus
    invite_code: str
    max_participants: int
    prefer_single_cycle: bool
    owner: UserBrief
    my_role: ParticipantRole
    my_participant_id: uuid.UUID
    participant_count: int
    created_at: datetime


class GroupSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    display_name: str
    theme: ThemeOut
    event_at: datetime | None
    status: GroupStatus
    my_role: ParticipantRole
    participant_count: int


class InvitePreviewOut(BaseModel):
    title: str
    display_name: str
    theme: ThemeOut
    event_at: datetime | None
    event_location: str | None
    min_value_cents: int | None
    max_value_cents: int | None
    organizer_name: str
    participant_count: int
    can_join: bool
    reason: str | None = Field(description="Por que não dá para entrar, quando can_join=false")


class JoinOut(BaseModel):
    group_id: uuid.UUID
    already_member: bool


class GroupDuplicate(BaseModel):
    """Nova edição: copia as configurações; as pessoas entram de novo pelo convite novo."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    event_at: AwareDatetime | None = None
    avoid_previous_pairs: bool = True
