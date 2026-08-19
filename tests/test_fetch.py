import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from arxiv_radar.config import Settings
from arxiv_radar.fetch import build_queries, fetch_between, fetch_recent, parse_atom
from arxiv_radar.models import Paper


class FetchTests(unittest.TestCase):
    def test_parse_atom_entry(self):
        xml = '''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry><id>http://arxiv.org/abs/2606.12345v2</id><updated>2026-06-20T10:00:00Z</updated><published>2026-06-19T10:00:00Z</published><title> A spectral paper </title><summary> An abstract. </summary><author><name>A. Author</name></author><arxiv:primary_category term="math.SP"/><category term="math.SP"/><link href="https://arxiv.org/abs/2606.12345v2" rel="alternate"/><link title="pdf" href="https://arxiv.org/pdf/2606.12345v2" rel="related"/></entry></feed>'''
        result = parse_atom(xml)
        self.assertEqual(result[0].arxiv_id, "2606.12345")
        self.assertEqual(result[0].primary_category, "math.SP")
        self.assertEqual(result[0].title, "A spectral paper")

    def test_old_style_arxiv_id_is_preserved(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry><id>http://arxiv.org/abs/math/0601001v3</id><updated>2026-06-20T10:00:00Z</updated><published>2006-01-01T10:00:00Z</published><title>Old identifier</title><summary>Abstract.</summary><author><name>A. Author</name></author><arxiv:primary_category term="math.SP"/><category term="math.SP"/></entry></feed>'''
        self.assertEqual(parse_atom(xml)[0].arxiv_id, "math/0601001")

    def test_query_is_a_single_category_bounded_search(self):
        settings = Settings(keywords=["Steklov"], author_keywords=["Dorin Bucur"])
        queries = build_queries(settings, datetime(2026, 6, 1), datetime(2026, 6, 21))
        self.assertEqual(len(queries), 1)
        query = queries[0]
        self.assertIn("cat:math.SP", query)
        self.assertIn("cat:math.DG", query)
        self.assertIn("submittedDate:[202606010000 TO 202606210000]", query)
        self.assertNotIn("cat:math.CA", query)
        self.assertNotIn("gr-qc", query)

    def test_fetch_discards_keyword_hit_outside_allowed_categories(self):
        now = datetime.now(timezone.utc)
        outside = Paper("Spectral geometry for transformers", ["A. Author"], "2606.9", "Machine learning.", "cs.LG", ["cs.LG"], now, now, "pdf", "abs")
        settings = Settings(keywords=["spectral geometry"], max_results=10, request_delay_seconds=0)
        with patch("arxiv_radar.fetch._request", return_value=[outside]):
            self.assertEqual(fetch_recent(settings, now=now), [])

    def test_fetch_discards_crosslist_with_disallowed_primary_category(self):
        now = datetime.now(timezone.utc)
        crosslisted = Paper("A graph spectrum paper", ["A. Author"], "2606.10", "Spectral geometry of graphs.", "math.CO", ["math.CO", "math.SP"], now, now, "pdf", "abs")
        settings = Settings(keywords=["spectral geometry"], max_results=10, request_delay_seconds=0)
        with patch("arxiv_radar.fetch._request", return_value=[crosslisted]):
            self.assertEqual(fetch_recent(settings, now=now), [])

    def test_pagination_collects_multiple_pages_and_stops_past_window(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, tzinfo=timezone.utc)

        def paper_on(identifier, dt):
            return Paper(identifier, ["A. Author"], identifier, "abstract", "math.SP", ["math.SP"], dt, dt, "pdf", "abs")

        full_page = [paper_on(f"p{i}", datetime(2026, 6, 20, tzinfo=timezone.utc)) for i in range(200)]
        tail_page = [
            paper_on("recent", datetime(2026, 6, 10, tzinfo=timezone.utc)),
            paper_on("too-old", datetime(2026, 5, 20, tzinfo=timezone.utc)),
        ]
        settings = Settings(max_results=1000, request_delay_seconds=0)
        with patch("arxiv_radar.fetch._request", side_effect=[full_page, tail_page]) as request:
            result = fetch_between(settings, start=start, end=end)
        self.assertEqual(request.call_count, 2)
        ids = {paper.arxiv_id for paper in result}
        self.assertIn("recent", ids)
        self.assertNotIn("too-old", ids)
        self.assertEqual(len(result), 201)
