# arXiv Research Radar

A small, transparent research radar for new arXiv papers. It searches recent
submissions in the categories and keywords you choose, removes papers reported
in earlier runs, assigns an explainable score from 0 to 100, and shows the
results either in a Markdown digest or a local web dashboard.

Every score is computed locally from a paper's title, abstract, and metadata.
**The tool uses no external AI service and needs no API key** — the ranking is
a small set of readable rules you can inspect and edit.

It ships pre-configured for spectral geometry and geometric analysis, but the
topic, title, keywords, categories, and authors are all set in a single
configuration file, so you can point it at any field on arXiv.

## What it does

- Searches the official arXiv Atom API by your categories and keyword batches.
- Enforces a hard primary-category boundary: only papers whose *primary*
  category is one you listed are kept (cross-listed papers from elsewhere are
  discarded). `math-ph` is treated as an alias of `math.MP`.
- Collects title, authors, abstract, categories, dates, arXiv ID, and links.
- Deduplicates results and keeps a local SQLite record of previously seen
  versions, so each run shows you what is new.
- Scores topic relevance (40), likely importance (30), author/network signal
  (10), freshness (10), and project proximity (10).
- In the web dashboard, learns from your feedback buttons with adjustments
  capped at ±10 points, so the transparent mathematical score stays visible.
- Treats author reputation as a small signal only: an off-topic paper cannot
  rank highly on authorship alone.

## Configuration

All the personal settings live in [`radar.toml`](radar.toml) in the project
root. Open it and edit:

- **`[profile]`** — the title, subtitle, and tagline shown in the page and
  reports.
- **`[search]`** — the arXiv `categories`, the `keywords` that define your
  topic, the `authors` you want surfaced, and the default search window.
- **`[scoring]`** *(optional)* — fine-grained phrase weights, for advanced
  tuning. Most people never need to touch this.

Every key is optional; delete a line to fall back to the built-in default. If
`radar.toml` is missing entirely, the radar still runs with its spectral
geometry defaults.

## Installation

Python 3.11 or newer is required.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Web dashboard

```bash
python -m arxiv_radar web
```

Your browser opens at `http://127.0.0.1:8765`. Press **Run radar** whenever you
want a fresh search. The dashboard keeps the best papers in one tab and every
other candidate in another.

Use **Browse → Today** for papers submitted today, or **Browse → Specific day**
to choose an exact submission date. **Recent window** keeps the rolling
7/30/60-day search.

The **Very relevant**, **Useful**, **Save later**, and **Not relevant** buttons
are stored in `feedback.json`. **Very relevant** promotes a paper into the best
matches; **Not relevant** moves it outside the cut. Both also teach
category-specific keyword preferences for future searches, capped at ±10 points.
You can change a choice later by pressing a different button.

On macOS you can instead double-click **Open Radar.app** in Finder to start the
dashboard quietly, and **Stop Radar.app** to stop it. These are optional
convenience wrappers; the command above works everywhere.

## Command-line usage

```bash
python -m arxiv_radar run --days 30
python -m arxiv_radar run --days 1 --output report.md
python -m arxiv_radar run --days 14 --min-score 55
```

The radar retrieves every paper submitted in the window (up to a generous
`--max-results` ceiling), but writes only the ten highest-scoring papers to
`report.md`. Every candidate outside the top ten is listed with its score and
ranking evidence in `ignored.md`. A longer window therefore surfaces more
papers than a shorter one.

Useful options:

- `--top N` changes the maximum number of reported papers (default: 10).
- `--max-results N` caps how many candidates are scanned in the window
  (default: 2000).
- `--min-score N` sets the score at or above which a paper gets a full report
  entry (default: 55).
- `--database PATH` changes the SQLite history file
  (default: `.arxiv-radar/seen.sqlite3`).
- `--ignored-output PATH` changes the audit report path (default: `ignored.md`).
- `--include-seen` reports previously seen papers again.

Only papers first seen in the current run, or papers whose arXiv version has
since been updated, appear by default. A successful run records the candidates
after writing the report. To rebuild a digest from scratch, use a separate
database path or `--include-seen`.

## Scoring

The ranking in [`arxiv_radar/rank.py`](arxiv_radar/rank.py) is deliberately
inspectable, and its phrase tables default to the values in
[`arxiv_radar/config.py`](arxiv_radar/config.py) (overridable from `radar.toml`):

- Exact phrases such as "Steklov" and "Dirichlet-to-Neumann" receive the
  strongest topic weights; title matches gain a small bonus.
- Closely related themes receive medium weights.
- Result language such as "sharp", "optimal", "rigidity", "Weyl law",
  "counterexample", and "open problem" contributes to likely impact.
- Known authors contribute at most 10 points.
- New submissions and substantive recent updates receive freshness credit.

Labels are: 85–100 **Must read**, 70–84 **Very relevant**, 55–69
**Worth skimming**, 40–54 **Possibly relevant**, and below 40
**Ignore unless time permits**.

The arXiv API is queried politely, with a three-second delay between searches.

## Tests

```bash
python -m unittest discover -s tests
```

## Project layout

- `radar.toml`: your editable profile, keywords, categories, and authors
- `arxiv_radar/config.py`: defaults and the config-file loader
- `arxiv_radar/fetch.py`: arXiv queries and Atom parsing
- `arxiv_radar/rank.py`: transparent score and labels
- `arxiv_radar/storage.py`: SQLite seen-paper history
- `arxiv_radar/feedback.py`: feedback storage and learned nudges
- `arxiv_radar/report.py`: Markdown rendering
- `arxiv_radar/web.py`: Flask dashboard
- `arxiv_radar/cli.py`: command-line interface
- `tests/`: ranking, feed parsing, feedback, and web tests
