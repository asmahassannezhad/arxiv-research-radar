from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, request

from .config import Settings, load_settings
from .feedback import FeedbackStore
from .fetch import ArxivFetchError, category_is_allowed, fetch_between, fetch_recent
from .models import Paper, ScoreBreakdown
from .rank import label_for_score, score_paper
from .storage import SeenPaperStore


def _paper_to_dict(paper: Paper) -> dict:
    data = asdict(paper)
    data["submitted"] = paper.submitted.isoformat()
    data["updated"] = paper.updated.isoformat()
    return data


def _paper_from_dict(data: dict) -> Paper:
    values = dict(data)
    values["submitted"] = datetime.fromisoformat(values["submitted"])
    values["updated"] = datetime.fromisoformat(values["updated"])
    return Paper(**values)


class RadarService:
    def __init__(self, root: Path):
        self.root = root
        self.settings = load_settings(root)
        self.feedback = FeedbackStore(root / self.settings.feedback_path, self.settings)
        self.store = SeenPaperStore(root / self.settings.database_path)
        self.state_path = root / self.settings.web_state_path
        self.papers: list[Paper] = []
        self.ranked: list[tuple[Paper, ScoreBreakdown]] = []
        self.days = self.settings.days
        self.top_count = 10
        self.target_date: str | None = None
        self.last_run: str | None = None
        self._lock = Lock()
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.papers = [
                paper
                for item in data.get("papers", [])
                if category_is_allowed((paper := _paper_from_dict(item)).primary_category, self.settings)
            ]
            self.days = int(data.get("days", self.days))
            self.top_count = int(data.get("top_count", self.top_count))
            self.target_date = data.get("target_date")
            self.last_run = data.get("last_run")
            self._rerank()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.papers = []

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "papers": [_paper_to_dict(paper) for paper in self.papers],
            "days": self.days,
            "top_count": self.top_count,
            "target_date": self.target_date,
            "last_run": self.last_run,
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _rerank(self) -> None:
        ranked = []
        for paper in self.papers:
            score = score_paper(paper, replace(self.settings, days=self.days))
            adjustment, evidence = self.feedback.adjustment(paper)
            rating = self.feedback.rating_for(paper.arxiv_id)
            if rating == "very_relevant":
                score.feedback = max(25, adjustment)
                evidence.insert(0, "manually marked very relevant")
            elif rating == "useful":
                score.feedback = max(8, adjustment)
                evidence.insert(0, "manually marked useful")
            elif rating == "not_relevant":
                score.feedback = -100
                evidence.insert(0, "manually marked not relevant")
            else:
                score.feedback = adjustment
            score.evidence.extend(evidence)
            ranked.append((paper, score))
        self.ranked = sorted(
            ranked,
            key=lambda item: (
                self.feedback.rating_for(item[0].arxiv_id) != "not_relevant",
                self.feedback.rating_for(item[0].arxiv_id) == "very_relevant",
                item[1].total,
            ),
            reverse=True,
        )

    def run(self, *, days: int, max_results: int, top_count: int, target_date: str | None = None) -> dict:
        settings = replace(self.settings, days=days, max_results=max_results)
        if target_date:
            chosen_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            start = datetime.combine(chosen_date, time.min, tzinfo=timezone.utc)
            papers = fetch_between(settings, start=start, end=start + timedelta(days=1))
        else:
            papers = fetch_recent(settings)
        with self._lock:
            self.papers = papers
            self.days = days
            self.top_count = top_count
            self.target_date = target_date
            self.last_run = datetime.now().astimezone().isoformat(timespec="seconds")
            self._rerank()
            self._save_state()
            self.store.mark_seen(papers)
            return self.snapshot()

    def record_feedback(self, arxiv_id: str, rating: str) -> dict:
        with self._lock:
            paper = self.paper(arxiv_id)
            if paper is None:
                raise KeyError(arxiv_id)
            self.feedback.record(paper, rating)
            self._rerank()
            return self.snapshot()

    def paper(self, arxiv_id: str) -> Paper | None:
        return next((paper for paper in self.papers if paper.arxiv_id == arxiv_id), None)

    def _card(self, paper: Paper, score: ScoreBreakdown, rank: int) -> dict:
        rating = self.feedback.rating_for(paper.arxiv_id)
        label = (
            "Very relevant · your choice" if rating == "very_relevant"
            else "Not relevant · your choice" if rating == "not_relevant"
            else label_for_score(score.total)
        )
        data = _paper_to_dict(paper)
        data.update({
            "rank": rank,
            "score": score.total,
            "label": label,
            "breakdown": {
                "topic": score.topic,
                "importance": score.importance,
                "authors": score.author_network,
                "freshness": score.freshness,
                "proximity": score.proximity,
                "feedback": score.feedback,
            },
            "evidence": score.evidence,
            "feedback_rating": rating,
        })
        return data

    def snapshot(self) -> dict:
        cards = [self._card(paper, score, index) for index, (paper, score) in enumerate(self.ranked, 1)]
        active = [card for card in cards if card["feedback_rating"] != "not_relevant"]
        dismissed = [card for card in cards if card["feedback_rating"] == "not_relevant"]
        return {
            "top": active[:self.top_count],
            "ignored": active[self.top_count:] + dismissed,
            "days": self.days,
            "target_date": self.target_date,
            "top_count": self.top_count,
            "total": len(cards),
            "last_run": self.last_run,
        }


def create_app(root: Path | None = None) -> Flask:
    root = root or Path.cwd()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    service = RadarService(root)
    app.config["RADAR_SERVICE"] = service

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            site_title=service.settings.site_title,
            eyebrow=service.settings.eyebrow,
            tagline=service.settings.tagline,
        )

    @app.get("/api/status")
    def status():
        return jsonify(service.snapshot())

    @app.post("/api/run")
    def run_radar():
        data = request.get_json(silent=True) or {}
        try:
            days = max(1, min(90, int(data.get("days", 30))))
            max_results = max(10, min(3000, int(data.get("max_results", service.settings.max_results))))
            top_count = max(1, min(50, int(data.get("top_count", 10))))
            raw_target_date = data.get("target_date")
            target_date = str(raw_target_date).strip() if raw_target_date is not None else None
            target_date = target_date or None
            return jsonify(service.run(days=days, max_results=max_results, top_count=top_count, target_date=target_date))
        except (ValueError, TypeError):
            return jsonify(error="Choose a valid date and numeric search settings."), 400
        except ArxivFetchError as exc:
            return jsonify(error=str(exc)), 502

    @app.post("/api/feedback")
    def feedback():
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(service.record_feedback(str(data.get("arxiv_id", "")), str(data.get("rating", ""))))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except KeyError:
            return jsonify(error="Paper not found in the current radar."), 404

    return app


def serve(*, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    create_app().run(host=host, port=port, debug=False)
