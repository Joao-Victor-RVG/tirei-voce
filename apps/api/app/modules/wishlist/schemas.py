import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

ItemTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Priority = Annotated[int, Field(ge=1, le=3, description="1 = quero muito, 3 = tanto faz")]
Cents = Annotated[int, Field(ge=0, le=100_000_00)]


class WishlistItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ItemTitle
    url: HttpUrl | None = None
    price_hint_cents: Cents | None = None
    priority: Priority = 2
    notes: LongText | None = None


class WishlistItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ItemTitle | None = None
    url: HttpUrl | None = None
    price_hint_cents: Cents | None = None
    priority: Priority | None = None
    notes: LongText | None = None


class WishlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    url: str | None
    price_hint_cents: int | None
    priority: int
    notes: str | None


class PreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dislikes: LongText | None = None
    notes: LongText | None = None


class PreferencesOut(BaseModel):
    dislikes: str | None
    notes: str | None
