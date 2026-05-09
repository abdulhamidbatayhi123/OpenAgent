# Marketing copy bank

Short reusable variants for every place you'll mention this project. All
defensible against interview questions — claims match what the code actually
does.

---

## GitHub repo "About" (under the repo name, ~120 char limit)

> Multi-agent RAG pipeline that makes 3B local LLMs answer health questions
> without inventing citations. 100% local, with verifier ablation.

**Topics to add to the repo:** `llm`, `rag`, `agents`, `multi-agent`, `ollama`,
`local-ai`, `chromadb`, `fastapi`, `python`, `health`.

---

## One-line elevator pitch (verbal, interview, hallway)

> I built a five-agent pipeline that runs entirely on a laptop and uses a
> separate verifier model to strip fabricated citations from another model's
> output — measured on a 30-question medical eval, with the verifier ablation
> showing it actually works.

---

## Twitter / X version (280 char limit)

> Small open-source LLMs hallucinate citations. So I built a 5-agent local
> pipeline where a separate verifier reads every [Sx] cite against the
> evidence and strips the unsupported ones.
>
> Ollama + ChromaDB + FastAPI. 30-q eval. Repo:
> {github-url}

---

## CV bullets — three lengths

### One line (for resume header / CV summary)

> Built MedMind, a five-agent local-RAG pipeline (Python, Ollama, ChromaDB)
> with a citation-verification stage that measurably eliminates fabricated
> citations on a 30-question health-domain eval.

### Three lines (resume project bullet)

> **MedMind — Multi-agent RAG for trustworthy local LLMs.** Designed and built
> a 5-skill pipeline (Symptom Analyzer → Retriever → Reasoner → Citation
> Verifier → Safety Formatter) on Python / FastAPI / Ollama / ChromaDB, with
> per-skill model routing (3B for structured tasks, 8B for reasoning).
>
> Implemented a separate citation-verifier stage that re-reads each generated
> answer against retrieved evidence and removes unsupported `[Sx]` markers
> before the user sees them.
>
> Wrote a reproducible 30-question eval harness (`grounding_match_rate`,
> `hallucinated_citations_total`, per-skill timings) and an ablation showing
> the verifier reduces fabricated citations from {N_without} to {N_with}.

### Five-line version (cover letter, "interesting projects" page)

> **MedMind — Multi-agent RAG for trustworthy local LLMs (Python, Ollama, ChromaDB, FastAPI)**
>
> Single small (3B parameter) open-source LLMs hallucinate facts and fabricate
> citations on health questions. To make them usable for high-stakes domains
> without paying for a closed API, I designed a 5-agent pipeline where each
> stage has the right-sized model and a narrow contract.
>
> The key idea is **citation verification as a separate step**: the reasoner
> writes the answer with `[S1][S2]` markers, and a separate small model reads
> the same evidence and emits structured JSON saying which claims are
> supported. Unsupported markers are stripped before the user sees them.
>
> A 30-question eval harness measures grounding rate, refusal rate on
> out-of-distribution queries, and total fabricated citations. The verifier
> ablation drops fabricated citations from {N_without} to {N_with} on the same
> question set.
>
> Engineering details I'm pleased with: deterministic chunk IDs for idempotent
> ingestion, sigmoid-normalised retrieval confidence with an honest-refusal
> path below threshold, per-skill timings exposed on the API, a single shared
> orchestrator across the HTTP API and an optional Telegram bot.

---

## "Interview answer when asked about the project"

A pre-prepared 90-second walkthrough. Don't memorise word-for-word; learn the
beats.

> **The problem.** I wanted an AI health assistant that didn't cost money and
> didn't leak my queries to a third-party API. The obvious option is a small
> open-source LLM running locally. The problem is, small models hallucinate —
> especially on knowledge-heavy domains like medicine, and they fabricate
> citations that look real.
>
> **What I built.** A five-stage pipeline. The first stage parses the user's
> question into structured JSON — symptoms, urgency, sub-queries, language. A
> retriever does multi-query search over a local vector store and reranks with
> a cross-encoder. A reasoner writes the answer with `[S1][S2]` citations. A
> separate verifier — a different small model — re-reads the answer and the
> same evidence, and emits JSON saying which claims are supported. Unsupported
> citations are stripped. Then a rule-based formatter adds disclaimers and
> sources.
>
> **Why it works.** Each stage is small enough that a 3B model handles it.
> Only the reasoning stage benefits from the 8B model. The verifier earns its
> place because it catches the model cheating with a different model — saying
> "don't make up citations" doesn't work; reading its output with another
> model does.
>
> **How I measured it.** A 30-question eval harness. The metric I care about
> is `hallucinated_citations_total` — how many `[Sx]` markers in answers don't
> map to a returned source. With the verifier off, it's {N_without}. With the
> verifier on, it's {N_with}.
>
> **Honest limitations.** Small curated knowledge base — 25 conditions, 15
> drugs — so the system refuses most questions outside that scope, which is
> actually the right behaviour. No clinical validation. Latency is 10–30
> seconds per query on a laptop CPU. It's a portfolio project, not a
> medical product.

---

## Anticipated tough questions (and honest answers)

> **Why not just use GPT-4 / Claude?**
>
> Cost and privacy. Cloud APIs charge per token and send sensitive medical
> queries to a third party. The point of this project is to show what's
> achievable with small open-source models running entirely on the user's
> machine. The architecture is the contribution, not the model choice.

> **Couldn't a single bigger model do this in one prompt?**
>
> Probably yes for an 8B+ model. But (1) "tell the model not to lie" doesn't
> reliably work — verification with a second model does, regardless of model
> size; (2) per-skill routing means the heavy model only runs on the one stage
> that needs it; (3) splitting the work makes it auditable — you can measure
> each stage in isolation.

> **Is the eval set representative?**
>
> No, it's 30 fixed questions chosen to exercise specific behaviours
> (grounded answers, out-of-distribution refusal, urgency detection,
> drug-related queries). It's a smoke test for the architecture, not a
> medical accuracy benchmark. The roadmap calls out adding adversarial cases.

> **Would you use this on yourself?**
>
> For background reading, yes. For a real medical decision, no — and the
> system tells the user that on every response. The disclaimer is there for
> a reason.

> **What was the hardest part?**
>
> Calibrating the retrieval-confidence threshold. Too high and the system
> refuses good questions; too low and it answers from thin evidence and the
> verifier strips half the citations. Settled on 0.45 after looking at the
> score distribution from the eval harness. The harness paid for itself in
> that one tuning step.
