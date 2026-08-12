#!/usr/bin/env python3
"""Read the archive directly, bypassing every index.

This exists so evaluation questions can be written from the source material
without going through the thing being evaluated. It deliberately does NOT
import `lib.retrieve` or touch `stores/`: if a question is discovered by
searching, the search is guaranteed to find it again, and the eval measures
nothing.

    uv run python tools/read_thread.py --list 2018 2019   # index of a period
    uv run python tools/read_thread.py t0042              # one thread in full
"""

import argparse
import json
from pathlib import Path

# Resolved from this file rather than imported from lib.config, so running the
# reader needs nothing from the package under evaluation.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load():
    records = {}
    with open(DATA_DIR / "clean.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            records[rec["id"]] = rec
    threads = json.loads((DATA_DIR / "threads.json").read_text(encoding="utf-8"))
    return records, threads


def members(threads, tid, records):
    return [records[m] for m in threads[tid]["message_ids"] if m in records]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("thread_id", nargs="?")
    parser.add_argument("--list", nargs=2, metavar=("FROM", "TO"),
                        help="list threads starting in this inclusive year range")
    parser.add_argument("--min-messages", type=int, default=4)
    args = parser.parse_args()

    records, threads = load()

    if args.list:
        lo, hi = args.list
        rows = []
        for tid in threads:
            msgs = members(threads, tid, records)
            if len(msgs) < args.min_messages:
                continue
            dates = sorted(m["date"] for m in msgs if m.get("date"))
            if not dates or not (lo <= dates[0][:4] <= hi):
                continue
            rows.append((dates[0][:10], tid, len(msgs), msgs[0]["subject"][:70]))
        for start, tid, n, subject in sorted(rows):
            print(f"{tid}  {start}  {n:3d} msgs  {subject}")
        print(f"\n{len(rows)} threads with >= {args.min_messages} messages, {lo}-{hi}")
        return

    if not args.thread_id:
        raise SystemExit("give a thread id, or --list FROM TO")
    if args.thread_id not in threads:
        raise SystemExit(f"no such thread: {args.thread_id}")

    msgs = members(threads, args.thread_id, records)
    print(f"### {args.thread_id} ({len(msgs)} messages)\n")
    for i, rec in enumerate(msgs):
        print(f"--- [{i}] {rec['date'][:10]} | {rec['from_name']} "
              f"<{rec['from_email']}> | {rec['subject']} ---")
        print(rec["body"])
        print()


if __name__ == "__main__":
    main()
