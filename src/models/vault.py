from pydantic import BaseModel


class VaultNoteSummary(BaseModel):
    path: str
    title: str
    wikilinks: list[str]
    headings: list[str]


class VaultNote(BaseModel):
    path: str
    frontmatter: dict
    content: str
    wikilinks: list[str]


class VaultMap(BaseModel):
    total_notes: int
    notes: list[VaultNoteSummary]
    as_string: str
