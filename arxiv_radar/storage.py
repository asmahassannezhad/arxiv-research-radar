from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from .models import Paper


class SeenPaperStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS seen_papers (
                    arxiv_id TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)

    def filter_new(self, papers: Sequence[Paper], *, include_updated: bool = True) -> list[Paper]:
        with self._connect() as db:
            rows = db.execute("SELECT arxiv_id, last_updated FROM seen_papers").fetchall()
        seen = {paper_id: updated for paper_id, updated in rows}
        return [p for p in papers if p.arxiv_id not in seen or (include_updated and p.updated.isoformat() > seen[p.arxiv_id])]

    def mark_seen(self, papers: Sequence[Paper]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.executemany("""
                INSERT INTO seen_papers(arxiv_id, first_seen, last_updated) VALUES (?, ?, ?)
                ON CONFLICT(arxiv_id) DO UPDATE SET last_updated=excluded.last_updated
            """, [(p.arxiv_id, now, p.updated.isoformat()) for p in papers])

