import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from arxiv_radar.config import Settings
from arxiv_radar.feedback import FeedbackStore
from arxiv_radar.models import Paper


def sample_paper(arxiv_id="2606.1"):
    now = datetime.now(timezone.utc)
    return Paper(
        "Random hyperbolic surfaces",
        ["A. Geometer"],
        arxiv_id,
        "We study the geometry and spectrum of a random hyperbolic surface.",
        "math.DG",
        ["math.DG", "math.SP"],
        now,
        now,
        "https://arxiv.org/pdf/2606.1",
        "https://arxiv.org/abs/2606.1",
    )


class FeedbackTests(unittest.TestCase):
    def test_useful_feedback_learns_positive_topic_adjustment(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FeedbackStore(Path(folder) / "feedback.json", Settings())
            paper = sample_paper()
            store.record(paper, "useful")
            adjustment, evidence = store.adjustment(sample_paper("2606.2"))
            self.assertGreater(adjustment, 0)
            self.assertTrue(evidence)

    def test_irrelevant_feedback_learns_negative_topic_adjustment(self):
        with tempfile.TemporaryDirectory() as folder:
            store = FeedbackStore(Path(folder) / "feedback.json", Settings())
            paper = sample_paper()
            store.record(paper, "not_relevant")
            adjustment, _ = store.adjustment(sample_paper("2606.2"))
            self.assertLess(adjustment, 0)

    def test_very_relevant_feedback_is_stronger_than_useful(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            useful = FeedbackStore(Path(first) / "feedback.json", Settings())
            very = FeedbackStore(Path(second) / "feedback.json", Settings())
            useful.record(sample_paper(), "useful")
            very.record(sample_paper(), "very_relevant")
            self.assertGreater(very.adjustment(sample_paper("2606.2"))[0], useful.adjustment(sample_paper("2606.2"))[0])
