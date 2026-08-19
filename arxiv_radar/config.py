from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path


# ---------------------------------------------------------------------------
# Default profile.
#
# These Python defaults keep the radar working even when no ``radar.toml`` file
# is present. To adapt the radar to a different research area, edit the
# ``radar.toml`` file in the project root rather than this module — see that
# file and the README for guidance.
# ---------------------------------------------------------------------------

SITE_TITLE = "Spectral Geometry Radar"
EYEBROW = "Research desk"
TAGLINE = "A quiet filter for the noisy edge of arXiv."

CATEGORIES = ["math.SP", "math.DG", "math.AP", "math.MG", "math-ph"]

KEYWORDS = [
    "spectral geometry", "Steklov", "Dirichlet-to-Neumann", "Laplace eigenvalue",
    "Laplacian eigenvalue", "Laplacian eigenfunction", "mixed boundary conditions",
    "hot spots",
    "eigenvalue optimisation", "eigenvalue optimization", "extremal metric",
    "harmonic map", "minimal surface", "free boundary minimal surface",
    "hyperbolic surface", "random hyperbolic surface", "random surface",
    "hyperbolic geometry", "hyperbolic manifold", "finite area", "nodal set",
    "nodal domain", "Cheeger inequality", "Jammes", "Escobar", "orbifold",
    "Hodge Laplacian", "geometric PDE", "capacity", "Robin",
    "boundary eigenvalue problem", "p-Laplacian", "Paneitz", "biharmonic map",
    "conformal geometry", "geometric analysis", "Riemannian geometry",
    "Teichmüller space", "moduli space", "spectral convergence", "inverse spectral",
]

AUTHOR_KEYWORDS = [
    "Antoine Métras", "Hélène Perrin", "Iosif Polterovich", "Alexandre Girouard",
    "Bruno Colbois", "Ahmad El Soufi", "Nadirashvili", "Karpukhin", "Kokarev",
    "Vinokurov", "Jammes", "Escobar", "Otal", "Rosas", "Schoen", "Wolpert",
    "Yau", "Dodziuk", "Randol", "Polymerakis", "Levitin", "Capoferri", "Cakoni",
    "Rudnick", "Fraser", "Brendle", "Rupflin", "Monk", "Laura Monk",
    "Sugata Mondal", "Bram Petri", "Dorin Bucur", "Ilaria Fragalà",
    "Ilaria Fragala", "Sher",
]

SCORING_WEIGHTS = {
    "topic": 40,
    "importance": 30,
    "author_network": 10,
    "freshness": 10,
    "proximity": 10,
}

# Phrases that most strongly identify the research area, with their topic weights.
HIGH_TOPIC = {
    "steklov eigenvalue": 38, "steklov spectrum": 38, "steklov problem": 36,
    "steklov eigenfunction": 36, "dirichlet-to-neumann": 38, "spectral geometry": 36,
    "laplace eigenvalue": 34, "laplace eigenvalues": 34,
    "laplacian eigenvalue": 34, "laplacian eigenfunction": 34,
    "eigenvalue optimisation": 34, "eigenvalue optimization": 34,
    "eigenvalues optimisation": 34, "eigenvalues optimization": 34,
    "boundary eigenvalue problem": 32, "extremal metric": 32,
}

# Closely related phrases with medium topic weights.
MEDIUM_TOPIC = {
    "random hyperbolic surface": 35, "random surface": 28,
    "hyperbolic surface": 31, "hyperbolic geometry": 28, "hyperbolic manifold": 28,
    "hodge laplacian": 27,
    "nodal set": 25, "nodal domain": 25, "inverse spectral": 25,
    "spectral convergence": 25, "free boundary minimal surface": 31,
    "p-laplacian": 22, "robin": 21, "orbifold": 20, "geometric pde": 20,
    "mixed boundary conditions": 27, "hot spot": 25,
    "minimal surface": 25, "harmonic map": 22, "geometric analysis": 24,
    "riemannian geometry": 18, "teichmüller space": 22, "moduli space": 17,
    "paneitz": 17,
    "cheeger inequality": 24, "jammes inequality": 26, "escobar problem": 24,
    "biharmonic map": 17, "conformal geometry": 16, "capacity": 16,
}

# Phrases that indicate a paper sits very close to the reader's own work.
PROXIMATE = [
    "steklov", "dirichlet-to-neumann", "laplace eigenvalue", "laplacian eigen",
    "eigenvalue optim", "extremal metric", "hyperbolic surface", "spectral convergence",
]

# Result language that suggests a paper is likely to be important.
IMPACT_TERMS = {
    "open problem": 8, "sharp": 6, "optimal": 6, "rigidity": 6, "compactness": 5,
    "asymptotic": 5, "weyl law": 7, "gap": 4, "maximizer": 5, "minimizer": 5,
    "existence": 3, "convergence": 4, "counterexample": 7, "classification": 5,
    "first": 3, "settle": 8, "resolve": 8, "new method": 6,
    "brunn-minkowski": 6, "brunn--minkowski": 6, "log-concave": 4,
    "unique hot spot": 4,
}

# Context words used to damp false positives from other fields (e.g. a
# machine-learning paper that mentions "spectral geometry" only in passing).
MACHINE_LEARNING_CONTEXT = [
    "transformer", "machine learning", "neural", "training data",
    "language model", "imagenet",
]
GEOMETRIC_CONTEXT = [
    "manifold", "surface", "riemannian", "hyperbolic", "laplace",
    "eigenvalue", "boundary spectrum", "metric",
]


@dataclass(slots=True)
class Settings:
    # Presentation
    site_title: str = SITE_TITLE
    eyebrow: str = EYEBROW
    tagline: str = TAGLINE
    # Search
    categories: list[str] = field(default_factory=lambda: CATEGORIES.copy())
    keywords: list[str] = field(default_factory=lambda: KEYWORDS.copy())
    author_keywords: list[str] = field(default_factory=lambda: AUTHOR_KEYWORDS.copy())
    # Scoring
    scoring_weights: dict[str, int] = field(default_factory=lambda: SCORING_WEIGHTS.copy())
    high_topic: dict[str, int] = field(default_factory=lambda: HIGH_TOPIC.copy())
    medium_topic: dict[str, int] = field(default_factory=lambda: MEDIUM_TOPIC.copy())
    proximate: list[str] = field(default_factory=lambda: PROXIMATE.copy())
    impact_terms: dict[str, int] = field(default_factory=lambda: IMPACT_TERMS.copy())
    machine_learning_context: list[str] = field(default_factory=lambda: MACHINE_LEARNING_CONTEXT.copy())
    geometric_context: list[str] = field(default_factory=lambda: GEOMETRIC_CONTEXT.copy())
    minimum_score: int = 40
    days: int = 30
    max_results: int = 2000
    # Paths
    output_path: Path = Path("report.md")
    database_path: Path = Path(".arxiv-radar/seen.sqlite3")
    feedback_path: Path = Path("feedback.json")
    web_state_path: Path = Path(".arxiv-radar/web-state.json")
    request_delay_seconds: float = 3.0


DEFAULT_SETTINGS = Settings()

CONFIG_FILENAME = "radar.toml"


def load_settings(root: Path | None = None) -> Settings:
    """Return settings from ``radar.toml`` if present, otherwise the defaults.

    Only keys that appear in the file override the defaults, so a partial or
    minimal config file is perfectly valid.
    """
    root = root or Path.cwd()
    config_path = root / CONFIG_FILENAME
    if not config_path.exists():
        return Settings()
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return Settings()

    profile = data.get("profile", {})
    search = data.get("search", {})
    scoring = data.get("scoring", {})

    overrides: dict = {}

    def take(source: dict, key: str, target: str) -> None:
        if key in source:
            overrides[target] = source[key]

    take(profile, "site_title", "site_title")
    take(profile, "eyebrow", "eyebrow")
    take(profile, "tagline", "tagline")

    take(search, "categories", "categories")
    take(search, "keywords", "keywords")
    take(search, "authors", "author_keywords")
    take(search, "days", "days")
    take(search, "max_results", "max_results")
    take(search, "minimum_score", "minimum_score")

    take(scoring, "weights", "scoring_weights")
    take(scoring, "high_topic", "high_topic")
    take(scoring, "medium_topic", "medium_topic")
    take(scoring, "proximate", "proximate")
    take(scoring, "impact_terms", "impact_terms")
    take(scoring, "machine_learning_context", "machine_learning_context")
    take(scoring, "geometric_context", "geometric_context")

    return replace(Settings(), **overrides)
