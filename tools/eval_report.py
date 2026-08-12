#!/usr/bin/env python3
"""Merge, score and report the blind evaluation.

Three phases, deliberately isolated:
  author  -- reads the archive via tools/read_thread.py, never the search system
  answer  -- gets only the question, may only use search.py
  judge   -- sees gold vs produced, never the archive

    uv run python tools/eval_report.py merge    # authored-*.json -> questions.json
    uv run python tools/eval_report.py report   # score answers + judgements
"""

import argparse
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"


def merge() -> None:
    """Collect the authored slices into one question set with stable ids."""
    questions = []
    for path in sorted(EVAL_DIR.glob("authored-*.json")):
        slice_name = path.stem.removeprefix("authored-")
        try:
            authored = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  SKIP {path.name}: unparseable ({exc})")
            continue
        for n, q in enumerate(authored, 1):
            missing = [f for f in ("question", "gold_answer", "key_facts", "gold_threads")
                       if not q.get(f)]
            if missing:
                print(f"  SKIP {slice_name}#{n}: missing {missing}")
                continue
            questions.append({"question_id": f"{slice_name}-q{n}", "slice": slice_name, **q})
        print(f"  {path.name}: {len(authored)} authored")

    out = EVAL_DIR / "questions.json"
    out.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")
    by_difficulty: dict[str, int] = {}
    for q in questions:
        key = q.get("difficulty", "?")
        by_difficulty[key] = by_difficulty.get(key, 0) + 1
    print(f"\n{len(questions)} questions -> {out}")
    print(f"difficulty: {by_difficulty}")


def report() -> None:
    questions = {q["question_id"]: q
                 for q in json.loads((EVAL_DIR / "questions.json").read_text())}
    answers, judgements = {}, {}
    for path in EVAL_DIR.glob("answer-*.json"):
        try:
            a = json.loads(path.read_text(encoding="utf-8"))
            answers[a["question_id"]] = a
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"  unreadable {path.name}: {exc}")
    for path in EVAL_DIR.glob("judged-*.json"):
        try:
            for j in json.loads(path.read_text(encoding="utf-8")):
                judgements[j["question_id"]] = j
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"  unreadable {path.name}: {exc}")

    rows = []
    for qid, q in sorted(questions.items()):
        a = answers.get(qid)
        j = judgements.get(qid)
        gold = set(q["gold_threads"])
        cited = set((a or {}).get("cited_threads") or [])
        rows.append({
            "id": qid,
            "difficulty": q.get("difficulty", "?"),
            # Retrieval is scored separately from answering: the system can
            # surface the right thread and still be summarised badly, and it
            # can reach a right-sounding answer off the wrong thread.
            "retrieved": bool(gold & cited),
            "found": bool((a or {}).get("found")),
            "verdict": (j or {}).get("verdict", "unjudged"),
            "answered": a is not None,
        })

    total = len(rows)
    print(f"\n{'id':22} {'diff':11} {'retrieved':10} {'found':6} verdict")
    print("-" * 68)
    for r in rows:
        print(f"{r['id']:22} {r['difficulty']:11} "
              f"{'yes' if r['retrieved'] else 'NO':10} "
              f"{'yes' if r['found'] else 'no':6} {r['verdict']}")

    def pct(n: int) -> str:
        return f"{n}/{total} ({100 * n // max(total, 1)}%)"

    print(f"\nanswered:            {pct(sum(r['answered'] for r in rows))}")
    print(f"gold thread reached: {pct(sum(r['retrieved'] for r in rows))}")
    print(f"claimed found:       {pct(sum(r['found'] for r in rows))}")
    verdicts: dict[str, int] = {}
    for r in rows:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    print(f"verdicts:            {verdicts}")

    by_diff: dict[str, list] = {}
    for r in rows:
        by_diff.setdefault(r["difficulty"], []).append(r)
    print("\nby difficulty:")
    for diff, group in sorted(by_diff.items()):
        correct = sum(1 for r in group if r["verdict"] == "correct")
        reached = sum(1 for r in group if r["retrieved"])
        print(f"  {diff:12} {len(group):2} questions  "
              f"retrieved {reached}/{len(group)}  correct {correct}/{len(group)}")

    # The failure that matters most: an answer asserted without the evidence
    # for it. Confident, wrong, and indistinguishable from a good answer to
    # anyone who does not already know.
    bluffs = [r for r in rows if r["found"] and not r["retrieved"]]
    if bluffs:
        print(f"\nANSWERED WITHOUT REACHING A GOLD THREAD ({len(bluffs)}):")
        for r in bluffs:
            print(f"  {r['id']}  verdict={r['verdict']}")




def bundle(answer_prefix: str = "answer", out_prefix: str = "tojudge",
           only: str | None = None) -> None:
    """Write per-judge input files: question + gold + produced answer.

    Judges get no archive access and no retrieval metadata -- not the queries
    run, not the cited threads. Only whether the answer matches the gold.

    `answer_prefix` selects which run to grade, so a re-run can be scored
    against the same golds without overwriting the first run's record.
    """
    questions = json.loads((EVAL_DIR / "questions.json").read_text())
    if only:
        questions = [q for q in questions if q.get("difficulty") == only]
    per_judge, batch = 8, []
    for q in questions:
        path = EVAL_DIR / f"{answer_prefix}-{q['question_id']}.json"
        produced = json.loads(path.read_text()) if path.exists() else {}
        batch.append({
            "question_id": q["question_id"],
            "question": q["question"],
            "gold_answer": q["gold_answer"],
            "key_facts": q["key_facts"],
            "difficulty": q.get("difficulty"),
            "produced_answer": produced.get("answer", "(no answer file produced)"),
            "produced_found": produced.get("found", False),
        })
    for n in range(0, len(batch), per_judge):
        chunk = batch[n : n + per_judge]
        out = EVAL_DIR / f"{out_prefix}-{n // per_judge:02d}.json"
        out.write_text(json.dumps(chunk, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {out.name}: {len(chunk)} questions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["merge", "bundle", "report"])
    parser.add_argument("--answers", default="answer", help="answer file prefix")
    parser.add_argument("--out", default="tojudge", help="bundle file prefix")
    parser.add_argument("--only", default=None, help="restrict to one difficulty")
    args = parser.parse_args()
    if args.action == "bundle":
        bundle(args.answers, args.out, args.only)
    else:
        {"merge": merge, "report": report}[args.action]()
