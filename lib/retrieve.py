"""Interface-agnostic retrieval. No CLI or HTTP types appear in any signature,
so the future MCP wrapper is a thin adapter over these same functions."""

import difflib
import json
import re
import sqlite3
from functools import cached_property
from pathlib import Path

from lib.config import DATA_DIR, STORES_DIR, load_config, pick_device
from lib.expand import build_lexicon, expand_query
from lib.fts import search_fts


def rrf_fuse(rankings: list[list[str]], k: int = 60,
             weights: list[float] | None = None) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion.

    BM25 scores and cosine similarities are incommensurable, so we fuse
    positions rather than values -- which means there is nothing to tune.

    The returned score is derived purely from rank position (1/(k+rank),
    summed across rankings). With a single ranking -- i.e. a `bm25`- or
    `vector`-only search -- it collapses to a function of rank alone, so it
    carries no information about match strength and is only meaningful for
    ordering *within* one result set, never as a confidence value and never
    across different queries or modes.

    `weights` scales each ranking's contribution. It defaults to equal, which
    is the right prior when neither retriever is known to be more reliable.
    Pass it only where there is a reason, not to tune a number until one
    query looks better.
    """
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError(
            f"{len(weights)} weights for {len(rankings)} rankings"
        )
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: -item[1])


# ---- quote verification --------------------------------------------------
#
# The blind modelling-advice evaluation resolved 297 citations mechanically
# and found zero invented identifiers -- but two quotes were still wrong: a
# thread cited for a line no participant in it ever wrote, and a phrase
# attributed to a thread that never uses that wording. Existence being
# checked said nothing about containment. This is the containment check.
#
# Typographic quotes and hard-wrapped lines mean a phrase copied accurately
# from a message will still differ byte-for-byte from that message's stored
# text, so matching normalises whitespace, quote characters and case before
# comparing. It does NOT fuzzy-match beyond that: a paraphrase must fail, or
# the check stops meaning anything. `_closest_in_text` is the deliberately
# separate, deliberately weaker fallback -- diagnostic only, never able to
# turn a miss into a hit.

_QUOTE_TRANS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'",  # single quotes, prime
    "“": '"', "”": '"', "„": '"', "″": '"',  # double quotes, prime
})


# A space before a full stop or comma is a typo, not a difference in wording,
# and it is everywhere in this corpus: 21% of messages and 38% of document
# chunks contain one. Anyone quoting such a sentence writes it correctly --
# "instances of this class." for a source reading "instances of this class ."
# -- and collapsing whitespace alone leaves that space in place, so the quote
# fails and an accurate citation is reported as fabricated. That happened to a
# real answer: two verbatim sentences from t0872 were flagged as unfound
# because the source has "class ." mid-sentence.
#
# This cannot launder a paraphrase into a match. Two strings that differ only
# by whitespace adjacent to punctuation are the same words in the same order.
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:?!])")


def _normalize_ws_quotes(text: str) -> str:
    """Typographic quotes -> ASCII, any run of whitespace (including the
    hard-wrap newlines mailing-list text is full of) -> a single space, and
    whitespace sitting before punctuation dropped.

    Case is deliberately preserved here: matching lower-cases separately, but
    the context returned to a caller should read as the source actually
    capitalised it, not shout in lowercase.
    """
    collapsed = re.sub(r"\s+", " ", text.translate(_QUOTE_TRANS))
    return _SPACE_BEFORE_PUNCT.sub(r"\1", collapsed).strip()


# "A ... B" and "A [editorial note] B" are ordinary quoting conventions, not
# evidence of invention, and an answer following the house style ("quote
# sparingly") is the one most likely to elide. Without this an accurate,
# correctly-elided quotation is reported as fabricated -- which happened to a
# citation of the Monterey 2002 minutes whose two halves are both verbatim.
#
# Fragments must appear IN ORDER and without overlapping. That is what stops
# the loosening from being a licence to reorder a source: "A ... B" must not
# match a text where B precedes A, because that quotation would misrepresent
# what was said. Each fragment also has to carry real weight, so trivially
# short ones are not treated as an elision at all.
_ELISION = re.compile(r"\s*(?:\.\.\.|…|\[[^\]]*\])\s*")
_MIN_ELISION_WORDS = 4


def _find_elided(norm_lower: str, phrase_norm: str) -> tuple[int, int] | None:
    """Span covering an elided phrase whose fragments occur in order."""
    fragments = [f for f in _ELISION.split(phrase_norm) if f.strip()]
    if len(fragments) < 2:
        return None
    if any(len(f.split()) < _MIN_ELISION_WORDS for f in fragments):
        return None
    start = end = -1
    cursor = 0
    for fragment in fragments:
        found = norm_lower.find(fragment.lower(), cursor)
        if found == -1:
            return None
        if start == -1:
            start = found
        end = found + len(fragment)
        cursor = end
    return (start, end)


def _find_in_text(text: str, phrase: str, pad: int = 60) -> dict | None:
    """Case-insensitive, whitespace/quote-normalised substring search.

    Handles elided quotations ("A ... B") by requiring every fragment to be
    present and in order; see `_find_elided`.

    Returns the matched span (in its original casing) and a window of
    context around it, or None -- never a bare bool, so a caller can show
    what it actually found.
    """
    norm = _normalize_ws_quotes(text)
    phrase_norm = _normalize_ws_quotes(phrase)
    if not phrase_norm:
        return None
    idx = norm.lower().find(phrase_norm.lower())
    if idx == -1:
        span = _find_elided(norm.lower(), phrase_norm)
        if span is None:
            return None
        idx, end = span
        lo, hi = max(0, idx - pad), min(len(norm), end + pad)
        return {
            "match": norm[idx:end],
            "context": (
                ("…" if lo > 0 else "") + norm[lo:idx]
                + "**" + norm[idx:end] + "**"
                + norm[end:hi] + ("…" if hi < len(norm) else "")
            ),
        }
    end = idx + len(phrase_norm)
    lo, hi = max(0, idx - pad), min(len(norm), end + pad)
    return {
        "match": norm[idx:end],
        "context": (
            ("…" if lo > 0 else "") + norm[lo:idx]
            + "**" + norm[idx:end] + "**"
            + norm[end:hi] + ("…" if hi < len(norm) else "")
        ),
    }


def _closest_in_text(text: str, phrase: str, pad: int = 60) -> dict | None:
    """The best the source actually contains, when an exact match fails.

    Purely diagnostic: `score` is the fraction of the phrase found as one
    contiguous run of characters in the text, via the longest common
    substring (not the alignment `find_quote` uses to decide FOUND, and
    never promoted into one). `autojunk=False` matters here -- difflib's
    default marks frequently-repeated characters (spaces, above ~1% of a
    long text) as "popular" and excludes them from matches, which on prose
    this short would silently shrink or relocate the match.
    """
    norm = _normalize_ws_quotes(text).lower()
    phrase_norm = _normalize_ws_quotes(phrase).lower()
    if not norm or not phrase_norm:
        return None
    sm = difflib.SequenceMatcher(None, phrase_norm, norm, autojunk=False)
    block = sm.find_longest_match(0, len(phrase_norm), 0, len(norm))
    if block.size == 0:
        return None
    display = _normalize_ws_quotes(text)  # same offsets, original casing
    lo, hi = max(0, block.b - pad), min(len(display), block.b + block.size + pad)
    return {
        "score": round(block.size / len(phrase_norm), 3),
        "excerpt": (
            ("…" if lo > 0 else "") + display[lo:block.b]
            + "**" + display[block.b:block.b + block.size] + "**"
            + display[block.b + block.size:hi] + ("…" if hi < len(display) else "")
        ),
    }


_THREAD_ID_RE = re.compile(r"^t\d{4}$")
_EPISODE_ID_RE = re.compile(r"^t\d{4}-e\d+$")


# The 7.3.2 declaration's own paragraph styles (`CRM First Order Logic`,
# `CRM Full Path`, ...) are what delimited these sections at parse time; by
# the time a declaration reaches documents.jsonl it is one newline-joined
# `text` blob, so these header strings are what mark section boundaries when
# reading it back. Kept in sync with lib.index's whitelist-is-wrong lesson by
# being a boundary marker only, never a filter: anything between two known
# headers is absorbed into the open section regardless of what it contains.
_CRM732_SECTION_HEADERS = frozenset({
    "Subclass of:", "Subproperty of:", "Superclass of:", "Superproperty of:",
    "Domain:", "Range:", "Quantification:", "Quantificatio\xa0n:",
    "Scope note:", "Properties:", "Full path:", "Examples:", "Example:",
    "In first-order logic:",
})


def _declaration_section(text: str, header: str) -> list[str]:
    """Non-blank lines under `header` in a 7.3.2 declaration's flattened
    text, up to the next known section header or the end of the block.

    Returns every line, not just the first: a declaration can carry more
    than one full path (P1, P49, P51, P53, P152 each shortcut two distinct
    paths), and an axiom set is naturally one line per axiom.
    """
    lines = text.split("\n")
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []
    end = start
    while end < len(lines) and lines[end].strip() not in _CRM732_SECTION_HEADERS:
        end += 1
    return [ln.strip() for ln in lines[start:end] if ln.strip()]


_VALID_MODES = ("hybrid", "bm25", "vector")

# Naming an identifier is a lookup, and BM25 has no way to express that. Its
# length normalisation actively works against it: querying the document store
# for "P2 has type" returned the P125 and P3 declarations above P2's own,
# because their shorter fields score the token "P2" higher than P2's own
# longer ones. A declaration is the definitive source for the identifier it
# declares, so an exact match is promoted ahead of the fused ranking instead
# of competing inside it.
_QUERY_ID = re.compile(r"\b([EP]\d{1,3})(?:\.\d)?i?\b", re.IGNORECASE)


# A result page is a budget. Two hits from one thread can be worth showing
# (different authors, different points); a third never is, because the whole
# thread is one `search.py thread <id>` away.
#
# Justified on diversity, not recall: measured over the smoke set this cap
# changes no case's rank at all. What it changes is what a page contains --
# "teacher student relationship" went from six distinct threads across ten
# slots to nine. Kept for that, and guarded by a test asserting the diversity
# property rather than a retrieval one, because that is what it actually does.
MAX_HITS_PER_THREAD = 2


def vector_weight_for(query: str) -> float:
    """How much to favour the dense ranking over BM25 for this query.

    When a query names a CRM identifier, BM25 is indispensable -- an exact
    "E22" match is the strongest signal available -- and the two rankings
    fuse evenly. When it names none, BM25 has nothing to match exactly and
    its ordering is mostly noise, so the dense side carries twice the weight.

    This started life inside `search_documents`, where an even fusion had put
    "Modelling principles > Minimality" above E36 Visual Item and P62 depicts
    for "how do I model a photograph of a building". `search` fused evenly for
    much longer than it should have.

    Measured over the smoke set plus the case that exposed it (thread t0426,
    where Martin Doerr writes "Master-client should be activity mediated:
    Apprenticeship"), varying weighting and message-dedup independently:

        even, no dedup   t0426 missed entirely   <- the old behaviour
        even + dedup     rank 9
        weighted only    rank 9
        weighted + dedup rank 8

    So this weighting and the message-dedup below are each *independently*
    sufficient to surface it, and neither is load-bearing given the other --
    removing this alone does not fail any test. Both are kept because they fix
    different faults (a noisy ranking, and a wasted result budget) and together
    they rank it highest, but the honest claim for this function alone is
    "helps", not "fixes". Every smoke case stays at rank 1 throughout.

    NOT applied to `search_episodes`: measured there it changes nothing on
    three queries and demotes "asymmetric social relations" from rank 1 to 2.
    Episode summaries run 102-2,536 chars, so BM25's length normalisation --
    the whole reason this weighting exists -- has nothing to bite on.
    """
    return 1.0 if _QUERY_ID.search(query) else 2.0
_FALLBACK_POOL_CEILING = 20_000
_DOCUMENT_KINDS = {"declaration", "narrative", "issue", "minutes", "principles"}
# The reference model proper. `docs` defaults to these so the spec is
# never outranked by the decision record simply for being smaller.
#
# The margin this protects keeps widening. When only the issue pages shared
# the store the split was 3,002 non-spec chunks against 374 spec ones, and
# they took every top-5 slot until this default existed. Adding the meeting
# minutes brings another 3,644, so the spec is now 374 of 7,020 -- five per
# cent of the store. `--kind minutes` and `--kind issue` reach the rest
# deliberately; nothing reaches it by accident.
SPEC_KINDS = {"declaration", "narrative"}


# Reference apparatus: bibliographies, "see also" lists, further reading.
# Indexed like everything else, and they answer nothing -- a Works Cited
# entry is a list of author names and titles, which is exactly the shape
# BM25 rewards. Measured: 43 chunks of 7,086 (0.6% of the corpus, 54 KB) and
# they took two of the top five slots on "grave goods burial ship burial
# archaeology", pushing out the modelling guidance the query was for. An
# agent modelling the Sutton Hoo helmet hit this and reported the tool as
# returning nothing useful.
#
# Excluded by default rather than dropped from the corpus: the chunks are
# real text a reader may legitimately want, and `include_apparatus=True`
# still returns them. Rebuilding documents.jsonl to remove them would also
# mean re-embedding 7,086 chunks, which is hours for 0.6%.
_APPARATUS_MARKERS = frozenset({
    "works cited", "bibliography", "references", "further reading",
    "see also",
})


def _is_apparatus(rec: dict) -> bool:
    where = " > ".join(rec.get("section_path") or []) or (rec.get("heading") or "")
    lowered = where.lower()
    return any(marker in lowered for marker in _APPARATUS_MARKERS)


class Retriever:
    def __init__(self, archive: str = "crm-sig") -> None:
        self.cfg = load_config(archive)
        self.store_dir = STORES_DIR / archive
        self.episode_store_dir = STORES_DIR / f"{archive}-episodes"
        self.document_store_dir = STORES_DIR / f"{archive}-docs"
        # No concept store: the ontology is served whole, not retrieved (spec §4).
        # get_concept() is a dict lookup over data/ontology.json.
        # Keyed by store_dir (message store vs episode store are different
        # dirs) so a long-lived MCP process pays the ~6-12s Chroma + embedding
        # model load once per store, not once per search() call.
        self._chroma_cache: dict[Path, object] = {}
        # Keyed by what actually determines the vectors, so the three stores
        # -- messages, episodes, docs -- share one loaded model instead of
        # holding three copies of it. Measured across all three: 1.34GB
        # resident and 24s to load before, 0.52GB and 9.5s after. Two stores
        # built with different models still get different embedders, because
        # the model name is part of the key and comes from each store's own
        # meta.json -- the binding that keeps query-time and build-time from
        # drifting is upstream of this cache, not bypassed by it.
        self._embedder_cache: dict[tuple, object] = {}

    # ---- lazily-loaded data ------------------------------------------------

    @cached_property
    def ontology(self) -> dict:
        return json.loads((DATA_DIR / "ontology.json").read_text(encoding="utf-8"))

    @cached_property
    def lexicon(self) -> dict:
        return build_lexicon(self.ontology, self.cfg["ontology"]["stop_labels"])

    @cached_property
    def messages(self) -> dict[str, dict]:
        # clean.jsonl is the cleaned mbox: 143MB, gitignored, shipped out of
        # band from this repository. A fresh clone -- the environment this
        # tool is published for -- has no such file, and `concept` reaches
        # this property (via by_hash) just to count how often the archive
        # mentions an identifier. Before this guard, that lookup raised
        # FileNotFoundError and `search.py concept E22` died on a bare
        # traceback in exactly the checkout the ontology half must serve.
        # The sibling lazy properties `episodes` and `documents` already
        # treat an absent file as empty; this matches their shape.
        path = DATA_DIR / "clean.jsonl"
        if not path.exists():
            return {}
        out = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                out[rec["message_id"]] = rec
        return out

    @cached_property
    def by_hash(self) -> dict[str, dict]:
        return {r["id"]: r for r in self.messages.values()}

    @cached_property
    def threads(self) -> dict:
        # threads.json is built from the archive and gitignored, shipped out
        # of band -- same story as clean.jsonl (see `messages` above). A
        # fresh clone has no such file, and `get_thread` (and so
        # `search.py thread <id>`) reaches this property directly. Before
        # this guard it raised FileNotFoundError with a bare traceback,
        # found while verifying Task 1's fix to `messages` (task-1-report.md)
        # but out of that task's scope because it is an archive property, not
        # an ontology one -- it belongs here, where what needs which data is
        # the whole subject. `messages`, `episodes` and `documents` already
        # return empty rather than raise; this matches their shape.
        path = DATA_DIR / "threads.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @cached_property
    def thread_of(self) -> dict[str, str]:
        return {m: t for t, v in self.threads.items() for m in v["message_ids"]}

    @cached_property
    def episodes(self) -> list[dict]:
        path = DATA_DIR / "episodes.jsonl"
        if not path.exists():
            return []
        return [json.loads(ln) for ln in open(path, encoding="utf-8")]

    @cached_property
    def episodes_by_id(self) -> dict[str, dict]:
        return {e["episode_id"]: e for e in self.episodes}

    @cached_property
    def issues(self) -> dict[str, dict]:
        path = DATA_DIR / "issues.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def get_issue(self, issue_id: int | str) -> dict | None:
        """One SIG issue: its official status and every thread that cites it.

        The archive's own unit of decision. Threading by reply-chain scatters
        a single issue across years -- 332 runs over ten threads from 2017 to
        2022 -- so a debate that was settled reads as several that trail off.
        The register carries the status; this joins it to the discussion.
        """
        return self.issues.get(str(issue_id).lstrip("#"))

    @cached_property
    def documents(self) -> dict[str, dict]:
        path = DATA_DIR / "documents.jsonl"
        if not path.exists():
            return {}
        out = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                out[rec["chunk_id"]] = rec
        return out

    def _chroma(self, store_dir: Path):
        # Cached per store_dir: constructing this loads the embedding model
        # and opens the Chroma client, ~6-12s. Without the cache, every
        # hybrid/vector search() call on a long-lived instance (an MCP
        # server, a smoke-test suite) would pay that cost again.
        if store_dir in self._chroma_cache:
            return self._chroma_cache[store_dir]

        # Quiet the load before it happens. Importing these configures
        # logging handlers that emit at INFO on first use, and the result --
        # measured at 218 lines for one `docs` query, mostly httpx HEAD
        # requests to huggingface.co and a progress bar -- lands on stderr.
        # It is protocol-safe (the MCP server's stdout stays pure JSON-RPC,
        # verified) but it is not harmless: an agent driving the server
        # through a client that passes stderr through read the wall of text
        # as a failure and reported the call as broken when it had succeeded.
        #
        # Set before the imports, because huggingface_hub reads the
        # environment at import time and attaches its handler then. Only
        # these libraries' own loggers are touched; nothing here changes what
        # this project logs.
        import logging
        import os

        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        for noisy in ("httpx", "httpcore", "huggingface_hub", "filelock",
                      "sentence_transformers", "transformers", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        # A missing vector store and a missing vector library are the same
        # situation to a user -- "I fetched with --no-vectors" -- and the
        # bare ImportError names neither the cause nor the remedy. Both
        # fixes are one line, so say them.
        try:
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "vector search needs the `archive` extra, which is not "
                "installed: uv sync --extra archive. To search without it, "
                'pass mode="bm25" -- BM25 covers the whole archive and needs '
                "no embedding model."
            ) from exc

        if not (store_dir / "meta.json").exists():
            raise RuntimeError(
                f"no vector store at {store_dir} -- fetched with "
                "--no-vectors? Run `build.py fetch` for the full corpus, or "
                'pass mode="bm25" to search the full-text index alone.'
            )

        # The model comes from meta.json, never from config: that binding is
        # what stops query-time and build-time from drifting. Device does not
        # need to match the build -- it changes throughput, not the vectors.
        # Caching the built store must not become a second path that
        # bypasses this: each store_dir still reads its own meta.json the
        # first time it's requested, and only that already-bound store is
        # what gets reused thereafter.
        meta = json.loads((store_dir / "meta.json").read_text(encoding="utf-8"))
        key = (meta["embedding_model"], meta.get("normalize", True), pick_device())
        embeddings = self._embedder_cache.get(key)
        if embeddings is None:
            embeddings = HuggingFaceEmbeddings(
                model_name=key[0],
                model_kwargs={"device": key[2]},
                encode_kwargs={"normalize_embeddings": key[1]},
            )
            self._embedder_cache[key] = embeddings
        store = Chroma(persist_directory=str(store_dir), embedding_function=embeddings)
        self._chroma_cache[store_dir] = store
        return store

    def warm(self) -> list[str]:
        """Load every vector store now, so no user query pays for it.

        The load is ~9.5s across the three stores and happens on whichever
        search asks first. In a long-lived server that is one unlucky user;
        in a container that restarts, it is one unlucky user per restart.
        Calling this before the port is bound moves the cost into startup,
        where a healthcheck can hide it.

        Stores whose vectors are absent are skipped rather than raising:
        `build.py fetch --no-vectors` leaves `meta.json` behind (it is how
        the model binding is checked) but no `chroma.sqlite3`, and a
        BM25-only deployment is a supported one. A store whose vectors ARE
        present and whose library is not still raises -- that is a broken
        install, and boot is the right place to find out.
        """
        loaded = []
        for store_dir in (self.store_dir, self.episode_store_dir,
                          self.document_store_dir):
            if not (store_dir / "chroma.sqlite3").exists():
                continue
            self._chroma(store_dir)
            loaded.append(store_dir.name)
        return loaded

    @cached_property
    def fts_total(self) -> int:
        """Total rows in this store's FTS index.

        The natural ceiling for widening a filtered search's candidate pool:
        once k_each reaches this, `search_fts` is already being asked for
        every row it has, so widening further cannot surface more matches.
        """
        conn = sqlite3.connect(self.store_dir / "fts.sqlite3")
        try:
            return conn.execute("SELECT count(*) FROM messages_fts").fetchone()[0]
        finally:
            conn.close()

    def _pool_ceiling(self, mode: str) -> int:
        """The largest k_each worth requesting for `mode`.

        hybrid asks both retrievers for the same k_each, so its ceiling is
        the larger of the two totals -- past that point, at least one
        retriever is already returning everything it has.
        """
        ceilings = []
        if mode in ("hybrid", "bm25"):
            ceilings.append(self.fts_total)
        if mode in ("hybrid", "vector"):
            try:
                ceilings.append(self._chroma(self.store_dir)._collection.count())
            except AttributeError:
                # langchain_chroma internals changed shape; fall back to a
                # safety net rather than crash the widen loop.
                ceilings.append(_FALLBACK_POOL_CEILING)
        return max(ceilings, default=0)

    # ---- search ------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
        expand: bool = True,
        from_email: str | None = None,
        after: int | None = None,
        before: int | None = None,
        entity: str | None = None,
    ) -> list[dict]:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Unknown mode {mode!r}; expected one of {_VALID_MODES}"
            )
        added = (
            expand_query(query, self.lexicon, self.cfg["ontology"]["id_pattern"])
            if expand
            else []
        )
        filtering = bool(from_email or after or before or entity)

        def rec_passes(rec: dict) -> bool:
            if from_email and from_email.lower() not in rec.get("from_email", ""):
                return False
            year = int((rec.get("date") or "0")[:4] or 0)
            if after and year < after:
                return False
            if before and year > before:
                return False
            if entity and entity not in (
                rec.get("entities", []) + rec.get("entities_historical", [])
            ):
                return False
            return True

        def fused_candidates(k_each: int) -> list[tuple[str, float]]:
            rankings: list[list[str]] = []
            weights: list[float] = []
            if mode in ("hybrid", "bm25"):
                terms = query.split() + added
                if entity:
                    terms.append(entity)
                rankings.append([cid for cid, _ in search_fts(
                    self.store_dir / "fts.sqlite3", terms, k_each)])
                weights.append(1.0)
            if mode in ("hybrid", "vector"):
                vector_query = query + ((" " + " ".join(added)) if added else "")
                store = self._chroma(self.store_dir)
                docs = store.similarity_search(vector_query, k=k_each)
                rankings.append([d.metadata["chunk_id"] for d in docs])
                weights.append(vector_weight_for(query))
                self._chunk_meta = {d.metadata["chunk_id"]: d for d in docs}
            return rrf_fuse(rankings, weights=weights)

        def build_results(fused: list[tuple[str, float]]) -> list[dict]:
            results = []
            # Results are chunk-level, so without these two guards a single
            # long message can occupy several slots and a single busy thread
            # most of them. Measured on "teacher student relationship": six
            # distinct threads across ten slots, four of them spent on
            # repeats, which is what pushed the answer off the page. The
            # reader's next move is `search.py thread <id>`, so a second hit
            # from a thread already listed buys almost nothing; the third
            # buys nothing at all.
            seen_messages: set[str] = set()
            per_thread: dict[str, int] = {}
            for chunk_id, score in fused:
                msg_hash = chunk_id.split("#")[0]
                rec = self.by_hash.get(msg_hash)
                if rec is None:
                    continue
                if not rec_passes(rec):
                    continue
                if msg_hash in seen_messages:
                    continue
                thread_id = self.thread_of.get(msg_hash, "")
                if thread_id and per_thread.get(thread_id, 0) >= MAX_HITS_PER_THREAD:
                    continue
                seen_messages.add(msg_hash)
                per_thread[thread_id] = per_thread.get(thread_id, 0) + 1
                results.append(
                    {
                        "chunk_id": chunk_id,
                        "score": score,
                        "message_id": rec["message_id"],
                        "thread_id": self.thread_of.get(msg_hash, ""),
                        "date": rec.get("date"),
                        "from_name": rec.get("from_name"),
                        "subject": rec.get("subject"),
                        "snippet": (rec.get("body") or "")[:300],
                        "entities": rec.get("entities", []),
                    }
                )
                if len(results) >= top_k:
                    break
            return results

        k_each = top_k * 3
        results = build_results(fused_candidates(k_each))

        # A narrow filter can starve this fixed-size pool: rankings are
        # capped at k_each per retriever, and filter-matching documents that
        # don't happen to fall inside that window are simply gone -- there
        # is no widen-and-retry without this loop. Unfiltered searches never
        # enter it, so they are unaffected: exactly the one call above.
        if filtering and len(results) < top_k:
            ceiling = self._pool_ceiling(mode)
            while len(results) < top_k and k_each < ceiling:
                # Both retrievers are fast once the store is loaded (FTS:
                # sub-millisecond; Chroma: ~0.02s once _chroma is cached), so
                # a few extra rounds cost nothing. Capping at the retriever's
                # own total is what guarantees this loop terminates even
                # when genuinely fewer than top_k documents satisfy the
                # filter -- k_each cannot grow past `ceiling`, so the `while`
                # condition eventually goes false regardless of match count.
                k_each = min(k_each * 2, ceiling)
                results = build_results(fused_candidates(k_each))

        return results

    def get_message(self, message_id: str) -> dict | None:
        return self.messages.get(message_id) or self.by_hash.get(message_id)

    def get_thread(self, thread_id: str) -> list[dict]:
        thread = self.threads.get(thread_id)
        if not thread:
            return []
        return [self.by_hash[m] for m in thread["message_ids"] if m in self.by_hash]

    def search_episodes(self, query: str, top_k: int = 5, mode: str = "hybrid") -> list[dict]:
        """Hybrid FTS + vector search over the episode-summary store, the
        same rrf_fuse-based fusion search_documents uses.

        build_episode_index writes an FTS row for every episode (see
        episode_chunks / _episode_fts_rows), but a vector-only search here
        never read it -- so an exact identifier query, the one thing BM25
        does that an embedding model cannot, had no way to win. Fixed
        alongside the bug that made those FTS rows unsafe to trust: `subject`
        used to hold `outcome` (an enum word like "decided"), which would
        have leaked straight into this ranking once FTS was wired in.

        Unlike search_documents, weights stay equal (rrf_fuse's default).
        search_documents doubles the vector weight because a 7,405-char
        declaration loses to a short discursive section under BM25's length
        normalisation; episode summaries run 102-2,536 chars with no
        comparable long/short split, and measuring several identifier and
        conceptual queries both ways found no case where doubling changed
        the top result for the better -- so there is nothing here for that
        weighting to correct.
        """
        if not self.episode_store_dir.exists():
            return []
        if mode not in _VALID_MODES:
            raise ValueError(f"Unknown mode {mode!r}; expected one of {_VALID_MODES}")

        fts_path = self.episode_store_dir / "fts.sqlite3"

        def fused_candidates(k_each: int) -> list[tuple[str, float]]:
            rankings: list[list[str]] = []
            if mode in ("hybrid", "bm25"):
                rankings.append(
                    [cid for cid, _ in search_fts(fts_path, query.split(), k_each)]
                )
            if mode in ("hybrid", "vector"):
                store = self._chroma(self.episode_store_dir)
                docs = store.similarity_search(query, k=k_each)
                rankings.append([d.metadata["episode_id"] for d in docs])
            return rrf_fuse(rankings)

        fused = fused_candidates(top_k * 3)
        by_id = {e["episode_id"]: e for e in self.episodes}
        results = []
        for episode_id, _ in fused:
            if episode_id in by_id:
                results.append(by_id[episode_id])
            if len(results) >= top_k:
                break
        return results

    def search_documents(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
        kind: str | set[str] | None = None,
        include_apparatus: bool = False,
    ) -> list[dict]:
        """Hybrid FTS + vector search over the reference-document store.

        Not vector-only, and neither is search_episodes: a normative
        specification is full of exact identifiers ("P2", "E55") and section
        titles, which is precisely what BM25 is good at and an embedding
        model is not (it splits "E55" into a semantically empty "E" + "55").
        Fuses the two rankings with the same rrf_fuse used by search().

        `kind` restricts to "declaration" or "narrative" -- "show me the
        rule" and "show me the definition" are different questions. Returns
        full data/documents.jsonl records (plus a fused `score`), not Chroma
        metadata, the same way search()'s build_results reads through to
        `self.by_hash` rather than trusting what got embedded.
        """
        if not self.document_store_dir.exists():
            return []
        if mode not in _VALID_MODES:
            raise ValueError(f"Unknown mode {mode!r}; expected one of {_VALID_MODES}")
        # A set, because the three kinds in this store are not peers. The
        # reference model (declaration + narrative) is normative; issue pages
        # are the SIG's decision record. Ranking them together buries the
        # spec: 3,002 issue chunks against 374 spec chunks took every top-5
        # slot for "how do I model a photograph of a building" and "when
        # should I declare a new class", which is the same blurring that made
        # documents a separate corpus from the mailing list in the first place.
        if kind is None:
            # Default to the reference model, not to everything. This module
            # is the interface-agnostic layer -- a CLI-only default would
            # leave the MCP wrapper, the eval harness and every future caller
            # inheriting the buried-spec behaviour. Pass an explicit set (or
            # _DOCUMENT_KINDS) to search the whole store.
            kind = set(SPEC_KINDS)
        if isinstance(kind, str):
            kind = {kind}
        if kind is not None:
            unknown = kind - _DOCUMENT_KINDS
            if unknown:
                raise ValueError(
                    f"Unknown document kind(s) {sorted(unknown)}; "
                    f"expected any of {sorted(_DOCUMENT_KINDS)}"
                )

        fts_path = self.document_store_dir / "fts.sqlite3"
        asked = {m.group(1).upper() for m in _QUERY_ID.finditer(query)}

        def fts_total() -> int:
            conn = sqlite3.connect(fts_path)
            try:
                return conn.execute("SELECT count(*) FROM messages_fts").fetchone()[0]
            finally:
                conn.close()

        def pool_ceiling() -> int:
            ceilings = []
            if mode in ("hybrid", "bm25"):
                ceilings.append(fts_total())
            if mode in ("hybrid", "vector"):
                try:
                    ceilings.append(self._chroma(self.document_store_dir)._collection.count())
                except AttributeError:
                    ceilings.append(_FALLBACK_POOL_CEILING)
            return max(ceilings, default=0)

        def fused_candidates(k_each: int) -> list[tuple[str, float]]:
            rankings: list[list[str]] = []
            weights: list[float] = []
            if mode in ("hybrid", "bm25"):
                rankings.append(
                    [cid for cid, _ in search_fts(fts_path, query.split(), k_each)]
                )
                weights.append(1.0)
            if mode in ("hybrid", "vector"):
                store = self._chroma(self.document_store_dir)
                docs = store.similarity_search(query, k=k_each)
                rankings.append([d.metadata["chunk_id"] for d in docs])
                # Declarations run to 7,405 chars and BM25 normalises hard by
                # length, so on a conceptual question the short discursive
                # sections outrank the long declaration that actually answers
                # it: "how do I model a photograph of a building" put
                # Modelling principles > Minimality above E36 Visual Item and
                # P62 depicts, which were correct. When the query names an
                # identifier BM25 is indispensable and the weighting stays
                # even; when it names none there is nothing for it to match
                # exactly, and its ranking is mostly noise.
                weights.append(1.0 if asked else 2.0)
            return rrf_fuse(rankings, weights=weights)

        def build_results(fused: list[tuple[str, float]]) -> list[dict]:
            scores = dict(fused)
            promoted = [
                cid for cid, rec in self.documents.items()
                if rec.get("kind") == "declaration"
                and rec.get("concept_id") in asked
                and not (kind and rec.get("kind") not in kind)
            ]
            order = promoted + [cid for cid, _ in fused if cid not in set(promoted)]
            results = []
            for chunk_id in order:
                rec = self.documents.get(chunk_id)
                if rec is None:
                    continue
                if kind and rec.get("kind") not in kind:
                    continue
                if not include_apparatus and _is_apparatus(rec):
                    continue
                results.append({**rec, "score": scores.get(chunk_id, 0.0)})
                if len(results) >= top_k:
                    break
            return results

        k_each = top_k * 3
        results = build_results(fused_candidates(k_each))

        # Same starvation guard as search(): a `kind` filter can exclude most
        # of a fixed-size candidate window, so without widening, "declaration"
        # or "narrative" alone could come back thin even when the store holds
        # plenty of matches outside that window.
        if kind and len(results) < top_k:
            ceiling = pool_ceiling()
            while len(results) < top_k and k_each < ceiling:
                k_each = min(k_each * 2, ceiling)
                results = build_results(fused_candidates(k_each))

        return results

    def get_concept(self, key: str) -> dict | None:
        onto = self.ontology
        ident = key.strip()
        # "extensions" covers the CRM family (FRBRoo, CRMsci, ...): ids v7.1.3
        # never declared at all, current in their own model's declarations or
        # known only to this archive. "property_of_property" is the fifth
        # bucket (P14.1 "in the role of" and 15 others) -- see
        # data/ontology.json.
        #
        # `.get(bucket, {})` rather than `onto[bucket]`: data/ is gitignored
        # and rebuilt by `build.py ontology`, so anyone who pulled this
        # branch without rebuilding still has a four-bucket artifact on
        # disk with no "property_of_property" key at all. A bare index
        # raised KeyError on every miss -- confirmed against a stale copy:
        # E22 worked (found before reaching the fifth bucket), but P14.1, a
        # label lookup ("Type"), and an unknown id (ZZ999) all crashed.
        # `.get` degrades that crash to a clean miss, which falls through
        # to the label lookup below and then to search.py's "No such
        # concept" plus its rebuild hint -- reporting, not swallowing.
        for bucket in ("classes", "properties", "historical", "extensions",
                       "property_of_property"):
            if ident in onto.get(bucket, {}):
                entry = dict(onto[bucket][ident])
                entry["bucket"] = bucket
                return entry
        # Allow lookup by label ("Type" -> E55).
        #
        # A label does NOT identify a property: 14 of them are shared. "consists
        # of" is P5, P9 or P45; "contains" is P10, P86, P89 or P172. This used
        # to `return self.get_concept(ids)` on the first hit of the loop and
        # discard the rest, so `concept "consists of"` answered P5 Condition
        # State with no hint that P45, the material-composition one a reader
        # almost certainly wants, also matched. A silently-chosen wrong answer
        # is the failure mode this codebase keeps rediscovering, so the other
        # candidates ride along on the entry and the caller shows them.
        matches = self.lexicon["label_to_ids"].get(ident.lower(), [])
        if matches:
            entry = self.get_concept(matches[0])
            if entry is not None and len(matches) > 1:
                entry = {**entry, "also_matches": list(matches[1:]),
                         "matched_label": ident}
            return entry
        for bucket in ("classes", "properties"):
            for entry in onto[bucket].values():
                if entry.get("label", "").lower() == ident.lower():
                    out = dict(entry)
                    out["bucket"] = bucket
                    return out
        return None

    # ---- concept dossier enrichment (Task 19) ------------------------------
    #
    # None of these three ever raise on a miss -- a concept with no siblings,
    # no 7.3.2 declaration or no narrative mentions is still a real concept,
    # so a caller treating an empty result as "this doesn't exist" would be
    # exactly the kind of confident wrongness the module already warns about
    # for the archive chronology.

    @cached_property
    def _concept_skeleton(self) -> dict[str, dict]:
        # ontology_skeleton() already inverts sub_class_of/sub_property_of
        # into a children map (see lib.ontology); reused here rather than
        # recomputed, per the corpus spec's explicit instruction.
        from lib.ontology import ontology_skeleton

        return {s["id"]: s for s in ontology_skeleton(self.ontology)}

    def concept_siblings(self, concept_id: str) -> list[dict]:
        """Other subclasses (for a class) or subproperties (for a property)
        of `concept_id`'s own parent(s) -- the discrimination aid: what a
        reader is choosing BETWEEN, not just what they chose.

        A root concept (E1: no parents) or a concept with no declared
        parent at all (many properties sit outside any subproperty chain,
        e.g. P62) correctly returns []: there is nothing else at that level
        to discriminate against. Historical and extension ids are absent
        from the skeleton entirely and also return [].
        """
        entry = self._concept_skeleton.get(concept_id)
        if not entry:
            return []
        seen = {concept_id}
        siblings = []
        for parent in entry["parents"]:
            for child in self._concept_skeleton.get(parent, {}).get("children", []):
                if child not in seen:
                    seen.add(child)
                    siblings.append(self._concept_skeleton[child])
        return siblings

    def get_declaration(self, concept_id: str) -> dict | None:
        """First-order logic and full path from the 7.3.2 declaration for
        `concept_id`, keyed as `crm732#<id>` in data/documents.jsonl.

        7.3.2 is the source for BOTH, but for different reasons. `full_path`
        genuinely has no counterpart in the v7.1.3 XML. `fol` does -- every
        one of the 241 classes and properties carries an
        `<inFirstOrderLogic>` element -- but 7.3.2 is the better rendering:
        it covers three concepts the XML does not (E100, P199, P200), writes
        a proper `∧` where 7.1.3 writes `˄`, and fixes at least one
        unbalanced bracket (`[P10(x,y) ∧ P10(y,z)] ⇒ P10(x,z)`).

        Not every current concept has one -- E38 is deprecated and 7.3.2
        dropped its declaration along with the rest of the class -- so a
        miss means "no FOL/full-path material for this id", never "this
        concept doesn't exist"; return None rather than raise.
        """
        decl = self.documents.get(f"crm732#{concept_id}")
        if decl is None:
            return None
        text = decl.get("text", "")
        return {
            "fol": _declaration_section(text, "In first-order logic:"),
            "full_path": _declaration_section(text, "Full path:"),
            "cite": decl.get("cite"),
        }

    def concept_narratives(self, concept_id: str) -> list[dict]:
        """7.3.2 narrative chunks whose extracted `entities` include
        `concept_id` -- the modelling-guidance material that discusses it,
        as distinct from its own declaration.

        Ranked by how many concepts a chunk mentions, fewest first: a chunk
        naming one or two ids is talking specifically about them; one naming
        a dozen is a broad list this concept happens to appear in. There is
        no query here to rank against relevance, so specificity is the next
        best signal. Ties break on chunk_id for a deterministic order.
        """
        matches = [
            rec for rec in self.documents.values()
            if rec.get("kind") == "narrative"
            and concept_id in (rec.get("entities") or []) + (rec.get("entities_historical") or [])
        ]
        return sorted(
            matches,
            key=lambda r: (
                len(r.get("entities") or []) + len(r.get("entities_historical") or []),
                r["chunk_id"],
            ),
        )

    # ---- quote verification -------------------------------------------------
    #
    # An answering agent reconstructs a quote from memory after reading a long
    # thread; a reviewer with full access can still be fooled into confirming
    # it. Existence and containment are both decidable, so both get checked
    # mechanically instead of trusted. `find_quote` never calls an LLM and
    # never touches Chroma -- it reads the same local JSON/JSONL this module
    # already caches, so it costs nothing beyond what a `concept` lookup does.

    def find_quote(self, source_id: str, phrase: str, context_chars: int = 60) -> dict:
        """Does `phrase` actually occur in `source_id`, and where.

        `source_id` is a thread id (`t0408`), an episode id (`t0408-e1`), a
        message id (either the mail `Message-ID` header or this archive's
        internal hash id -- whatever `get_message` accepts), or a document
        chunk id (`crm732#E55`, `crm732#s0042`). Resolved in that order,
        matching the id shapes used throughout the archive.

        Always returns a dict, never a bare bool:
          - unknown source_id: {"source_id", "source_kind": None, "found":
            False, "error"}.
          - found: {"found": True, "match", "context", ...source-specific
            fields}. Threads and episodes also carry `message_id`,
            `message_index` (1-based, matching what `search.py thread` shows)
            and `author`; documents carry `heading`/`section_path`/`cite`.
          - not found: {"found": False, "closest": {...} | None}. `closest`
            is the nearest thing actually present -- a different wording in
            the same place, or the same wording in a different place -- so a
            caller can tell a misremembered quote from a misremembered
            source. It is diagnostic only: nothing here can turn a miss into
            a hit, no matter how close the score.

        Matching is case-insensitive and normalises whitespace (hard-wrapped
        lines) and typographic quote characters, because the corpus is full
        of both and an accurately-copied quote would otherwise fail on
        formatting alone. It does not fuzzy-match past that: a paraphrase is
        supposed to fail.
        """
        source_id = source_id.strip()
        if not phrase or not phrase.strip():
            raise ValueError("phrase must not be empty")

        if _THREAD_ID_RE.fullmatch(source_id) and source_id in self.threads:
            return self._find_quote_in_thread(source_id, phrase, context_chars)
        if _EPISODE_ID_RE.fullmatch(source_id) and source_id in self.episodes_by_id:
            return self._find_quote_in_episode(source_id, phrase, context_chars)
        if "#" in source_id and source_id in self.documents:
            return self._find_quote_in_document(source_id, phrase, context_chars)
        msg = self.get_message(source_id)
        if msg is not None:
            return self._find_quote_in_message(source_id, msg, phrase, context_chars)

        return {
            "source_id": source_id,
            "source_kind": None,
            "found": False,
            "error": (
                f"unknown source id {source_id!r}: not a thread, episode, "
                "message or document chunk id in this archive"
            ),
        }

    def _search_quote_candidates(
        self, base: dict, candidates: list[tuple[int | None, dict]],
        phrase: str, pad: int,
    ) -> dict:
        """Shared by thread and episode lookup: try every candidate message
        in order, return the first exact hit, else the best diagnostic
        near-miss across all of them (not just the first candidate) so
        `closest` reflects the whole source, not an arbitrary prefix of it.
        """
        best_closest = None
        for index, rec in candidates:
            hit = _find_in_text(rec.get("body") or "", phrase, pad)
            if hit is not None:
                return {
                    **base,
                    "found": True,
                    "match": hit["match"],
                    "context": hit["context"],
                    "message_id": rec.get("message_id"),
                    "message_index": index,
                    "author": rec.get("from_name"),
                    "date": rec.get("date"),
                }
            closeness = _closest_in_text(rec.get("body") or "", phrase, pad)
            if closeness and (best_closest is None or closeness["score"] > best_closest["score"]):
                best_closest = {
                    **closeness,
                    "message_id": rec.get("message_id"),
                    "message_index": index,
                    "author": rec.get("from_name"),
                }
        return {**base, "found": False, "closest": best_closest}

    def _find_quote_in_thread(self, thread_id: str, phrase: str, pad: int) -> dict:
        msg_hashes = self.threads[thread_id]["message_ids"]
        candidates = [
            (i + 1, self.by_hash[h]) for i, h in enumerate(msg_hashes) if h in self.by_hash
        ]
        base = {"source_id": thread_id, "source_kind": "thread"}
        return self._search_quote_candidates(base, candidates, phrase, pad)

    def _find_quote_in_episode(self, episode_id: str, phrase: str, pad: int) -> dict:
        ep = self.episodes_by_id[episode_id]
        thread_id = ep.get("thread_id", "")
        # Message index is reported relative to the FULL thread, matching
        # what `search.py thread <thread_id>` displays -- an episode is a
        # subset of a thread's messages, not a numbering scheme of its own,
        # and a citation naming "message 2" should mean the same message
        # whether it was reached via the thread or via this episode.
        thread_index = {h: i + 1 for i, h in enumerate(self.threads.get(thread_id, {}).get("message_ids", []))}
        candidates = [
            (thread_index.get(h), self.by_hash[h])
            for h in ep.get("message_ids", [])
            if h in self.by_hash
        ]
        base = {"source_id": episode_id, "source_kind": "episode", "thread_id": thread_id}
        return self._search_quote_candidates(base, candidates, phrase, pad)

    def _find_quote_in_message(self, source_id: str, rec: dict, phrase: str, pad: int) -> dict:
        base = {
            "source_id": source_id,
            "source_kind": "message",
            "message_id": rec.get("message_id"),
            "author": rec.get("from_name"),
            "date": rec.get("date"),
        }
        hit = _find_in_text(rec.get("body") or "", phrase, pad)
        if hit is not None:
            return {**base, "found": True, "match": hit["match"], "context": hit["context"]}
        return {**base, "found": False, "closest": _closest_in_text(rec.get("body") or "", phrase, pad)}

    def _find_quote_in_document(self, chunk_id: str, phrase: str, pad: int) -> dict:
        rec = self.documents[chunk_id]
        base = {
            "source_id": chunk_id,
            "source_kind": "document",
            "heading": rec.get("heading"),
            "section_path": rec.get("section_path"),
            "cite": rec.get("cite"),
        }
        hit = _find_in_text(rec.get("text") or "", phrase, pad)
        if hit is not None:
            return {**base, "found": True, "match": hit["match"], "context": hit["context"]}
        return {**base, "found": False, "closest": _closest_in_text(rec.get("text") or "", phrase, pad)}
