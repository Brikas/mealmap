from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.utils import date_utils


class BasicModel(BaseModel):
    """Pydantic model with basic configs for all other models."""

    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: date_utils.datetime_to_iso,
            time: date_utils.time_to_iso,
            UUID: str,
        },
    )


class OrmBasicModel(BasicModel):
    """Pydantic model to be created from an orm."""

    model_config = ConfigDict(from_attributes=True)


class NoExtraBasicModel(BasicModel):
    """Pydantic model which does not allow extra fields."""

    model_config = ConfigDict(extra="forbid")
