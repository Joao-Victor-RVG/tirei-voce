"""Registro de todos os models, usado pelo Alembic e pelos testes."""

from app.core.db import Base
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.groups.models import Group, GroupTheme
from app.modules.participants.models import Participant
from app.modules.users.models import User
from app.modules.wishlist.models import ParticipantPreferences, WishlistItem

__all__ = [
    "Base",
    "EmailToken",
    "Group",
    "GroupTheme",
    "Participant",
    "ParticipantPreferences",
    "RefreshToken",
    "User",
    "WishlistItem",
]
