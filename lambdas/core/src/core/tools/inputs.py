from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PeriodInput(Input):
    start: date = Field(alias="from")
    end: date = Field(alias="to")
