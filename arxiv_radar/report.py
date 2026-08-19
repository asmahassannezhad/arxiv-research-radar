from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from .models import Paper, ScoreBreakdown
from .rank import label_for_score

RankedPaper = tuple[Paper, ScoreBreakdown]


def _abstract_excerpt(abstract: str, limit: int = 320) -> str:
    text = " ".join(abstract.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _breakdown_line(score: ScoreBreakdown) -> str:
    parts = [
        f"topic {score.topic}", f"importance {score.importance}",
        f"authors {score.author_network}", f"freshness {score.freshness}",
        f"proximity {score.proximity}",
    ]
    if score.feedback:
        parts.append(f"feedback {score.feedback:+d}")
    return " · ".join(parts)


def _top_entry(rank: int, paper: Paper, score: ScoreBreakdown) -> str:
    evidence = "\n".join(f"- {item}" for item in score.evidence) or "- Broad category relevance only."
    return f"""### Rank {rank}. {paper.title}

Score: {score.total}/100
Label: {label_for_score(score.total)}
Authors: {', '.join(paper.authors)}
arXiv: {paper.arxiv_id}
Link: {paper.abstract_url}
PDF: {paper.pdf_url}

**Abstract.**
{_abstract_excerpt(paper.abstract)}

**Why it ranked here.**

{evidence}

**Score breakdown.**
{_breakdown_line(score)}
"""


def render_report(
    ranked: Sequence[RankedPaper], *, days: int, min_score: int,
    title: str = "arXiv Research Radar", report_date: date | None = None,
) -> str:
    report_date = report_date or date.today()
    top = [item for item in ranked if item[1].total >= min_score]
    other = [item for item in ranked if 40 <= item[1].total < min_score]
    ignored = [item for item in ranked if item[1].total < 40]
    sections = [f"# {title}\n\nDate: {report_date.isoformat()}  \nWindow: last {days} days\n\n## Top recommendations\n"]
    sections.extend(_top_entry(i, p, s) for i, (p, s) in enumerate(top, 1))
    if not top:
        sections.append("No new papers met the recommendation threshold.\n")
    sections.append("## Other possibly relevant papers\n")
    sections.extend(f"- **{p.title}** — {', '.join(p.authors)} — {s.total}/100. {s.evidence[0] if s.evidence else 'Broad relevance only'}." for p, s in other)
    if not other:
        sections.append("No additional papers scored between 40 and the recommendation threshold.\n")
    sections.append("\n## Ignored papers\n")
    sections.extend(f"- {p.title} ({s.total}/100): insufficient specific topic evidence." for p, s in ignored)
    if not ignored:
        sections.append("No ignored papers in this run.\n")
    return "\n\n".join(sections).rstrip() + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_ignored_report(
    excluded: Sequence[RankedPaper], *, days: int, report_date: date | None = None
) -> str:
    report_date = report_date or date.today()
    lines = [
        "# Papers outside the top results",
        "",
        f"Date: {report_date.isoformat()}  ",
        f"Window: last {days} days",
        "",
        "These papers were scanned but did not place in the main report. They are ordered by score so the closest omissions are easiest to inspect.",
        "",
    ]
    for index, (paper, score) in enumerate(excluded, 1):
        reason = "; ".join(score.evidence) or "no specific topic match"
        lines.extend([
            f"## {index}. {paper.title}",
            "",
            f"Score: {score.total}/100  ",
            f"Authors: {', '.join(paper.authors)}  ",
            f"Categories: {', '.join(paper.categories)}  ",
            f"Link: {paper.abstract_url}  ",
            f"Reason: {reason}.",
            "",
        ])
    if not excluded:
        lines.append("No papers fell outside the top results in this run.")
    return "\n".join(lines).rstrip() + "\n"
