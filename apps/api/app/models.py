"""Registro de todos os models, usado pelo Alembic e pelos testes."""

from app.core.db import Base
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.users.models import User

__all__ = ["Base", "EmailToken", "RefreshToken", "User"]
