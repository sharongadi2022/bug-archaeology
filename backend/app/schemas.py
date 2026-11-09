from pydantic import BaseModel, Field
from typing import Any


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Source(BaseModel):
    id: str
    kind: str
    title: str
    excerpt: str
    url: str = ""
    date: str = ""
    score: float = 0.0


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    mode: str


class IngestResponse(BaseModel):
    indexed: int
    message: str
    repository: str
