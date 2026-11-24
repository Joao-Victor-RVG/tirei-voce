import enum
from typing import Any

from sqlalchemy import Enum


def str_enum(enum_cls: type[enum.StrEnum], name: str) -> Any:
    """Enum guardado como VARCHAR + CHECK (mais simples de evoluir que o ENUM nativo)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )
