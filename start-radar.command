#!/bin/zsh
cd "$(dirname "$0")" || exit 1

if [[ ! -x ".venv/bin/python" ]]; then
  echo "The local Python environment is missing. Run the installation steps in README.md first."
  read "?Press Return to close."
  exit 1
fi

echo "Starting Spectral Geometry Radar…"
echo "Leave this window open while using the dashboard. Press Control-C to stop it."
.venv/bin/python -m arxiv_radar web
