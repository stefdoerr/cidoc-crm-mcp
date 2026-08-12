"""BM25 lexical index over message chunks, via SQLite FTS5.

FTS5 ships inside stdlib sqlite3, so this adds no dependency. The unicode61
tokenizer keeps `E55` and `P140` as single tokens -- exactly what an embedding
model cannot do, since it splits `E55` into a semantically empty `E` + `55`.
"""

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE VIRTUAL TABLE messages_fts USING fts5(
  chunk_id UNINDEXED, message_id UNINDEXED, thread_id UNINDEXED,
  subject, from_name, body, entities,
  tokenize = 'unicode61 remove_diacritics 2'
);
"""


def fts_escape(term: str) -> str:
    """Quote a term so FTS5 treats it as a literal, not as query syntax.

    Strips NUL and other control characters that would cause SQLite to raise
    unterminated string errors or other parsing issues.
    """
    # Strip NUL and control characters (0x00-0x1F, 0x7F)
    cleaned = "".join(c for c in term if ord(c) >= 0x20 and ord(c) != 0x7F)
    return '"' + cleaned.replace('"', '""') + '"'


def build_fts(db_path: str | Path, chunks: list[dict]) -> int:
    """(Re)build the FTS index. Returns the row count written.

    Deduplicates by chunk_id, keeping the first occurrence.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deduplicate by chunk_id, keeping first occurrence
    seen = set()
    deduped = []
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if cid not in seen:
            seen.add(cid)
            deduped.append(chunk)

    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS messages_fts")
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT INTO messages_fts "
            "(chunk_id, message_id, thread_id, subject, from_name, body, entities) "
            "VALUES (:chunk_id, :message_id, :thread_id, :subject, :from_name, "
            ":body, :entities)",
            deduped,
        )
        conn.commit()
        return conn.execute("SELECT count(*) FROM messages_fts").fetchone()[0]
    finally:
        conn.close()


def search_fts(db_path: str | Path, terms: list[str], limit: int) -> list[tuple[str, float]]:
    """OR the escaped terms; return (chunk_id, rank) best-first.

    SQLite's bm25() is negative and more-negative is better, so ascending
    `rank` is already best-first. Do not add DESC.

    Weights: entities=4.0 (curated identifiers), subject=2.0 (metadata),
    body=1.0 (content), from_name=0.0 (noise).
    """
    if not terms:
        return []
    query = " OR ".join(fts_escape(t) for t in terms if t.strip())
    if not query:
        return []
    conn = sqlite3.connect(Path(db_path))
    try:
        rows = conn.execute(
            "SELECT chunk_id, bm25(messages_fts, 0.0, 0.0, 0.0, 2.0, 0.0, 1.0, 4.0) "
            "FROM messages_fts "
            "WHERE messages_fts MATCH ? ORDER BY bm25(messages_fts, 0.0, 0.0, 0.0, 2.0, 0.0, 1.0, 4.0) LIMIT ?",
            (query, limit),
        ).fetchall()
        return [(cid, float(rank)) for cid, rank in rows]
    finally:
        conn.close()
