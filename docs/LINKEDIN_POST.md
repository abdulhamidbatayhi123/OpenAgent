# LinkedIn launch post — three versions

Three drafts of escalating length. Pick the one that matches your timeline:
the short one ships today, the medium one is the default, the long one is for
when you've finished the eval and have real numbers to lead with.

Replace anything in `{curly braces}`. Don't post until you have:

- The 30–60 second demo GIF (`docs/media/demo.gif`)
- The ablation chart (`docs/media/ablation.png`)
- The eval `summary.json` numbers in the README
- The repo set to public

---

## Short version (5 lines, 30 seconds to post)

> Small open-source LLMs hallucinate citations on health questions. So I built a
> 5-agent pipeline that catches them.
>
> A separate verifier checks every `[Sx]` citation against the retrieved
> evidence and strips the unsupported ones before the user sees the answer.
> 100% local, no API keys, runs on a laptop with Ollama.
>
> Repo: {github-url}
>
> #LLM #RAG #Agents #LocalAI

---

## Medium version (default)

> A single 3B parameter open-source LLM, asked a health question, will often
> invent citations that look real. This is the well-known limitation that makes
> small local models hard to trust on high-stakes domains.
>
> So I built **MedMind** — a 5-agent pipeline that treats trustworthiness as an
> engineering property:
>
> 1. **Symptom Analyzer** — turns the question into structured JSON (symptoms,
>    urgency, sub-queries, language). Small fast model.
> 2. **Medical Retriever** — multi-query search over a local ChromaDB, with a
>    cross-encoder rerank on top of cosine similarity.
> 3. **Clinical Reasoner** — generates the answer with `[S1][S2]` citations
>    over the retrieved evidence. The only stage that uses the bigger 8B model.
> 4. **Citation Verifier** — a *separate* 3B model re-reads the answer and the
>    same evidence, and removes any citation that isn't actually supported.
> 5. **Safety Formatter** — disclaimers, emergency banners, refusal templates.
>
> The verifier is the part I'm most pleased with. It's the difference between
> "looks cited" and "actually grounded".
>
> A 30-question eval harness measures grounding rate, refusal rate on
> out-of-distribution queries, and the count of fabricated citations. Target:
> `hallucinated_citations_total = 0`.
>
> Stack: Ollama (qwen2.5:3b + qwen3:8b + gemma3:4b vision + nomic-embed-text),
> ChromaDB, sentence-transformers cross-encoder, FastAPI, vanilla JS frontend,
> Telegram bot.
>
> 100% local. No API keys. No data leaves the machine.
>
> Code + write-up: {github-url}
>
> #LLM #RAG #Agents #Ollama #LocalAI #OpenSource #HealthTech

---

## Long version (after the eval is run)

> **What does it take to make a 3B-parameter local LLM stop fabricating
> citations on health questions?**
>
> Here's what I tried, and the numbers from a 30-question eval.
>
> The problem: cloud LLMs cost money and leak sensitive medical questions.
> Open-source models that run on your laptop are free and private, but small
> ones (3B–8B) hallucinate facts and invent citations. For a health-domain
> assistant, that's the worst possible failure mode.
>
> **The architecture:** a 5-agent pipeline.
>
> ```
> Question → Analyzer → Retriever → Reasoner → Verifier → Formatter → Answer
> ```
>
> Each agent has a narrow job and the right-sized model. The Analyzer and
> Verifier do small JSON-shaped work on a 3B model. The Reasoner does the
> open-ended generation on a larger 8B model — the only stage that needs it.
>
> **The key idea — citation verification as a separate step.** The Reasoner
> writes the answer with `[S1][S2]` markers. A *second* model then reads the
> same evidence and the answer, and emits structured JSON saying which claims
> are supported. Unsupported markers are removed before the user sees the
> answer.
>
> **What I measured (30 fixed questions):**
>
> - Grounding match rate: {grounding_match_rate}
> - Refusal match rate (out-of-distribution): {refusal_match_rate}
> - Urgency detection: {urgency_match_rate}
> - **Fabricated citations without verifier: {N_without}**
> - **Fabricated citations with verifier: {N_with}**
>
> The ablation is the chart that matters. Same questions, same models, same
> retrieval — only the verifier changes. {N_without} fabricated citations
> become {N_with}.
>
> **Stack:** Ollama, ChromaDB, sentence-transformers cross-encoder reranker,
> FastAPI, vanilla JS UI, optional Telegram bot. 100% local, no API keys, no
> data leaves the machine. Bilingual (English + Arabic).
>
> **What this project taught me:**
>
> - Multi-agent orchestration is mostly prompt engineering and routing — the
>   hard part is deciding what each agent's *contract* is.
> - Verification beats prompting. Telling a model "don't make up citations"
>   doesn't work. Reading its output with a second model does.
> - "I don't know" is a feature. Out-of-distribution questions should fail
>   loudly, not quietly invent.
>
> **Honest limitations:** small curated knowledge base (25 conditions, 15
> drugs, 30 foods), no clinical validation, 10–30 sec latency on laptop CPU.
> It's a portfolio project, not a medical device.
>
> Code, eval harness, and write-up: {github-url}
>
> Happy to chat with anyone working on local LLMs, agentic systems, or
> retrieval — DMs open.
>
> #LLM #RAG #Agents #Ollama #LocalAI #OpenSource #HealthTech #Python

---

## Hashtag bank

Pick 4–6 from these. Don't use all of them — the LinkedIn algorithm penalises
hashtag spam.

`#LLM` `#RAG` `#Agents` `#AgenticAI` `#Ollama` `#LocalAI` `#OpenSource`
`#Python` `#FastAPI` `#MachineLearning` `#AI` `#Healthcare` `#HealthTech`
`#Privacy` `#StudentProject` `#PortfolioProject`

---

## Posting tips

- **Post on a Tuesday or Wednesday morning** in your timezone — best LinkedIn
  engagement window. Avoid Friday afternoons.
- **First comment is for the link.** LinkedIn reduces reach for posts that
  link out in the body. Put the GitHub URL in your first reply.
- **Ask one question at the end** to drive comments — "What's your favourite
  way to keep a small model from hallucinating?" gets discussion.
- **Reply to every comment in the first hour.** It compounds reach.
- **Tag 1–2 relevant people** if you have permission. Don't spam tag.
- **Pin the post to your profile** for at least a week.
