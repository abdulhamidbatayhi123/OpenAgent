# MedMind — Eval Harness

A small reproducible benchmark for the multi-agent pipeline. Add or edit
questions in `questions.jsonl`; each line is one test case.

## What it measures

| Metric | What it means |
|---|---|
| `grounding_match_rate` | Fraction of questions where `grounded` matched `expect.must_be_grounded`. |
| `refusal_match_rate` | Fraction where the system correctly refused (or didn't) per `expect.should_refuse`. |
| `urgency_match_rate` | Fraction where the detected urgency falls in `expect.urgency_in`. |
| `keyword_hit_rate` | Fraction where at least one expected keyword appeared in the answer. |
| `hallucinated_citations_total` | Number of `[Sx]` markers in answers that don't map to a returned source. The verifier should drive this to 0. |
| `mean_timings_s` | Mean wall-clock seconds per skill (`analyze`, `retrieve`, `reason`, `verify`, `format`). |

## Question schema

```json
{
  "id": "q01",
  "question": "What are common symptoms of type 2 diabetes?",
  "expect": {
    "should_refuse": false,
    "must_be_grounded": true,
    "urgency_in": ["low", "medium"],
    "must_mention_any": ["thirst", "urination"]
  }
}
```

`must_mention_any` uses case-insensitive substring matching. Listing
several synonyms is expected — keyword recall is a sanity check, not a
semantic similarity score.

## How to run

```bash
# 1. Make sure Ollama and the knowledge base are ready.
ollama serve
python scripts/ingest.py

# 2. Run the eval (uses the same orchestrator as the API).
python eval/run.py
python eval/run.py --limit 10        # quick subset
python eval/run.py --out my.jsonl    # custom output path
```

Outputs:
- `eval/results.jsonl` — one JSON object per question with full detail
- `eval/summary.json` — aggregate metrics (paste these into the README)
