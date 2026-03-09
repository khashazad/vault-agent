from typing import Literal

from pydantic import BaseModel, Field


class ReadNoteInput(BaseModel):
    path: str = Field(max_length=500)


class CreateNoteInput(BaseModel):
    path: str = Field(max_length=500)
    content: str = Field(max_length=200_000)


class UpdateNoteInput(BaseModel):
    path: str = Field(max_length=500)
    operation: Literal["append_section"]
    heading: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=200_000)
