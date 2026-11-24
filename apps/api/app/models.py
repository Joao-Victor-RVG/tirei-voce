"""Registro de todos os models, usado pelo Alembic e pelos testes."""

from app.core.db import Base
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.chat.models import ChatMessage
from app.modules.draws.models import Draw, DrawAssignment
from app.modules.groups.models import Group, GroupTheme
from app.modules.notifications.models import PushSubscription
from app.modules.participants.models import Participant
from app.modules.rules.models import BlockedPair, ExclusionCircle, ExclusionCircleMember
from app.modules.users.models import User
from app.modules.wishlist.models import ParticipantPreferences, WishlistItem

__all__ = [
    "Base",
    "BlockedPair",
    "ChatMessage",
    "Draw",
    "DrawAssignment",
    "EmailToken",
    "ExclusionCircle",
    "ExclusionCircleMember",
    "Group",
    "GroupTheme",
    "Participant",
    "ParticipantPreferences",
    "PushSubscription",
    "RefreshToken",
    "User",
    "WishlistItem",
]
