from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

Key = Annotated[str, StringConstraints(min_length=10, max_length=255, pattern=r"^[A-Za-z0-9_=-]+$")]


class PushKeys(BaseModel):
    p256dh: Key
    auth: Key


class PushSubscriptionIn(BaseModel):
    """Formato de PushSubscription.toJSON() do navegador."""

    model_config = ConfigDict(extra="ignore")

    endpoint: Annotated[HttpUrl, Field(max_length=2048)]
    keys: PushKeys


class PushConfigOut(BaseModel):
    enabled: bool
    public_key: str | None
    subscribed: bool = Field(description="Se este navegador (endpoint informado) já está inscrito")
