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

# arXiv accepts large pages; a few hundred per request keeps URLs and memory
# reasonable while minimising the number of requests (and thus rate-limiting).
PAGE_SIZE = 200


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


def build_queries(settings: Settings, start: datetime, end: datetime) -> list[str]:
    """Return the search queries for a window.

    A single category-restricted, date-bounded query is used. Because the radar
    only keeps papers whose *primary* category is in ``settings.categories``,
    this one query is a strict superset of any keyword or author sub-search, so
    extra requests would only add rate-limiting risk without widening coverage.
    Keyword and author relevance are applied later, during ranking.
    """
    date_clause = f"submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
    category_clause = " OR ".join(f"cat:{category}" for category in settings.categories)
    return [f"({category_clause}) AND {date_clause}"]


def category_is_allowed(primary_category: str, settings: Settings) -> bool:
    allowed = set(settings.categories)
    if "math-ph" in allowed:
        allowed.add("math.MP")
    return primary_category in allowed


def _retry_after_seconds(exc: HTTPError) -> float | None:
    header = exc.headers.get("Retry-After") if exc.headers else None
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def _request(query: str, max_results: int, *, start_index: int = 0, timeout: float = 60.0, retries: int = 3) -> list[Paper]:
    params = {
        "search_query": query,
        "start": start_index,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{API_URL}?{urlencode(params)}"
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": "arxiv-research-radar/0.2 (research tool)"})
            with urlopen(request, timeout=timeout) as response:
                return parse_atom(response.read().decode("utf-8"))
        except HTTPError as exc:
            # 429 (rate limited) and 503 (temporarily unavailable) are both arXiv
            # asking us to slow down; back off and retry, honouring Retry-After.
            if exc.code in (429, 503) and attempt < retries:
                time.sleep(_retry_after_seconds(exc) or 5.0 * (attempt + 1))
                continue
            if exc.code in (429, 503):
                raise ArxivFetchError(
                    "arXiv is busy or rate-limiting requests right now "
                    f"(HTTP {exc.code}). Please wait a minute and press Run radar again."
                ) from exc
            raise ArxivFetchError(f"arXiv request failed: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            # Transient network/slowness (arXiv can be slow under load): back off and retry.
            if attempt < retries:
                time.sleep(3.0 * (attempt + 1))
                continue
            raise ArxivFetchError(f"arXiv request failed: {exc}") from exc
        except (ET.ParseError, UnicodeDecodeError) as exc:
            raise ArxivFetchError(f"arXiv request failed: {exc}") from exc
    return []


def fetch_recent(settings: Settings, *, now: datetime | None = None) -> list[Paper]:
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(days=settings.days)
    return fetch_between(settings, start=start, end=end)


def fetch_between(settings: Settings, *, start: datetime, end: datetime) -> list[Paper]:
    """Fetch every paper submitted in an explicit UTC interval, up to
    ``settings.max_results``, by paging through the arXiv results."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    query = build_queries(settings, start, end)[0]
    found: dict[str, Paper] = {}
    offset = 0
    while offset < settings.max_results:
        if offset:
            time.sleep(settings.request_delay_seconds)
        page_size = min(PAGE_SIZE, settings.max_results - offset)
        page = _request(query, page_size, start_index=offset)
        if not page:
            break
        reached_older_than_window = False
        for paper in page:
            if paper.submitted < start:
                # Results are newest-first, so everything after this is older too.
                reached_older_than_window = True
                continue
            if paper.submitted < end and category_is_allowed(paper.primary_category, settings):
                found[paper.arxiv_id] = paper
        if reached_older_than_window or len(page) < page_size:
            break
        offset += len(page)
    return sorted(found.values(), key=lambda p: p.submitted, reverse=True)[:settings.max_results]


def deduplicate(papers: Iterable[Paper]) -> list[Paper]:
    return list({paper.arxiv_id: paper for paper in papers}.values())
