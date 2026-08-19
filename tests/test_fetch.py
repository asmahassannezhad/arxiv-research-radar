import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from arxiv_radar.config import Settings
from arxiv_radar.fetch import build_queries, fetch_recent, parse_atom
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

    def test_every_query_is_restricted_to_allowed_categories(self):
        settings = Settings(keywords=["Steklov"], author_keywords=["Dorin Bucur"])
        queries = build_queries(settings, datetime(2026, 6, 1), datetime(2026, 6, 21))
        self.assertTrue(all("cat:math.SP" in query and "cat:math.DG" in query for query in queries))
        self.assertTrue(all("cat:math.CA" not in query and "cat:gr-qc" not in query for query in queries))
        self.assertTrue(any('au:"Dorin Bucur"' in query for query in queries))

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
