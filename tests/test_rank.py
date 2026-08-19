import unittest
from datetime import datetime, timezone

from arxiv_radar.config import Settings
from arxiv_radar.models import Paper
from arxiv_radar.rank import label_for_score, score_paper

NOW = datetime(2026, 6, 21, tzinfo=timezone.utc)


def paper(title: str, abstract: str, authors=None, categories=None) -> Paper:
    return Paper(title, authors or ["A. Author"], "2606.12345", abstract, "math.SP", categories or ["math.SP"], NOW, NOW, "https://arxiv.org/pdf/2606.12345", "https://arxiv.org/abs/2606.12345")


class RankTests(unittest.TestCase):
    def test_direct_steklov_paper_scores_highly(self):
        result = score_paper(paper("Sharp Steklov eigenvalue bounds", "We prove an optimal inequality and rigidity theorem for manifolds with boundary."), Settings(), now=NOW)
        self.assertEqual(result.topic, 40)
        self.assertGreaterEqual(result.importance, 18)
        self.assertEqual(result.proximity, 10)
        self.assertGreaterEqual(result.total, 78)

    def test_famous_author_does_not_overcome_irrelevant_content(self):
        result = score_paper(paper("A combinatorial identity", "We count lattice colourings.", authors=["S. Yau"], categories=["math.CO"]), Settings(), now=NOW)
        self.assertGreater(result.author_network, 0)
        self.assertLess(result.total, 40)

    def test_exact_phrase_outweighs_broad_category(self):
        specific = score_paper(paper("Dirichlet-to-Neumann maps", "A spectral convergence theorem."), Settings(), now=NOW)
        broad = score_paper(paper("Curvature tensors", "A construction in differential geometry.", categories=["math.DG"]), Settings(), now=NOW)
        self.assertGreater(specific.total, broad.total)

    def test_plural_topic_terms_are_recognised(self):
        result = score_paper(paper("Optimisation of Laplace eigenvalues", "We construct extremal metrics."), Settings(), now=NOW)
        self.assertGreaterEqual(result.topic, 34)

    def test_random_hyperbolic_surfaces_receive_strong_geometric_score(self):
        result = score_paper(paper("Random hyperbolic surfaces", "We prove an asymptotic result on the geometry of a random surface.", categories=["math.DG", "math.PR"]), Settings(), now=NOW)
        self.assertGreaterEqual(result.topic, 35)
        self.assertGreaterEqual(result.total, 60)

    def test_steklov_average_is_not_mistaken_for_steklov_spectrum(self):
        result = score_paper(paper("A parabolic regularity theorem", "We use a slanted Steklov average and prove a gap bound.", categories=["math.AP"]), Settings(), now=NOW)
        self.assertLess(result.topic, 20)

    def test_machine_learning_spectral_geometry_phrase_is_downweighted(self):
        result = score_paper(paper("Spectral geometry of transformer representations", "We analyse singular values in a vision model.", categories=["cs.LG"]), Settings(), now=NOW)
        self.assertLessEqual(result.topic, 15)
        self.assertLess(result.total, 40)

    def test_machine_learning_spectral_geometry_in_math_category_is_still_downweighted(self):
        result = score_paper(paper("Optimisation for transformers", "We study the spectral geometry of language model training.", categories=["math.OC"]), Settings(), now=NOW)
        self.assertLess(result.total, 40)

    def test_minimal_surfaces_rank_above_generic_differential_geometry(self):
        minimal = score_paper(paper("Minimal surfaces and harmonic maps", "We prove a compactness theorem.", categories=["math.DG"]), Settings(), now=NOW)
        generic = score_paper(paper("Connections on a manifold", "We construct a geometric tensor.", categories=["math.DG"]), Settings(), now=NOW)
        self.assertGreater(minimal.total, generic.total)

    def test_new_author_signals_are_recognised(self):
        for author in ["Laura Monk", "Sugata Mondal", "Bram Petri", "Dorin Bucur", "Ilaria Fragalà"]:
            with self.subTest(author=author):
                result = score_paper(paper("A combinatorial identity", "We count objects.", authors=[author], categories=["math.CO"]), Settings(), now=NOW)
                self.assertGreater(result.author_network, 0)

    def test_bucur_fragala_mixed_laplacian_paper_ranks_as_relevant(self):
        result = score_paper(
            paper(
                "Concavity and hot spots in elliptic problems under mixed boundary conditions",
                "We study the first Laplacian eigenfunction and prove Brunn-Minkowski inequalities.",
                authors=["Dorin Bucur", "Ilaria Fragalà"],
                categories=["math.AP"],
            ),
            Settings(),
            now=NOW,
        )
        self.assertGreaterEqual(result.topic, 34)
        self.assertGreaterEqual(result.author_network, 9)
        self.assertGreaterEqual(result.total, 60)

    def test_mixed_laplacian_hot_spot_result_is_very_relevant_on_content_alone(self):
        result = score_paper(
            paper(
                "Concavity and hot spots in elliptic problems under mixed boundary conditions",
                "We prove strict log-concavity of the first Laplacian eigenfunction, show there exists a unique hot spot, and establish Brunn--Minkowski inequalities for the first mixed Laplacian eigenvalue.",
                authors=["Anonymous Author"],
                categories=["math.AP"],
            ),
            Settings(),
            now=NOW,
        )
        self.assertEqual(result.author_network, 0)
        self.assertGreaterEqual(result.total, 70)


    def test_labels(self):
        self.assertEqual(label_for_score(85), "Must read")
        self.assertEqual(label_for_score(70), "Very relevant")
        self.assertEqual(label_for_score(55), "Worth skimming")
        self.assertEqual(label_for_score(40), "Possibly relevant")
        self.assertEqual(label_for_score(39), "Ignore unless time permits")
