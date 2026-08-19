import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from arxiv_radar.models import Paper
from arxiv_radar.web import RadarService, create_app


class WebTests(unittest.TestCase):
    def test_dashboard_and_status_load(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app(root=Path(folder))
            client = app.test_client()
            self.assertEqual(client.get("/").status_code, 200)
            status = client.get("/api/status")
            self.assertEqual(status.status_code, 200)
            self.assertIn("top", status.get_json())

    def test_exact_day_search_uses_one_day_interval(self):
        with tempfile.TemporaryDirectory() as folder, patch("arxiv_radar.web.fetch_between", return_value=[]) as fetch:
            app = create_app(root=Path(folder))
            response = app.test_client().post("/api/run", json={
                "days": 30, "max_results": 200, "top_count": 10, "target_date": "2026-06-11"
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["target_date"], "2026-06-11")
            interval = fetch.call_args.kwargs
            self.assertEqual((interval["end"] - interval["start"]).days, 1)

    def test_recent_window_accepts_missing_or_null_target_date(self):
        with tempfile.TemporaryDirectory() as folder, patch("arxiv_radar.web.fetch_recent", return_value=[]) as fetch:
            app = create_app(root=Path(folder))
            client = app.test_client()

            missing = client.post("/api/run", json={"days": "7", "max_results": 200, "top_count": "10"})
            self.assertEqual(missing.status_code, 200)
            self.assertIsNone(missing.get_json()["target_date"])

            explicit_null = client.post("/api/run", json={
                "days": "7", "max_results": 200, "top_count": "10", "target_date": None
            })
            self.assertEqual(explicit_null.status_code, 200)
            self.assertIsNone(explicit_null.get_json()["target_date"])
            self.assertEqual(fetch.call_count, 2)

    def test_manual_feedback_overrides_the_automatic_cut(self):
        now = datetime.now(timezone.utc)
        strong = Paper("Sharp Steklov eigenvalue theorem", ["A. Author"], "2606.1", "An optimal rigidity result.", "math.SP", ["math.SP"], now, now, "pdf", "abs")
        weak = Paper("Connections on a manifold", ["B. Author"], "2606.2", "A construction in differential geometry.", "math.DG", ["math.DG"], now, now, "pdf", "abs")
        with tempfile.TemporaryDirectory() as folder:
            service = RadarService(Path(folder))
            service.papers = [strong, weak]
            service.top_count = 1
            service._rerank()
            self.assertEqual(service.snapshot()["top"][0]["arxiv_id"], strong.arxiv_id)

            promoted = service.record_feedback(weak.arxiv_id, "very_relevant")
            self.assertEqual(promoted["top"][0]["arxiv_id"], weak.arxiv_id)
            self.assertIn("your choice", promoted["top"][0]["label"])

            dismissed = service.record_feedback(weak.arxiv_id, "not_relevant")
            self.assertEqual(dismissed["top"][0]["arxiv_id"], strong.arxiv_id)
            self.assertEqual(dismissed["ignored"][-1]["arxiv_id"], weak.arxiv_id)

    def test_custom_profile_from_config_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "radar.toml").write_text(
                '[profile]\nsite_title = "Number Theory Radar"\n'
                '[search]\nkeywords = ["prime gaps"]\n',
                encoding="utf-8",
            )
            app = create_app(root=root)
            page = app.test_client().get("/")
            self.assertIn("Number Theory Radar", page.get_data(as_text=True))
            self.assertEqual(app.config["RADAR_SERVICE"].settings.keywords, ["prime gaps"])


if __name__ == "__main__":
    unittest.main()
