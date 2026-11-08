# Promo Finder

Reads a microdrama's timestamped screenplays and returns a **promo cut sheet** an editor can act on. You get a post list of 10 clips, then a bench, then the clips the AI judge rejected and why. Every clip comes with:

- the episode, plus the start and end of every segment
- the hook and the cliffhanger
- one line on why it works
- why it sits where it does in the posting order
- the one thing to check before posting

**Try it without installing anything:** open `demo/Promo_Finder.ipynb` in Google Colab and choose *Run all*. It runs on a built-in test show. Set `USE_DEMO_SHOW = False` to upload your own.

## Run it locally

```bash
pip install -r requirements.txt                          # requests (+ numpy for learn.py)
python -m promo_finder run path/to/show.zip --out out/    # no API key needed; ~2 s for 50 episodes
# open out/cut_sheet.html in a browser
```

Add the AI judge. Only the provider flag changes:

```bash
export GEMINI_API_KEY=...    && python -m promo_finder run show.zip --provider gemini            # default model gemini-3.5-flash-lite (2.5 models are closed to new keys)
export OPENAI_API_KEY=...    && python -m promo_finder run show.zip --provider openai --model gpt-4o-mini
export OPENAI_BASE_URL=https://your-endpoint/v1 OPENAI_API_KEY=... \
                             && python -m promo_finder run show.zip --provider openai --model <name>   # any OpenAI-compatible API
export ANTHROPIC_API_KEY=... && python -m promo_finder run show.zip --provider anthropic --model <name>
```

If every judge call fails (wrong key or model name), the run says so and exits with code 2. It doesn't quietly fall back to rules-only output.

Free API tiers may use what you send them for training. That's fine for a demo. For unreleased scripts, use a paid tier that doesn't retain data, or your own endpoint.

| Option | What it does |
|---|---|
| `--strategy funnel` / `peak` | Posting order. `funnel` puts clips from the first 5 episodes first. `peak` puts the strongest moments first. Both are hypotheses to A/B test. |
| `--lexicon period,modern` | Genre word lists to add. By default the tool picks them by counting their words in the scripts. |
| `--weights weights.json` | Posting weights learned from editor feedback (see below). |
| `--title`, `--promise duke` | Show title (default: the folder name) and the title-promise word (default: the title's last word). |

## How it works

1. **Code** parses every line of the script (dialogue, action, sound, camera) with its timestamp and a line ID.
2. **Simple rules** score each line, using the delivery tags already in the script ("Screaming", "Venomous") plus word lists for physical shocks, reveals, threats and questions.
3. **Code** builds candidate clips only on line boundaries: one continuous stretch, or 2–3 segments when a long scene has to fit in 60 s. The candidates are deduplicated, and the best one from **every** episode goes to the judge.
4. **The AI judge** sees one candidate plus the 30 s before and 15 s after it, with the show title but *no* story summary. It can keep, move, reshape or reject the clip. It answers with **line IDs, never timestamps**.
5. **Code** checks the answer:
   - IDs exist and are in order
   - total length is 20–60 s
   - no cut lands inside a sentence the script splits across two lines
   - the hook really starts in the first 3 s; if not, the start moves to it, or the clip can't enter the post list
6. **Code** ranks for posting, with one clip per story moment in the top 10.
7. **The editor** decides, using Accept/Reject on the cut sheet.

## Close the loop

The cut sheet's **Export my decisions** button saves a CSV of what the editor accepted and rejected.

```bash
python -m promo_finder.learn editor_feedback.csv --out weights.json   # re-fits the posting weights
python -m promo_finder run next_show.zip --weights weights.json
```

With fewer than 30 decisions, the learned weights are blended toward the starting ones. Later, the label can be real performance (for example, CTR above the median) instead of accept/reject.

## Checks

```bash
python tests/run_tests.py [kuku_input_pack.zip]        # 18 tests: parser, matching, validator, API connectors (fake server), held-out show
python -m promo_finder.evaluate out/ show.zip           # automatic checks on a run
python -m promo_finder.sensitivity out/                 # how much the ranking depends on the hand-set weights
python tests/score_planted.py out/                      # only for the test show: planted promos and traps
python review/build_blind_review.py runA/ runB/ --input show.zip   # blind side-by-side review page for a human
bash run_gemini.sh input_pack.zip                       # real Gemini run + checks + comparison + blind review
```

`tests/synthetic_show` is a 4-episode modern CEO-revenge show in the same script format. It has three promo moments and four traps (a split sentence, a resolved scene, a soft ending, a quiet episode) planted on purpose. The answer key, `tests/ground_truth.json`, was written before the tool was run on it.

## Files

```
promo_finder/   parse.py · features.py (line scoring) · lexicons.json + lexicon_packs/ · candidates.py
                judge.py (prompt, providers, checks) · rank.py (posting order, cut sheet) · evaluate.py
                sensitivity.py · learn.py
tests/          run_tests.py · synthetic test show + ground_truth.json · score_planted.py
review/         blind review builder + tally
demo/           Colab notebook (built by build_notebook.py)
docs/           solution doc source + research notes
```

**Limits:**
- It reads scripts, not video. It assumes the script times match the final cut.
- The parser expects this screenplay format.
- The word lists are English.

The input pack and any output that quotes it are Kuku's content. `outputs/` and the review files are git-ignored, so they stay out of public repos.
