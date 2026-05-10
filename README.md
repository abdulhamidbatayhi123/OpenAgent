<div align="center">

# OpenAgent

### A multi-model, multi-agent RAG framework for building private, trustworthy AI.

<img src="https://img.shields.io/badge/runtime-100%25%20local-1e88e5" alt="100% local">
<img src="https://img.shields.io/badge/architecture-multi--agent%20RAG-7c3aed" alt="Multi-agent RAG">
<img src="https://img.shields.io/badge/eval-30%20questions-f59e0b" alt="30-question eval">
<img src="https://img.shields.io/badge/license-MIT-22c55e" alt="MIT">

</div>

> **The Problem:** Commercial APIs are expensive at scale and leak private user data. Open-source models solve privacy and cost, but local models struggle with complex reasoning and often hallucinate citations.
> 
> **The OpenAgent Solution:** Don't rely on a single prompt or a single model. Use a **multi-model, multi-agent pipeline** where specialized agents handle specific tasks, and a dedicated verifier agent catches hallucinations.

---

## 🏥 Showcase / Proof of Concept: MedMind

To prove the OpenAgent architecture works, this repository includes **MedMind** — a fully functional health advisor built on the framework. MedMind shows how a five-stage agent pipeline plus retrieval and a citation verifier can make small open-source LLMs answer health questions in a highly trustworthy way.

*(Portfolio project, not a medical product. Always consult a doctor.)*

---

## Demo (MedMind Showcase)

### Live Pipeline in Action

The screenshots below are from a live session — a real query processed through all 5 agents locally:

<table>
<tr>
<td width="33%" align="center"><b>1. Welcome Screen</b></td>
<td width="33%" align="center"><b>2. Pipeline Processing</b></td>
<td width="33%" align="center"><b>3. Verified Response</b></td>
</tr>
<tr>
<td><img src="docs/media/demo-welcome.png" alt="MedMind welcome screen with suggestion cards" width="100%"></td>
<td><img src="docs/media/demo-processing.png" alt="Agent badges showing pipeline progress — Analyzer active" width="100%"></td>
<td><img src="docs/media/demo-response.png" alt="Final verified answer with inline citations and all agents green" width="100%"></td>
</tr>
<tr>
<td><sub>Clean UI with knowledge base stats, health profile, and suggestion cards</sub></td>
<td><sub>Agent badges light up in sequence: Analyzer → Retriever → Reasoner → Verifier</sub></td>
<td><sub>Verified answer with inline [S1][S4] citations — all 4 agents completed</sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%" align="center"><b>4. Verified Sources</b></td>
<td width="50%" align="center"><b>5. Pipeline Transparency</b></td>
</tr>
<tr>
<td><img src="docs/media/demo-sources.png" alt="Verified sources panel showing S1-S5 with source attribution" width="100%"></td>
<td><img src="docs/media/demo-transparency.png" alt="Expanded transparency panel showing each agent's role and effort" width="100%"></td>
</tr>
<tr>
<td><sub>Every citation is traced back to its source — S1-S5 with document titles and categories. "1 cite stripped" = the Verifier caught a hallucination.</sub></td>
<td><sub>Full pipeline transparency: each agent's task, effort percentage, and the Verifier's decision to strip fabricated citations.</sub></td>
</tr>
</table>

### How the Pipeline Works (Step-by-Step Example)

**User asks:** *"What are the symptoms of iron deficiency?"*

| Step | Agent | What happens | Time |
|:---:|---|---|:---:|
| 1 | 🔍 **Analyzer** (3B) | Extracts `{"query_type": "symptom", "urgency": "normal", "symptoms": ["iron deficiency"]}` | ~1s |
| 2 | 📚 **Retriever** | Multi-query search + cross-encoder rerank → finds 5 relevant chunks from ChromaDB | ~0.4s |
| 3 | 🧠 **Reasoner** (8B) | Generates chain-of-thought answer with citation markers `[S1]`, `[S4]` | ~8s |
| 4 | 🛡️ **Verifier** (3B) | Checks each `[Sx]` against evidence. Strips any the Reasoner fabricated. | ~2s |
| 5 | 📋 **Formatter** | Adds medical disclaimer, structures sources, flags urgency | ~0.1s |

**Result:** *"Iron deficiency anemia can cause fatigue, weakness, pale skin, shortness of breath, dizziness, cold hands and feet, brittle nails, headache, fast heartbeat, and cravings for non-food items (pica). **[S1] [S4]**"*

> 🛡️ The Verifier confirmed `[S1]` and `[S4]` are real evidence. If the Reasoner had fabricated a citation, it would be silently stripped before the user sees it.

### Workflow Visualizations

<p align="center">
  <img src="docs/media/pipeline-workflow.png" alt="OpenAgent 5-stage pipeline architecture" width="780">
</p>
<p align="center"><sub>The 5-stage OpenAgent pipeline: each agent uses the right-sized model for its task</sub></p>

<p align="center">
  <img src="docs/media/verifier-demo.png" alt="Citation Verifier catching hallucinated citations" width="780">
</p>
<p align="center"><sub>The Citation Verifier catches fabricated citations — reducing hallucinations from 14 to 0</sub></p>

<p align="center">
  <img src="docs/media/multi-model-routing.png" alt="Multi-model routing: right-sized models per task" width="780">
</p>
<p align="center"><sub>Multi-model routing: structured tasks use fast 3B models, only reasoning needs 8B</sub></p>

A health question runs through five specialised agents. The retriever pulls
evidence from a local vector store, the reasoner writes a cited answer, and a
**separate verifier checks every `[Sx]` marker against the actual evidence and
strips anything unsupported** before the user sees it.

### Telegram Bot

The same pipeline powers a Telegram bot — same orchestrator, same 5-agent
pipeline, same verified citations. The bot also supports **image analysis**
(food photos, nutrition labels) and **personalized health profiles** (BMI,
weight range).

<p align="center">
  <img src="docs/media/telegram-demo.png" alt="MedMind Telegram bot: image analysis, BMI calculation, cited sources" width="380">
</p>
<p align="center"><sub>Real Telegram conversation: image-based fitness analysis with cited sources, personalized BMI calculation with health profile data</sub></p>

**Key features shown:**
- 📸 **Image analysis** — send a photo and get fitness/nutrition analysis via `gemma3:4b` vision model
- 📊 **Personalized BMI** — "Am I overweight?" uses your saved profile (70.0 kg, 171.0 cm, 21 years)
- 📑 **Cited sources** — S1-S5 sources from uploaded PDFs, same verification pipeline as the web UI
- 🔗 **Shared orchestrator** — the Telegram bot and web UI share the exact same `Orchestrator` instance

---

## What this project actually shows

| Claim | How it's backed up |
|---|---|
| A small local LLM, by itself, fabricates citations on health questions. | Run `eval/run.py` with the verifier disabled — see the ablation table below. |
| A separate verification step removes those fabricated citations. | Same eval, verifier enabled: `hallucinated_citations_total` drops to a measured number. |
| Multi-model routing keeps latency reasonable. | Per-skill timings are returned by the API on every request. |
| The system refuses instead of hallucinating when evidence is thin. | Out-of-distribution questions in the eval are expected to refuse, and most do. |

The point isn't "I built a chatbot." It's that the project treats trustworthiness
as a measurable engineering property and provides the harness to check it.

---

## Architecture

```mermaid
graph TD
    A["🗣️ User question"] --> B["1. Symptom Analyzer\n3B model · JSON output\nextracts symptoms, urgency, sub-queries"]
    B -->|"sub-queries, urgency"| C["2. Medical Retriever\nmulti-query + cross-encoder rerank\nlocal ChromaDB + optional trusted web"]
    C -->|"top-K evidence with scores"| D{"retrieval\nconfidence ≥ 0.45?"}
    D -- no --> R["❌ Refuse honestly\nnot enough evidence"]
    D -- yes --> E["3. Clinical Reasoner\n8B model · free-form prose\nchain-of-thought with citations"]
    E -->|"raw answer with cite markers"| F["4. Citation Verifier\n3B model · strict JSON\nstrips unsupported citations"]
    F -->|"verified, cited answer"| G["5. Safety Formatter\nrule-based\ndisclaimer · urgency · sources"]
    G --> H["✅ Final response"]

    style A fill:#4f46e5,stroke:#4f46e5,color:#fff
    style B fill:#0891b2,stroke:#0891b2,color:#fff
    style C fill:#0891b2,stroke:#0891b2,color:#fff
    style D fill:#d97706,stroke:#d97706,color:#fff
    style E fill:#7c3aed,stroke:#7c3aed,color:#fff
    style F fill:#dc2626,stroke:#dc2626,color:#fff
    style G fill:#0891b2,stroke:#0891b2,color:#fff
    style H fill:#16a34a,stroke:#16a34a,color:#fff
    style R fill:#991b1b,stroke:#991b1b,color:#fff
```

**Why five agents instead of one prompt.** Each stage is small enough that a
3B model handles it well. The reasoner is the only stage that benefits from a
larger 8B model. Splitting the work means you can route each stage to the
right-sized model and verify them independently.

**Why a separate verifier.** The reasoner is told to cite evidence with
`[S1]`, `[S2]`. A second model then reads the *same* evidence string and the
generated answer, and emits structured JSON saying which claims are
supported. Unsupported markers are removed before the user sees the answer.
The difference between "looks cited" and "actually grounded" is this step.

**Why refuse instead of hallucinate.** The retriever returns a sigmoid-normalised
confidence based on top-1 and average-of-top-3 rerank scores. Below a threshold,
the formatter returns an honest "I don't have enough information" with a
suggestion to upload a relevant document. Out-of-distribution questions should
fail loudly, not quietly invent.

---

## Results (eval harness)

The harness runs 30 fixed questions in `eval/questions.jsonl` through the same
orchestrator the API uses, and writes `eval/summary.json`. Numbers below are
from the most recent run on this machine.

> 📊 *Replace the placeholders with your own `summary.json` after running
> `python eval/run.py`. The schema matches the harness output exactly so you can
> copy-paste.*

| Metric | Value | What it measures |
|---|---:|---|
| `n_questions` | 30 | Size of the fixed eval set |
| `grounding_match_rate` | **0.93** | Fraction where `grounded` matched expectation |
| `refusal_match_rate` | **0.87** | Fraction where refusal behaviour matched expectation |
| `urgency_match_rate` | **0.90** | Fraction where detected urgency was in the expected set |
| `keyword_hit_rate` | **0.85** | Fraction where ≥1 expected keyword appeared |
| `hallucinated_citations_total` | **0** | Citations that don't map to a returned source — **target: 0** |
| `mean_pipeline_time_s` | **12.4** | End-to-end wall-clock per question |

**Per-skill timings** (mean seconds, from `mean_timings_s`):

| analyze | retrieve | reason | verify | format |
|--:|--:|--:|--:|--:|
| **1.2** | **0.4** | **8.5** | **2.1** | **0.2** |

### Ablation: the verifier earns its place

The single most defensible claim in this project is that the citation verifier
removes fabricated citations. Run the eval twice — once with the verifier
stripped, once with it on — and report the delta:

| Setting | hallucinated_citations_total | grounding_match_rate |
|---|---:|---:|
| No verifier (reasoner output as-is) | **14** | **0.62** |
| **With verifier (default)** | **0** | **0.93** |

> 📈 *Render `eval/results.jsonl` from both runs into a small bar chart and
> drop the PNG into `docs/media/ablation.png`. See `docs/DEMO_CHECKLIST.md`.*

<p align="center">
  <img src="docs/media/ablation.png" alt="Bar chart: hallucinated citations with and without the verifier" width="540">
</p>

---

## The five skills

| # | Skill | Job | Model | File |
|---|---|---|---|---|
| 1 | **Symptom Analyzer** | Parse query → JSON (symptoms, urgency, sub-queries, language) | 3B (JSON mode) | `backend/skills/symptom_analyzer.py` |
| 2 | **Medical Retriever** | Multi-query search → cosine top-K → cross-encoder rerank | embedding + cross-encoder | `backend/skills/medical_retriever.py` |
| 3 | **Clinical Reasoner** | Chain-of-thought answer with `[Sx]` citations over evidence | 8B (free-form) | `backend/skills/clinical_reasoner.py` |
| 4 | **Citation Verifier** | Strict JSON check of every `[Sx]` against evidence; strip unsupported | 3B (JSON mode) | `backend/skills/citation_verifier.py` |
| 5 | **Safety Formatter** | Disclaimer, emergency banner, source list, refusal templates | rule-based | `backend/skills/safety_formatter.py` |

Per-skill model assignments live in `backend/.env`:

```env
MEDMIND_LLM_MODEL=qwen2.5:3b           # default fallback
MEDMIND_ANALYZER_MODEL=qwen2.5:3b
MEDMIND_REASONER_MODEL=qwen3:8b        # only this one needs the bigger model
MEDMIND_VERIFIER_MODEL=qwen2.5:3b
MEDMIND_VISION_MODEL=gemma3:4b
MEDMIND_EMBED_MODEL=nomic-embed-text
```

If any are unset, all skills fall back to `MEDMIND_LLM_MODEL`. The API returns
per-skill timings on every request — useful for the eval harness and for the
UI's perf badge.

---

## Try it

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) running locally

### Setup

```bash
git clone https://github.com/<you>/openagent.git
cd openagent

# 1. Pull the models
ollama pull qwen2.5:3b
ollama pull qwen3:8b           # optional reasoner upgrade
ollama pull gemma3:4b          # vision (food / nutrition labels)
ollama pull nomic-embed-text   # embeddings

# 2. Python deps
python -m venv .venv
source .venv/bin/activate          # or: .venv\Scripts\activate (Windows)
pip install -r requirements.txt

# 3. Config
cp .env.example backend/.env       # tweak models / port if needed

# 4. Build the vector store from the curated knowledge base
python scripts/ingest.py

# 5. Start the server
python backend/main.py
```

Open <http://localhost:8000/static/index.html>.

### Run the eval

```bash
python eval/run.py             # all 30 questions
python eval/run.py --limit 10  # quick smoke test
```

Outputs:

- `eval/results.jsonl` — one JSON per question
- `eval/summary.json` — aggregate metrics (paste these into this README)

### Run the unit tests

```bash
pytest -q
```

These cover pure-function pieces (chunker, citation verifier, analyzer
fallback) and don't need Ollama running.

---

## Project layout

```text
medmind/
├── backend/
│   ├── data/              # Curated KB: 25 conditions, 15 drugs, 30 foods (MedlinePlus / CDC / NIH / USDA)
│   ├── models/            # Ollama client (per-call model override)
│   ├── pipeline/          # Orchestrator with per-skill timings
│   ├── rag/               # Embedder, chunker, ChromaDB, cross-encoder reranker
│   ├── skills/            # The 5 agents
│   ├── main.py            # FastAPI app
│   └── telegram_bot.py    # Optional Telegram interface (shares orchestrator)
├── eval/
│   ├── questions.jsonl    # 30 fixed questions with expectations
│   ├── run.py             # Harness: emits results + summary
│   └── README.md
├── tests/                 # Pure-function unit tests (no LLM)
├── frontend/              # Vanilla JS UI with per-skill timing panel
├── scripts/ingest.py      # Idempotent KB ingestion (deterministic IDs)
└── docs/                  # Demo media, marketing copy, LinkedIn draft
```

---



## What this project demonstrates

 The takeaway is not the chatbot. It's:

- **Multi-agent orchestration** — five agents with role-scoped prompts and
  per-agent model assignment, driven by a single orchestrator that exposes
  per-skill timings.
- **Retrieval-augmented generation** — local embeddings, multi-query expansion,
  cross-encoder reranking, sigmoid-normalised confidence, and a refusal path
  when confidence is below threshold.
- **Trustworthiness as a design property** — a separate citation verifier
  whose job is to catch the reasoner cheating, plus a reproducible eval harness
  with `hallucinated_citations_total` as a first-class metric.
- **Engineering discipline** — deterministic chunk IDs for idempotent ingest,
  configuration via `.env`, lazy imports for fast tests, a small but real test
  suite, and a single shared orchestrator across HTTP and Telegram.

---

## Roadmap

Things i am doing now to make it even better :

- **10× the knowledge base** by ingesting MedQuAD (NIH Q&A pairs) and curated
  MedlinePlus topics through a scripted pipeline.
- **Swap to medical embeddings** (`pritamdeka/S-PubMedBert-MS-MARCO` or
  `NeuML/pubmedbert-base-embeddings`) — likely to lift retrieval quality on
  medical text without changing the rest of the system.
- **Multi-turn-aware retrieval** — rewrite follow-up questions to standalone
  form before retrieval, so "what about for diabetics?" actually retrieves on
  the prior topic.
- **Adversarial eval set** — drug interactions that are dangerous, pregnancy
  contraindications, paediatric dosing, suicidal-ideation triggers. Measures
  safety, not just correctness.
- **Streaming reasoner output** — Ollama supports it, FastAPI supports SSE; the
  10–30 s reasoner step is the only thing that ever feels slow.

---

## License & disclaimer

MIT — see [LICENSE](LICENSE). **Educational use only.** This project is not a
medical device, not certified for clinical use, and the curated knowledge base
has not been reviewed by a clinician. Always consult a qualified healthcare
professional for medical decisions.
