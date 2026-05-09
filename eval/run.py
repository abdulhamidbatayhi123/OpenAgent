"""
MedMind — Eval Harness

Runs each question in eval/questions.jsonl through the live orchestrator
and computes:
  - Grounding rate     : fraction grounded (when expected to be grounded)
  - Refusal rate       : fraction refused (when expected to refuse)
  - Hallucinated cites : citations that don't map to a returned source
  - Urgency match      : urgency falls in the expected set
  - Keyword recall     : at least one expected keyword appears in the answer
  - Per-skill timings  : mean of analyze / retrieve / reason / verify / format

Run from the project root after `python scripts/ingest.py`:
    python eval/run.py
    python eval/run.py --limit 10
    python eval/run.py --out eval/results.jsonl
"""

import argparse
import json
import re
import sys
import statistics
import time
from pathlib import Path

# Make the backend importable when running from project root.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))

from pipeline.orchestrator import Orchestrator  # noqa: E402


CITE_RE = re.compile(r"\[S(\d+)\]")


def load_questions(path: Path, limit: int | None) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if limit:
        rows = rows[:limit]
    return rows


def evaluate_one(q: dict, response: dict) -> dict:
    expect = q.get("expect", {})
    answer = response.get("answer", "") or ""
    answer_lower = answer.lower()
    sources = response.get("sources", []) or []
    grounded = bool(response.get("grounded", False))
    urgency = (response.get("urgency") or "none").lower()

    # Hallucinated citation check: every [Sx] in the answer must map to a
    # returned source (sources have labels S1..Sn).
    cited = {f"S{m}" for m in CITE_RE.findall(answer)}
    valid_labels = {(s.get("label") or "").strip() for s in sources}
    hallucinated = sorted(cited - valid_labels)

    # Refusal heuristic: orchestrator's "I don't have enough" template.
    refused = "don't have enough" in answer_lower or "do not have enough" in answer_lower

    # Keyword recall.
    must_any = [kw.lower() for kw in expect.get("must_mention_any", [])]
    keyword_hit = (not must_any) or any(kw in answer_lower for kw in must_any)

    expected_grounded = bool(expect.get("must_be_grounded", False))
    expected_refuse = bool(expect.get("should_refuse", False))
    urgency_ok = (not expect.get("urgency_in")) or urgency in [
        u.lower() for u in expect["urgency_in"]
    ]

    return {
        "id": q.get("id"),
        "question": q.get("question"),
        "answer_chars": len(answer),
        "grounded": grounded,
        "refused": refused,
        "urgency": urgency,
        "cited_sources": sorted(cited),
        "hallucinated_citations": hallucinated,
        "expected_grounded": expected_grounded,
        "expected_refuse": expected_refuse,
        "urgency_ok": urgency_ok,
        "keyword_hit": keyword_hit,
        "grounding_match": grounded == expected_grounded,
        "refusal_match": refused == expected_refuse,
        "timings": response.get("timings", {}),
        "pipeline_time": response.get("pipeline_time", 0.0),
        "retrieval_confidence": response.get("retrieval_confidence"),
    }


def aggregate(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    timings_keys = ["analyze", "retrieve", "reason", "verify", "format"]
    mean_timings = {}
    for k in timings_keys:
        vals = [r["timings"].get(k, 0.0) for r in results if r["timings"]]
        mean_timings[k] = round(statistics.mean(vals), 3) if vals else 0.0

    def rate(predicate) -> float:
        return round(sum(1 for r in results if predicate(r)) / n, 3)

    total_hallucinated = sum(len(r["hallucinated_citations"]) for r in results)

    return {
        "n_questions": n,
        "grounding_match_rate": rate(lambda r: r["grounding_match"]),
        "refusal_match_rate": rate(lambda r: r["refusal_match"]),
        "urgency_match_rate": rate(lambda r: r["urgency_ok"]),
        "keyword_hit_rate": rate(lambda r: r["keyword_hit"]),
        "hallucinated_citations_total": total_hallucinated,
        "hallucinated_citations_per_q": round(total_hallucinated / n, 3),
        "mean_pipeline_time_s": round(
            statistics.mean(r["pipeline_time"] for r in results), 2
        ),
        "mean_timings_s": mean_timings,
    }


def print_table(results: list[dict]):
    print("\n" + "-" * 78)
    print(f"{'id':<5} {'urg':<10} {'grnd':<5} {'ref':<4} {'kw':<4} {'cites':<6} {'halluc':<7} {'time':<6}")
    print("-" * 78)
    for r in results:
        print(
            f"{r['id']:<5} {r['urgency']:<10} "
            f"{'Y' if r['grounded'] else 'N':<5} "
            f"{'Y' if r['refused'] else 'N':<4} "
            f"{'Y' if r['keyword_hit'] else 'N':<4} "
            f"{len(r['cited_sources']):<6} "
            f"{len(r['hallucinated_citations']):<7} "
            f"{r['pipeline_time']:<6.2f}"
        )
    print("-" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(HERE / "questions.jsonl"))
    ap.add_argument("--out", default=str(HERE / "results.jsonl"))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    questions = load_questions(Path(args.questions), args.limit)
    print(f"[Eval] Loaded {len(questions)} questions from {args.questions}")

    print("[Eval] Initializing orchestrator (loads ChromaDB + models)...")
    orch = Orchestrator()

    results = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as fout:
        for q in questions:
            t0 = time.time()
            try:
                response = orch.process(
                    user_message=q["question"],
                    session_id=f"eval-{q['id']}",
                )
            except Exception as e:
                print(f"[Eval] {q['id']} ERROR: {e}")
                response = {"answer": "", "grounded": False, "urgency": "none"}

            r = evaluate_one(q, response)
            r["wall_time_s"] = round(time.time() - t0, 2)
            results.append(r)
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            fout.flush()
            print(
                f"[Eval] {q['id']:<5} {r['urgency']:<10} "
                f"grnd={'Y' if r['grounded'] else 'N'} "
                f"halluc={len(r['hallucinated_citations'])} "
                f"t={r['pipeline_time']}s"
            )

    summary = aggregate(results)
    print_table(results)

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    summary_path = HERE / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[Eval] Per-question results -> {out_path}")
    print(f"[Eval] Summary              -> {summary_path}")


if __name__ == "__main__":
    main()
