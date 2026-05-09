# Demo capture checklist

Everything you need to record in one sitting. The whole list takes about 30
minutes if you've got the system already running.

Recording tools:
- **Windows:** ScreenToGif (free, open source, GIF export built in) — use this.
- **Cross-platform alternative:** OBS Studio + ezgif.com to convert MP4 → GIF.

Save everything into `docs/media/`. The README and LinkedIn post already
reference these exact filenames, so don't rename without updating both.

---

## Asset 1 — `demo.gif` (the hero)

**Where it goes:** top of the README, under the title.
**Length:** 30–60 seconds. Loop the GIF.
**Resolution:** 1280×800 max, scale down if needed; LinkedIn shows it at ~780px.

**The script:**

1. Open the UI at `http://localhost:8000/static/index.html`.
2. Type the query: **"I have heartburn after meals, what could it be?"**
3. Hit send. The GIF should capture:
   - The "thinking" / step indicator showing the 5-skill pipeline
   - The answer streaming in with `[S1][S2]` citations
   - The sources panel with real URLs (medlineplus.gov, etc.)
   - The per-skill timings appearing
4. Hover over a citation so the source preview shows.
5. Cut.

This single query exercises retrieval, reasoning, citation, and source display.
Don't pick an emergency query for the hero — the urgency banner is dramatic but
distracting for a first impression.

---

## Asset 2 — `ablation.png` (the killer chart)

**Where it goes:** in the Results section of the README.
**What it shows:** fabricated citations with and without the verifier.

**How to generate it:**

1. Run the eval normally:
   ```bash
   python eval/run.py --out eval/results_with_verifier.jsonl
   ```

2. Disable the verifier temporarily — open `backend/skills/citation_verifier.py`
   and in `verify()`, comment out the call to `_llm_verify` so it returns the
   answer unchanged with all original citations intact. Save.

3. Run the eval again:
   ```bash
   python eval/run.py --out eval/results_no_verifier.jsonl
   ```

4. Restore the verifier (uncomment, save).

5. Generate the chart with this one-shot Python script — paste into
   `scripts/plot_ablation.py` and run:

   ```python
   import json
   from pathlib import Path
   import matplotlib.pyplot as plt

   def total_halluc(path):
       n = 0
       with open(path, encoding="utf-8") as f:
           for line in f:
               r = json.loads(line)
               n += len(r.get("hallucinated_citations", []))
       return n

   no_v = total_halluc("eval/results_no_verifier.jsonl")
   with_v = total_halluc("eval/results_with_verifier.jsonl")

   fig, ax = plt.subplots(figsize=(7, 4))
   bars = ax.bar(
       ["No verifier\n(reasoner output)", "With verifier\n(default)"],
       [no_v, with_v],
       color=["#ef4444", "#22c55e"],
   )
   ax.set_ylabel("Fabricated citations across 30 questions")
   ax.set_title("Citation verifier removes fabricated citations")
   for b, v in zip(bars, [no_v, with_v]):
       ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.2,
               str(v), ha="center", fontsize=12, fontweight="bold")
   ax.spines[["top", "right"]].set_visible(False)
   plt.tight_layout()
   Path("docs/media").mkdir(parents=True, exist_ok=True)
   plt.savefig("docs/media/ablation.png", dpi=160)
   print("Saved docs/media/ablation.png")
   ```

6. Run: `pip install matplotlib --break-system-packages` then `python scripts/plot_ablation.py`.

The whole ablation takes ~10 minutes of compute and is the single most
defensible piece of evidence in the project.

---

## Asset 3 — `architecture.png` (optional, nice-to-have)

The Mermaid diagram in the README renders fine on GitHub, but for the LinkedIn
post you need a static image.

**Easiest path:** open the README on github.com, screenshot the rendered Mermaid
diagram, save as `docs/media/architecture.png`. Crop tight.

**Cleaner path:** paste the Mermaid block into <https://mermaid.live>, click
"PNG", download, save as `docs/media/architecture.png`.

---

## Asset 4 — `refusal.png` (the credibility shot)

**Where it goes:** optional, in the Results section, near the eval table.
**What it shows:** the system honestly refusing an out-of-distribution question.

1. Type: **"What's the optimal antibiotic regimen for tularemia in pregnant patients?"**
   (Almost certainly outside the 25-condition KB.)
2. Wait for the "I don't have enough reliable information" response.
3. Screenshot the chat panel showing the refusal + the suggestion to upload a
   relevant document.

This is the screenshot that disarms the "but does it just hallucinate?"
question before anyone asks it.

---

## Asset 5 — `pipeline_panel.png` (makes the multi-agent claim visible)

**Where it goes:** README and LinkedIn, in the architecture section.
**What it shows:** the per-skill timing panel returned by the API.

1. Run any normal query.
2. Open browser DevTools → Network → click the `/chat` request → Response tab.
3. Screenshot the JSON showing `timings: {analyze: ..., retrieve: ..., reason: ..., verify: ..., format: ...}` and `steps_completed: 5`.

Crop tight, syntax-highlight if your DevTools allow it. This is the proof that
the pipeline is real, not a marketing claim.

> **Better version (worth adding):** surface this same data in the UI itself as
> a collapsible "How I answered this" panel. Reasoning steps, urgency,
> retrieval confidence, removed citations, per-skill timings. Then screenshot
> the panel in the UI instead of DevTools — much more polished. Everything you
> need is already in the API response object.

---

## Recording tips

- **Close every other tab and notification.** Nothing kills a demo like a
  Discord ping mid-record.
- **Use a clean Chrome profile** with no extensions visible in the toolbar.
- **Zoom the browser to 110–125%** so text is readable when scaled down.
- **Type at human speed.** Don't paste. Watching the LLM stream after the user
  finishes typing is the part that feels alive.
- **Trim aggressively.** Cut every second of dead air. 30 seconds tight beats
  90 seconds loose.
- **Optimise file size.** GIFs over 10 MB feel sluggish on GitHub. Aim for
  ~5 MB. ScreenToGif's "Reduce frame count" is your friend.

---

## Final checklist before shipping

- [ ] `docs/media/demo.gif` exists, ≤ 10 MB, loops cleanly
- [ ] `docs/media/ablation.png` exists with both bars labelled
- [ ] `docs/media/architecture.png` exists (optional but nice for LinkedIn)
- [ ] `docs/media/refusal.png` exists
- [ ] `docs/media/pipeline_panel.png` exists
- [ ] `eval/summary.json` numbers pasted into the README's results table
- [ ] All `**TBD**` markers in the README replaced with real numbers
- [ ] Repo is public, not private
- [ ] `.env` is in `.gitignore` (check `git status` doesn't show it)
- [ ] LICENSE file is present (MIT)
- [ ] First commit message on the public branch is clean
