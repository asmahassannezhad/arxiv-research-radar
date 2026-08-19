import unittest

from arxiv_radar.cli import build_parser


class CliTests(unittest.TestCase):
    def test_default_report_is_limited_to_ten_papers(self):
        args = build_parser().parse_args(["run"])
        self.assertEqual(args.top, 10)
        self.assertEqual(args.days, 30)

    def test_top_limit_can_be_changed(self):
        args = build_parser().parse_args(["run", "--top", "5"])
        self.assertEqual(args.top, 5)
