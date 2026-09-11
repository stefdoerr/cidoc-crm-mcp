"""Skip guards shared across the suite.

`data/` and `stores/` are git-ignored and shipped out of band, so a fresh
clone has neither. Most tests that need them already say so and skip -- 55
of them -- but nineteen did not, and a test that needs a file it does not
check for fails instead of skipping. `git clone && uv sync && pytest` was
nineteen red failures about nothing.

`needs_corpus` is the same condition mcp_server._first_missing_archive_file
uses to decide whether to register the archive layer at all: one definition
of "the archive is here", rather than a second one drifting alongside it.

It also covers the tests that need a FULL data/ontology.json. That artifact
is built from tracked sources, so a bare clone has one -- but the ontology
stage folds in whatever the corpus contributes (the historical bucket from
clean.jsonl, the three concepts only 7.3.2 declares from documents.jsonl)
and silently skips it when absent, so without the archive it is real and
smaller. Hence fetch, then ontology, then pytest -- which is the order the
README gives and the CI workflow runs.
"""

import pytest

from lib.config import DATA_DIR

_ARCHIVE_FILES = ("clean.jsonl", "threads.json", "documents.jsonl")

_missing = [f for f in _ARCHIVE_FILES if not (DATA_DIR / f).exists()]

needs_corpus = pytest.mark.skipif(
    bool(_missing),
    reason=f"archive not fetched (no data/{_missing[0] if _missing else ''}); "
           "run `uv run python build.py fetch --no-vectors` and then "
           "`build.py ontology`, in that order",
)
