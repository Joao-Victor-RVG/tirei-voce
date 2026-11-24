from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

from app.modules.users.schemas import Name

Password = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    email: EmailStr
    password: Password


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password


class CsrfOut(BaseModel):
    csrf_token: str
