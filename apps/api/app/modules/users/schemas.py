import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from app.modules.users.models import User

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Size = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    email_verified: bool
    avatar_url: str | None
    shirt_size: str | None
    shoe_size: str | None
    has_password: bool
    has_google: bool
    email_reminders: bool
    phone: str | None
    whatsapp_opt_in: bool
    is_admin: bool

    @classmethod
    def from_user(cls, user: User) -> "MeOut":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            email_verified=user.is_email_verified,
            avatar_url=user.avatar_url,
            shirt_size=user.shirt_size,
            shoe_size=user.shoe_size,
            has_password=user.password_hash is not None,
            has_google=user.google_sub is not None,
            email_reminders=user.email_reminders,
            phone=user.phone,
            whatsapp_opt_in=user.whatsapp_opt_in,
            is_admin=user.is_admin,
        )


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    avatar_url: HttpUrl | None = Field(default=None, max_length=2048)
    shirt_size: Size | None = None
    shoe_size: Size | None = None
    email_reminders: bool | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    whatsapp_opt_in: bool | None = None
