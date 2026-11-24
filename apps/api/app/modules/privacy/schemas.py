from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints


class DeleteAccountIn(BaseModel):
    """Contas com senha confirmam com a senha; contas só Google digitam EXCLUIR."""

    model_config = ConfigDict(extra="forbid")

    password: Annotated[str, StringConstraints(max_length=256)] | None = None
    confirm: Annotated[str, StringConstraints(max_length=20)] | None = None


class DeleteAccountOut(BaseModel):
    mode: str  # "deleted" | "anonymized"


ExportOut = dict[str, Any]
