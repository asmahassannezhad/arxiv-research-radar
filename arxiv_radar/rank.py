from __future__ import annotations

import re
from datetime import datetime, timezone

from .config import Settings
from .models import Paper, ScoreBreakdown


def _contains(text: str, phrase: str) -> bool:
    plural = "" if phrase.endswith("s") else "s?"
    return re.search(r"(?<!\w)" + re.escape(phrase) + plural + r"(?!\w)", text, re.IGNORECASE) is not None


def score_paper(paper: Paper, settings: Settings, *, now: datetime | None = None) -> ScoreBreakdown:
    now = now or datetime.now(timezone.utc)
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    text = f"{title} {abstract}"
    evidence: list[str] = []

    topic_candidates: list[tuple[int, str]] = []
    for phrase, value in {**settings.medium_topic, **settings.high_topic}.items():
        if _contains(text, phrase):
            title_bonus = 3 if _contains(title, phrase) else 0
            topic_candidates.append((min(40, value + title_bonus), phrase))
    topic = max((value for value, _ in topic_candidates), default=0)
    best_phrase = None
    if topic_candidates:
        best = max(topic_candidates)
        best_phrase = best[1]
        evidence.append(f'topic match: "{best[1]}"')
        if len(topic_candidates) >= 2:
            topic = min(40, topic + min(6, len(topic_candidates) - 1))
    elif "math.DG" in paper.categories:
        topic = 12
        evidence.append("differential-geometric arXiv category")
    elif any(c in {"math.SP", "math.AP", "math.MG"} for c in paper.categories):
        topic = 7
        evidence.append("broadly relevant arXiv category")

    mathematical_category = any(
        category.startswith("math.") or category in {"math-ph", "gr-qc"}
        for category in paper.categories
    )
    if not mathematical_category and topic:
        topic = min(topic, 15)
        evidence.append("topic phrase used outside a mathematical arXiv category")
    contextual_penalty = False
    if best_phrase == "spectral geometry" and any(term in text for term in settings.machine_learning_context) and not any(term in text for term in settings.geometric_context):
        topic = min(topic, 10)
        contextual_penalty = True
        evidence.append("machine-learning use of spectral geometry without geometric context")
    elif best_phrase == "dirichlet-to-neumann" and any(term in text for term in settings.machine_learning_context) and "inverse problem" not in text:
        topic = min(topic, 20)
        contextual_penalty = True
        evidence.append("computational DtN use without an inverse or geometric spectral problem")

    importance = 0
    impact_hits = []
    for phrase, value in settings.impact_terms.items():
        if _contains(text, phrase):
            importance += value
            impact_hits.append(phrase)
    importance = min(30, importance)
    if impact_hits:
        evidence.append("result signals: " + ", ".join(impact_hits[:4]))

    matched_authors = [known for known in settings.author_keywords if any(_contains(author, known) for author in paper.authors)]
    author_network = min(10, 7 + 2 * (len(matched_authors) - 1)) if matched_authors else 0
    if matched_authors:
        evidence.append("author signal: " + ", ".join(matched_authors))

    age_days = max(0, (now - paper.submitted).total_seconds() / 86400)
    update_gap = (paper.updated - paper.submitted).total_seconds() / 86400
    if update_gap > 2 and (now - paper.updated).total_seconds() / 86400 <= settings.days:
        freshness = 7 if update_gap >= 30 else 5
        evidence.append("recently updated submission")
    elif age_days <= 2:
        freshness = 10
    elif age_days <= settings.days:
        freshness = 8
    else:
        freshness = 2

    proximity_hits = [phrase for phrase in settings.proximate if phrase in text]
    if proximity_hits:
        proximity = 10 if any(p in text for p in settings.proximate[:5]) else 8
        evidence.append("direct project proximity: " + ", ".join(proximity_hits[:3]))
    elif topic >= 25:
        proximity = 6
    elif topic >= 15:
        proximity = 4
    else:
        proximity = 1 if topic else 0
    if not mathematical_category:
        proximity = min(proximity, 3)
    if contextual_penalty:
        proximity = min(proximity, 4)

    return ScoreBreakdown(
        topic=topic,
        importance=importance,
        author_network=author_network,
        freshness=freshness,
        proximity=proximity,
        evidence=evidence,
    )


def label_for_score(score: int) -> str:
    if score >= 85:
        return "Must read"
    if score >= 70:
        return "Very relevant"
    if score >= 55:
        return "Worth skimming"
    if score >= 40:
        return "Possibly relevant"
    return "Ignore unless time permits"
