import uuid

from pydantic import BaseModel


class ObjectCreationResponse(BaseModel):
    id: uuid.UUID


class BackendImageResponse(BaseModel):
    id: uuid.UUID
    image_url: str
    sequence_index: int


class MessageResponse(BaseModel):
    message: str
