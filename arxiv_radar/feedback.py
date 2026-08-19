from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from .config import Settings
from .models import Paper


class FeedbackStore:
    """Persist paper judgements and turn them into small, transparent score nudges."""

    def __init__(self, path: Path, settings: Settings):
        self.path = path
        self.settings = settings
        self._lock = Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"papers": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data.get("papers"), dict) else {"papers": {}}
        except (json.JSONDecodeError, OSError):
            return {"papers": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def record(self, paper: Paper, rating: str) -> None:
        if rating not in {"very_relevant", "useful", "not_relevant", "save_later"}:
            raise ValueError("Unknown feedback rating")
        with self._lock:
            self._data["papers"][paper.arxiv_id] = {
                "rating": rating,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "categories": paper.categories,
                "primary_category": paper.primary_category,
            }
            self._save()

    def rating_for(self, arxiv_id: str) -> str | None:
        return self._data["papers"].get(arxiv_id, {}).get("rating")

    def learned_weights(self) -> dict[str, int]:
        weights: dict[str, int] = {}
        for record in self._data["papers"].values():
            delta = {
                "very_relevant": 4,
                "useful": 2,
                "not_relevant": -4,
                "save_later": 0,
            }.get(record["rating"], 0)
            if not delta:
                continue
            text = f"{record.get('title', '')} {record.get('abstract', '')}".lower()
            for keyword in self.settings.keywords:
                if keyword.lower() in text:
                    category = record.get("primary_category") or (record.get("categories") or [""])[0]
                    signal = f"{keyword}@@{category}"
                    weights[signal] = max(-10, min(10, weights.get(signal, 0) + delta))
        return weights

    def adjustment(self, paper: Paper) -> tuple[int, list[str]]:
        text = f"{paper.title} {paper.abstract}".lower()
        matches = []
        for signal, weight in self.learned_weights().items():
            term, category = signal.rsplit("@@", 1)
            if term.lower() in text and category == paper.primary_category and weight:
                matches.append((term, weight))
        adjustment = max(-10, min(10, sum(weight for _, weight in matches)))
        evidence = [f"feedback preference: {term} ({weight:+d})" for term, weight in matches[:3]]
        return adjustment, evidence
