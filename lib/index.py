"""Stage 3: chunk -> Chroma vectors + FTS5 rows.

meta.json binds the embedding model to the vectors it produced, so the query
side can never drift from the build side -- the same discipline the reference
vectordb project uses.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.embeddings import Embeddings

from lib.config import DATA_DIR, PROJECT_ROOT, STORES_DIR, pick_device
from lib.fts import build_fts


def _year(date: str | None) -> int:
    if not date:
        return 0
    try:
        return datetime.fromisoformat(date).year
    except ValueError:
        return 0


def chunk_records(
    records: list[dict],
    thread_of: dict[str, str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    out: list[dict] = []
    for rec in records:
        body = (rec.get("body") or "").strip()
        if not body:
            continue
        for i, piece in enumerate(splitter.split_text(body)):
            out.append(
                {
                    "chunk_id": f"{rec['id']}#{i}",
                    "text": piece,
                    "message_id": rec["message_id"],
                    "thread_id": thread_of.get(rec["id"], ""),
                    "date": rec.get("date") or "",
                    "year": _year(rec.get("date")),
                    "from_email": rec.get("from_email", ""),
                    "from_name": rec.get("from_name", ""),
                    "subject": rec.get("subject", ""),
                    # Chroma metadata and FTS columns both want scalars
                    "entities": " ".join(rec.get("entities") or []),
                }
            )
    return out


def write_meta(
    store_dir: str | Path,
    name: str,
    description: str,
    embedding_model: str,
    source_path: str | Path | None,
    ontology_version: str,
) -> dict:
    store = Path(store_dir)
    store.mkdir(parents=True, exist_ok=True)
    sha = ""
    if source_path and Path(source_path).exists():
        digest = hashlib.sha256()
        with open(source_path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                digest.update(block)
        sha = digest.hexdigest()
    meta = {
        "name": name,
        "description": description,
        # A property of the built vectors, not a runtime knob.
        "embedding_model": embedding_model,
        "normalize": True,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": sha,
        "ontology_version": ontology_version,
    }
    (store / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def _build_embeddings(embedding_model: str, device: str, batch_size: int):
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True, "batch_size": batch_size},
    )


class _OomSafeEmbeddings(Embeddings):
    """Wraps HuggingFaceEmbeddings; falls back on CUDA OOM instead of trusting
    the caching allocator's silent free-and-retry.

    The allocator recovering from a transient OOM by itself produces correct
    output but no signal that anything was wrong -- a build that limped
    through on retries looks identical in the logs to one that had headroom
    to spare. This makes the fallback explicit: halve the batch size and
    retry, and if it still won't fit at batch_size=1, drop to CPU. Every step
    prints what it did, because a silent fallback (e.g. quietly finishing an
    hour-long build on CPU) is worse than a crash.
    """

    def __init__(self, embedding_model: str, device: str, batch_size: int):
        self.embedding_model = embedding_model
        self.device = device
        self.batch_size = batch_size
        self._inner = _build_embeddings(embedding_model, device, batch_size)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import torch

        device, batch_size = self.device, self.batch_size
        inner = self._inner
        while True:
            try:
                result = inner.embed_documents(texts)
                # Persist even on a no-fallback call: harmless when
                # unchanged, and required so a degradation from an earlier
                # call (see below) isn't the only path that writes self.
                self.device, self.batch_size, self._inner = device, batch_size, inner
                return result
            except torch.cuda.OutOfMemoryError as exc:
                if device == "cuda" and batch_size > 1:
                    batch_size = max(batch_size // 2, 1)
                    print(
                        f"[index] CUDA OOM ({exc}); retrying at "
                        f"device={device} batch_size={batch_size}"
                    )
                elif device == "cuda":
                    device, batch_size = "cpu", 16
                    print(
                        "[index] CUDA OOM persists at batch_size=1; "
                        f"falling back to device={device} batch_size={batch_size}"
                    )
                else:
                    raise
                # Release every reference to the failed model -- both the
                # loop-local `inner` and self._inner -- *before* emptying
                # the CUDA cache. Freeing the cache while either still
                # points at the OOM'd model reclaims nothing, and
                # _build_embeddings would then load a second model
                # alongside the first, worsening the pressure we're trying
                # to relieve. Order matters: drop references, then free,
                # then rebuild.
                inner = None
                self._inner = None
                torch.cuda.empty_cache()
                inner = _build_embeddings(self.embedding_model, device, batch_size)
                # Write the degraded state back to self immediately (not
                # just on eventual success) so it survives across calls to
                # this instance -- Chroma's local client caps batches at
                # 5,461, so a large `from_documents` call invokes
                # embed_documents more than once on the same instance, and
                # a later call must resume at the degraded device/batch
                # size instead of re-attempting CUDA from scratch.
                self.device, self.batch_size, self._inner = device, batch_size, inner

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)


# langchain_chroma's default collection name. Named explicitly so the reset
# below can target it rather than hoping the default never changes.
_COLLECTION = "langchain"


def reset_collection(store_dir: Path) -> None:
    """Drop any existing vector collection in `store_dir`.

    `Chroma.from_documents` APPENDS to whatever is already persisted, so
    without this a rebuild adds a second copy of every chunk instead of
    replacing it. That failure is invisible from the outside -- the FTS table
    is rebuilt each time and stays correct, `meta.json` is rewritten, and no
    error is raised -- but it corrupts ranking: duplicates occupy several
    slots of the same k-window, so RRF sums one chunk's rank contribution
    repeatedly and the candidate pool holds a fraction of the intended
    distinct documents. Three `build.py index` runs had left this store with
    26,565 vectors for 8,855 chunks.
    """
    import chromadb

    if not (store_dir / "chroma.sqlite3").exists():
        return
    client = chromadb.PersistentClient(path=str(store_dir))
    if _COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(_COLLECTION)


def _embed_into_chroma(store_dir: Path, chunks: list[dict], embedding_model: str) -> None:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    docs = [
        Document(
            page_content=c["text"],
            metadata={k: v for k, v in c.items() if k != "text"},
        )
        for c in chunks
    ]
    device = pick_device()
    # Chroma's HNSW insert runs at ~46 docs/s, ~30x slower than embedding
    # (measured ~1,377 docs/s on this card at batch 64) -- so the GPU sits
    # idle for most of the build regardless of batch size, and a smaller
    # batch costs almost nothing in wall-clock. Measured peak CUDA memory:
    # batch 32 ~795MB, batch 16 ~549MB. This 6.1GB card also drives the
    # desktop session, which alone can leave as little as ~3.3GB free, so
    # batch 64's ~232MB-per-step allocations were a warning away from a hard
    # failure. Batch 16 buys headroom that costs nothing; _OomSafeEmbeddings
    # is the backstop if headroom disappears anyway.
    batch_size = 16
    embeddings = _OomSafeEmbeddings(embedding_model, device, batch_size)
    reset_collection(store_dir)
    print(f"[index] embedding {len(docs)} chunks on {device} (batch_size={batch_size})")
    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(store_dir),
        collection_name=_COLLECTION,
        collection_metadata={"hnsw:space": "cosine"},
    )
    verify_collection(store_dir, len(docs))


def verify_collection(store_dir: Path, expected: int) -> None:
    """Fail loudly if the vector store did not receive every chunk.

    Chroma's local client caps an insert at 5,461 rows, so a large build is
    committed in several batches and an interruption leaves a store truncated
    at a batch boundary. The count is a plausible-looking number rather than
    zero, every other artifact is intact -- the FTS table is complete,
    meta.json is written -- and searches keep returning results, just from a
    fraction of the corpus. Two builds died that way today, one leaving 0
    vectors and one leaving exactly 5,461 of 8,855.

    Batching itself is harmless: it is an insert mechanism and does not touch
    what gets embedded. What was missing was anyone checking the total
    afterwards.
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(store_dir))
    actual = client.get_collection(_COLLECTION).count()
    if actual != expected:
        raise RuntimeError(
            f"{store_dir.name}: vector store holds {actual:,} of {expected:,} "
            "chunks. The build did not complete -- re-run it rather than "
            "querying a partial index."
        )


def episode_chunks(episodes: list[dict]) -> list[dict]:
    """One chunk per episode. `entities` is exactly the kind of field BM25 is
    good at, so it gets its own FTS column.

    Indexes `entities_extension` alongside `entities`: the CRM-family
    identifiers (FRBRoo F3, CRMsci S4, CRMgeo SP6, CRMarchaeo A8, ...) that
    validate_entities() keeps separately from core CRM ids. 135 of 883
    episodes carry only extension ids -- omitting them here would make those
    episodes unfindable by the identifiers they are actually about.
    """
    from lib.episodes import episode_text

    out = []
    for ep in episodes:
        text = episode_text(ep)
        if not text.strip():
            continue
        entities = " ".join((ep.get("entities") or []) + (ep.get("entities_extension") or []))
        out.append(
            {
                "chunk_id": ep["episode_id"],
                "episode_id": ep["episode_id"],
                "thread_id": ep["thread_id"],
                "topic": ep.get("topic", ""),
                "outcome": ep.get("outcome", ""),
                "entities": entities,
                "text": text,
            }
        )
    return out


def _episode_fts_rows(chunks: list[dict]) -> list[dict]:
    """Reshape episode chunks into build_fts row dicts.

    `subject` carries FTS weight 2.0, so it must hold a genuine title --
    `topic` -- never `outcome`. `outcome` is one of a handful of enum words
    ("decided", "unresolved", "informational", ...), and putting it in a
    weighted column let a query containing the literal word "decided" or
    "unresolved" score against it by accident, with nothing to do with the
    episode's actual subject matter. Pulled out of build_episode_index so
    the mapping is testable without paying for a real embedding build.
    """
    return [
        {"chunk_id": c["chunk_id"], "message_id": c["episode_id"],
         "thread_id": c["thread_id"], "subject": c["topic"],
         "from_name": "", "body": c["text"], "entities": c["entities"]}
        for c in chunks
    ]


def build_episode_index(cfg: dict, episodes: list[dict]) -> dict:
    chunks = episode_chunks(episodes)
    store_dir = STORES_DIR / f"{cfg['name']}-episodes"
    store_dir.mkdir(parents=True, exist_ok=True)

    rows = build_fts(store_dir / "fts.sqlite3", _episode_fts_rows(chunks))
    _embed_into_chroma(store_dir, chunks, cfg["embedding_model"])

    onto_version = json.loads((DATA_DIR / "ontology.json").read_text())["version"]
    write_meta(
        store_dir, f"{cfg['name']}-episodes",
        f"Episode summaries for {cfg['description']}",
        cfg["embedding_model"], None, onto_version,
    )
    return {"episodes": len(chunks), "fts_rows": rows, "store": str(store_dir)}


def document_chunks(records: list[dict]) -> list[dict]:
    """One chunk per data/documents.jsonl record -- declarations and
    narrative pieces are already chunked by lib.documents.chunk_document, so
    this only reshapes fields for the FTS row and the Chroma metadata, both
    of which need scalars: `section_path` (a list) is joined with " > ", and
    a narrative's `concept_id` (None) becomes "" since Chroma metadata
    rejects None outright.

    `entities` merges `entities` and `entities_historical` into one
    space-joined string, the same way episode_chunks merges its extension
    ids -- a normative document is exactly the kind of text BM25's entities
    column (weight 4.0) should be able to find either flavour of identifier
    in.
    """
    out: list[dict] = []
    for rec in records:
        text = (rec.get("text") or "").strip()
        if not text:
            continue
        entities = " ".join((rec.get("entities") or []) + (rec.get("entities_historical") or []))
        out.append(
            {
                "chunk_id": rec["chunk_id"],
                "doc_id": rec["doc_id"],
                "doc_title": rec["doc_title"],
                "cite": rec["cite"],
                "kind": rec["kind"],
                "concept_id": rec.get("concept_id") or "",
                "section_path": " > ".join(rec.get("section_path") or []),
                "heading": rec.get("heading") or "",
                "entities": entities,
                "text": text,
            }
        )
    return out


def build_document_index(cfg: dict, records: list[dict]) -> dict:
    """Index data/documents.jsonl into its own store, `stores/{name}-docs/`.

    Mirrors build_episode_index's shape (a second FTS table + Chroma
    collection alongside the message store) and its discipline for the FTS
    `subject` column (weight 2.0): it gets `heading` here, a genuine title,
    the same way build_episode_index uses `topic` rather than pressing some
    other field (e.g. the enum-valued `outcome`) into service.
    """
    chunks = document_chunks(records)
    store_dir = STORES_DIR / f"{cfg['name']}-docs"
    store_dir.mkdir(parents=True, exist_ok=True)

    rows = build_fts(store_dir / "fts.sqlite3", [
        {"chunk_id": c["chunk_id"], "message_id": c["doc_id"],
         "thread_id": c["concept_id"], "subject": c["heading"],
         "from_name": "", "body": c["text"], "entities": c["entities"]}
        for c in chunks
    ])
    _embed_into_chroma(store_dir, chunks, cfg["embedding_model"])

    onto_version = json.loads((DATA_DIR / "ontology.json").read_text())["version"]
    write_meta(
        store_dir, f"{cfg['name']}-docs",
        f"Reference documents for {cfg['description']}",
        cfg["embedding_model"], None, onto_version,
    )
    return {"chunks": len(chunks), "fts_rows": rows, "store": str(store_dir)}


def build_message_index(cfg: dict, records: list[dict], threads: dict) -> dict:
    thread_of = {
        mid: tid for tid, t in threads.items() for mid in t["message_ids"]
    }
    chunks = chunk_records(
        records, thread_of, cfg["chunk_size"], cfg["chunk_overlap"]
    )
    store_dir = STORES_DIR / cfg["name"]
    store_dir.mkdir(parents=True, exist_ok=True)

    rows = build_fts(store_dir / "fts.sqlite3", [
        {k: c[k] for k in
         ("chunk_id", "message_id", "thread_id", "subject", "from_name", "entities")}
        | {"body": c["text"]}
        for c in chunks
    ])
    _embed_into_chroma(store_dir, chunks, cfg["embedding_model"])

    onto_version = json.loads((DATA_DIR / "ontology.json").read_text())["version"]
    write_meta(
        store_dir, cfg["name"], cfg["description"], cfg["embedding_model"],
        PROJECT_ROOT / cfg["mbox"], onto_version,
    )
    return {"documents": len(records), "chunks": len(chunks), "fts_rows": rows,
            "store": str(store_dir)}
