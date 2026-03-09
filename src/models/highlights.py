from pydantic import BaseModel, Field


class HighlightInput(BaseModel):
    text: str = Field(max_length=50_000)
    source: str = Field(max_length=2_000)
    annotation: str | None = Field(default=None, max_length=10_000)


class BatchHighlightInput(BaseModel):
    highlights: list[HighlightInput] = Field(max_length=50)
