import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.groups.schemas import UserBrief
from app.modules.participants.models import ParticipantRole


class ParticipantOut(BaseModel):
    id: uuid.UUID
    user: UserBrief
    role: ParticipantRole
    joined_at: datetime
    is_me: bool
