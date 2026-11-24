import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CircleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ParticipantIds = Annotated[list[uuid.UUID], Field(min_length=2, max_length=200)]


class CircleMemberOut(BaseModel):
    participant_id: uuid.UUID
    name: str


class CircleOut(BaseModel):
    id: uuid.UUID
    name: str
    members: list[CircleMemberOut]


class CircleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CircleName
    participant_ids: ParticipantIds


class CircleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CircleName | None = None
    participant_ids: ParticipantIds | None = None


class CircleMemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: uuid.UUID


class PairPerson(BaseModel):
    participant_id: uuid.UUID
    name: str


class BlockedPairOut(BaseModel):
    id: uuid.UUID
    giver: PairPerson
    receiver: PairPerson
    bidirectional: bool


class BlockedPairCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    giver_participant_id: uuid.UUID
    receiver_participant_id: uuid.UUID
    bidirectional: bool = False


class BlockedPairUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bidirectional: bool
