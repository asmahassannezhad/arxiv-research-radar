from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from .config import load_settings
from .fetch import ArxivFetchError, fetch_recent
from .feedback import FeedbackStore
from .rank import score_paper
from .report import render_ignored_report, render_report, write_report
from .storage import SeenPaperStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arxiv-radar", description="Find and rank new arXiv papers by topic relevance.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Fetch, rank and report new papers")
    run.add_argument("--days", type=int, default=30)
    run.add_argument("--max-results", type=int, default=200)
    run.add_argument("--top", type=int, default=10, help="Maximum number of papers to include in the report (default: 10)")
    run.add_argument("--min-score", type=int, default=55, help="Score at or above which a paper gets a full report entry")
    run.add_argument("--output", type=Path, default=Path("report.md"))
    run.add_argument("--ignored-output", type=Path, default=Path("ignored.md"), help="Audit list of papers outside the top results")
    run.add_argument("--database", type=Path, default=Path(".arxiv-radar/seen.sqlite3"))
    run.add_argument("--include-seen", action="store_true", help="Include papers already reported")
    web = sub.add_parser("web", help="Launch the local web dashboard")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.days < 1 or args.max_results < 1 or args.top < 1 or not 0 <= args.min_score <= 100:
        raise SystemExit("days, max-results and top must be positive; min-score must be between 0 and 100")
    settings = replace(
        load_settings(Path.cwd()),
        days=args.days,
        max_results=args.max_results,
        minimum_score=args.min_score,
        output_path=args.output,
        database_path=args.database,
    )
    print(f"Checking arXiv for the last {args.days} days; this usually takes 35–60 seconds…", flush=True)
    try:
        papers = fetch_recent(settings)
    except ArxivFetchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    store = SeenPaperStore(settings.database_path)
    new_papers = papers if args.include_seen else store.filter_new(papers)
    if not new_papers and not args.include_seen:
        print("No unseen papers were found. Use --include-seen to rebuild the current top-ten report.", flush=True)
    scored = [(paper, score_paper(paper, settings)) for paper in new_papers]
    feedback = FeedbackStore(Path.cwd() / settings.feedback_path, settings)
    for paper, score in scored:
        score.feedback, feedback_evidence = feedback.adjustment(paper)
        score.evidence.extend(feedback_evidence)
    scored.sort(key=lambda item: item[1].total, reverse=True)
    selected = scored[:args.top]
    excluded = scored[args.top:]
    write_report(settings.output_path, render_report(selected, days=settings.days, min_score=args.min_score, title=settings.site_title))
    write_report(args.ignored_output, render_ignored_report(excluded, days=settings.days))
    store.mark_seen(new_papers)
    print(f"Wrote {settings.output_path} with the best {len(selected)} of {len(new_papers)} papers scanned.")
    print(f"Wrote {args.ignored_output} with {len(excluded)} papers outside the top results.")
    return 0


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "web":
        from .web import serve

        serve(host=args.host, port=args.port, open_browser=not args.no_open)
        return
    raise SystemExit(run(args))
