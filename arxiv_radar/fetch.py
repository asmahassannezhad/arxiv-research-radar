from __future__ import annotations

import time
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings
from .models import Paper

API_URL = "https://export.arxiv.org/api/query"
ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivFetchError(RuntimeError):
    pass


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalise_id(url: str) -> str:
    identifier = url.rstrip("/").partition("/abs/")[2] or url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", identifier)


def parse_atom(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ATOM):
        author_nodes = entry.findall("atom:author", ATOM)
        links = {link.get("rel", "alternate"): link.get("href", "") for link in entry.findall("atom:link", ATOM)}
        pdf = next((link.get("href", "") for link in entry.findall("atom:link", ATOM) if link.get("title") == "pdf"), "")
        abstract_url = links.get("alternate") or (entry.findtext("atom:id", "", ATOM))
        primary = entry.find("arxiv:primary_category", ATOM)
        papers.append(Paper(
            title=" ".join(entry.findtext("atom:title", "", ATOM).split()),
            authors=[a.findtext("atom:name", "", ATOM).strip() for a in author_nodes],
            arxiv_id=_normalise_id(entry.findtext("atom:id", "", ATOM)),
            abstract=" ".join(entry.findtext("atom:summary", "", ATOM).split()),
            primary_category=primary.get("term", "") if primary is not None else "",
            categories=[c.get("term", "") for c in entry.findall("atom:category", ATOM)],
            submitted=_parse_datetime(entry.findtext("atom:published", "", ATOM)),
            updated=_parse_datetime(entry.findtext("atom:updated", "", ATOM)),
            pdf_url=pdf,
            abstract_url=abstract_url,
        ))
    return papers


def _quoted(term: str) -> str:
    escaped = term.replace('"', '')
    return f'all:"{escaped}"'


def build_queries(settings: Settings, start: datetime, end: datetime) -> list[str]:
    date_clause = f"submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
    category_clause = " OR ".join(f"cat:{category}" for category in settings.categories)
    queries = [f"({category_clause}) AND {date_clause}"]
    # Keyword batches keep request URLs comfortably below common proxy limits.
    for offset in range(0, len(settings.keywords), 8):
        terms = " OR ".join(_quoted(k) for k in settings.keywords[offset:offset + 8])
        queries.append(f"({terms}) AND ({category_clause}) AND {date_clause}")
    for offset in range(0, len(settings.author_keywords), 8):
        authors = " OR ".join(
            f'au:"{author.replace(chr(34), "")}"'
            for author in settings.author_keywords[offset:offset + 8]
        )
        queries.append(f"({authors}) AND ({category_clause}) AND {date_clause}")
    return queries


def category_is_allowed(primary_category: str, settings: Settings) -> bool:
    allowed = set(settings.categories)
    if "math-ph" in allowed:
        allowed.add("math.MP")
    return primary_category in allowed


def _request(query: str, max_results: int, timeout: float = 30.0) -> list[Paper]:
    params = {"search_query": query, "start": 0, "max_results": max_results, "sortBy": "submittedDate", "sortOrder": "descending"}
    try:
        request = Request(
            f"{API_URL}?{urlencode(params)}",
            headers={"User-Agent": "arxiv-spectral-geometry-radar/0.1 (research tool)"},
        )
        with urlopen(request, timeout=timeout) as response:
            return parse_atom(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ET.ParseError, UnicodeDecodeError) as exc:
        raise ArxivFetchError(f"arXiv request failed: {exc}") from exc


def fetch_recent(settings: Settings, *, now: datetime | None = None) -> list[Paper]:
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(days=settings.days)
    return fetch_between(settings, start=start, end=end)


def fetch_between(settings: Settings, *, start: datetime, end: datetime) -> list[Paper]:
    """Fetch papers submitted in an explicit UTC date/time interval."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    found: dict[str, Paper] = {}
    queries = build_queries(settings, start, end)
    per_query = max(20, min(settings.max_results, (settings.max_results // len(queries)) + 10))
    for index, query in enumerate(queries):
        if index:
            time.sleep(settings.request_delay_seconds)
        for paper in _request(query, per_query):
            if category_is_allowed(paper.primary_category, settings) and start <= paper.submitted < end:
                found[paper.arxiv_id] = paper
    return sorted(found.values(), key=lambda p: p.submitted, reverse=True)[:settings.max_results]


def deduplicate(papers: Iterable[Paper]) -> list[Paper]:
    return list({paper.arxiv_id: paper for paper in papers}.values())
