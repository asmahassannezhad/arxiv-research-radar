from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Paper:
    title: str
    authors: list[str]
    arxiv_id: str
    abstract: str
    primary_category: str
    categories: list[str]
    submitted: datetime
    updated: datetime
    pdf_url: str
    abstract_url: str


@dataclass(slots=True)
class ScoreBreakdown:
    topic: int = 0
    importance: int = 0
    author_network: int = 0
    freshness: int = 0
    proximity: int = 0
    feedback: int = 0
    evidence: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return max(0, min(100, self.topic + self.importance + self.author_network + self.freshness + self.proximity + self.feedback))
