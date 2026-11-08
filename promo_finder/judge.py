"""Model judge: the only place an LLM is used.

Contract (same for every provider):
  in : one candidate's beats (with IDs + times) plus ~30 s of slack on each side
  out: strict JSON choosing segments BY BEAT ID, plus hook/cliff text and 1-5 scores

The model never writes a timestamp. Code maps beat IDs -> times, re-checks 20-60 s,
order and hook position, and falls back to the rule-based candidate if anything is invalid.
Swap the model with --provider / --model (or env vars); nothing else changes.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .candidates import Candidate, Segment, MIN_LEN, MAX_LEN
from .parse import Episode, fmt

SYSTEM = """You are a senior promo editor for vertical microdrama ads (ReelShort / DramaBox style) aimed at US viewers scrolling Instagram Reels, TikTok and YouTube Shorts. You pick clips from the show itself; you do not write new lines, edit audio or add text. You see only the script lines around one candidate clip, exactly as a viewer would meet them: you are NOT told the story so far, so judge "makes sense on its own" from these lines alone.

A great promo:
1. HOOK: something in the first 3 seconds stops a scrolling stranger (a slap or strike, a reveal, a shocking or humiliating line, a threat, a striking visual). The first segment must START on the hook line or action, or at most 3 s before it.
2. CLIFFHANGER: it cuts at an unresolved moment. Do NOT include the answer, the rescue or the resolution. A scene where the problem gets solved is not a promo.
3. STANDS ALONE: a stranger understands who is wronged, by whom, and what is at stake.
4. LENGTH: 20-60 s in total, 25-45 s ideal. Add the durations of your segments from the times shown and make sure the total is inside 20-60 s.
5. ONE CONTINUOUS STRETCH is the default. Use 2-3 segments only when no continuous stretch can hold both the hook and the cliff inside 60 s; every jump cut is a risk.

Rules: segment boundaries must be beat IDs copied exactly from the list (CAMERA lines describe what is on screen and may be used). Never invent IDs or timestamps. Segments in story order, not overlapping. If there is no strong hook or no real cliffhanger here, answer is_promo=false: a weak promo wastes ad spend.
Scoring 1-5, using the whole range: 1 = would not post, 3 = usable, 5 = among the best moments you'd expect in a whole series. Quote the hook and cliffhanger exactly as written in the beats. Answer with JSON only."""

SCHEMA = """Return exactly this JSON:
{"is_promo": true|false,
 "segments": [["<start_beat_id>", "<end_beat_id>"], ...],
 "hook": "<the line or action in the first 3 s, quoted from the beats>",
 "hook_type": "slap_or_violence|reveal|shocking_line|threat|humiliation|visual|question",
 "cliffhanger": "<the last line or action before the cut, quoted from the beats>",
 "why": "<one line: why a stranger would stop AND tap through>",
 "scores": {"hook": 1-5, "cliffhanger": 1-5, "standalone": 1-5, "emotion": 1-5},
 "spoiler_risk": "low|medium|high",
 "ad_policy_risk": "none|violence|sexual|child|other",
 "editor_check": "<the one thing a human editor should verify before posting>"}"""


def window_beats(c: Candidate, eps: dict[int, Episode], before=30.0, after=15.0):
    """All beats (dialogue, action, SFX and camera) of the candidate plus slack, in story order."""
    out = []
    for i, s in enumerate(c.segments):
        e = eps[s.ep]
        lo = s.start - (before if i == 0 else 4)
        hi = s.end + (after if i == len(c.segments) - 1 else 4)
        for b in e.beats:
            if lo <= b.start <= hi and b not in out:
                out.append(b)
    return out


def build_prompt(c: Candidate, eps: dict[int, Episode], show_title: str) -> dict:
    beats = window_beats(c, eps)
    proposal_ids = {s.beats[0].id: "START>" for s in c.segments}
    proposal_ids.update({s.beats[-1].id: "<END" for s in c.segments})
    lines = []
    cur_ep = None
    for b in beats:
        if b.ep != cur_ep:
            cur_ep = b.ep
            lines.append(f"--- Episode {b.ep} ---")
        mark = proposal_ids.get(b.id, "")
        if b.kind == "dialogue":
            who, text = f"{b.speaker} ({b.tags})", b.text
        else:
            who, text = b.kind.upper(), (b.text if len(b.text) <= 140 else b.text[:137] + "...")
        lines.append(f"{mark:6s}[{b.id}] {fmt(b.start)}-{fmt(b.end)} {who}: {text}")
    # No episode summary on purpose: the judge must meet the clip the way a cold viewer does.
    user = (f"Show: {show_title}\n\n"
            f"A rules engine proposed the clip marked START> ... <END ({c.kind}, {c.duration:.1f} s). "
            f"You may keep it, move its boundaries to any listed beat, reshape it, or reject it.\n\n"
            + "\n".join(lines) + "\n\n" + SCHEMA)
    return {"id": c.id, "system": SYSTEM, "user": user, "beat_ids": [b.id for b in beats]}


# ---------------------------------------------------------------- providers
def _post(url, headers, body, timeout=90):
    import requests
    for attempt in range(4):
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code in (429, 500, 503):
            time.sleep(2 ** attempt * 3)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def call_gemini(p, model):
    key = os.environ["GEMINI_API_KEY"]
    base = os.environ.get("PROMO_GEMINI_URL", "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{base}/v1beta/models/{model}:generateContent?key={key}"
    j = _post(url, {"Content-Type": "application/json"}, {
        "systemInstruction": {"parts": [{"text": p["system"]}]},
        "contents": [{"role": "user", "parts": [{"text": p["user"]}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                             # thinking off: this is a scoring task, and it keeps cost and latency predictable
                             **({"thinkingConfig": {"thinkingBudget": 0}} if model.startswith("gemini-2.5") else {})}})
    return j["candidates"][0]["content"]["parts"][0]["text"]


def call_openai(p, model):
    """Any OpenAI-compatible endpoint: OpenAI, Groq, OpenRouter, Together, local Ollama, or an API Kuku provides."""
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    j = _post(f"{base}/chat/completions",
              {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'none')}", "Content-Type": "application/json"},
              {"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}]})
    return j["choices"][0]["message"]["content"]


def call_anthropic(p, model):
    base = os.environ.get("PROMO_ANTHROPIC_URL", "https://api.anthropic.com").rstrip("/")
    j = _post(f"{base}/v1/messages",
              {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
               "content-type": "application/json"},
              {"model": model, "max_tokens": 800, "temperature": 0.2, "system": p["system"],
               "messages": [{"role": "user", "content": p["user"]}]})
    return j["content"][0]["text"]


PROVIDERS = {"gemini": (call_gemini, "gemini-3.5-flash-lite"),
             "openai": (call_openai, "gpt-4o-mini"),
             "anthropic": (call_anthropic, "claude-haiku-4-5")}


def prompt_key(p, provider, model):
    """Same prompt + same model -> same answer. 'file' answers are model-agnostic by design."""
    import hashlib
    # imported answers are keyed by the model that wrote them, so one model's answers never stand in for another's
    tag = (f"file:{model}" if model else "file") if provider == "file" else f"{provider}:{model or PROVIDERS[provider][1]}"
    return hashlib.sha256((tag + p["system"] + p["user"]).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- validation
def parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def apply_verdict(c: Candidate, v: dict, eps: dict[int, Episode], allowed: list[str]) -> tuple[Candidate, list[str]]:
    """Turn a model verdict into a validated Candidate. Returns (candidate, problems)."""
    problems = []
    by_id = {b.id: b for e in eps.values() for b in e.beats}
    order = {bid: i for i, bid in enumerate(allowed)}
    segs = []
    for pair in v.get("segments") or []:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            problems.append(f"bad segment {pair}")
            continue
        a, b = pair
        if a not in order or b not in order:
            problems.append(f"unknown beat id {a if a not in order else b}")
            continue
        if order[a] > order[b]:
            problems.append(f"segment {a}>{b} reversed")
            continue
        end = order[b]
        while by_id[allowed[end]].cliff <= -2 and end + 1 < len(allowed) \
                and by_id[allowed[end + 1]].ep == by_id[allowed[end]].ep:
            end += 1  # the line continues in the next beat: extend instead of cutting mid-sentence
        if end != order[b]:
            problems.append(f"auto_fix: end moved past a split sentence ({b} -> {allowed[end]})")
        beats = [by_id[x] for x in allowed[order[a]:end + 1]]
        if len({x.ep for x in beats}) > 1:
            problems.append("segment crosses episodes")
            continue
        if segs and order[a] <= order[segs[-1].beats[-1].id]:
            problems.append("segments overlap or out of order")
            continue
        segs.append(Segment(beats[0].ep, beats))
    if not v.get("is_promo", True):
        return c, problems + ["model says no promo here"]
    if not segs:
        return c, problems + ["no valid segments"]
    new = Candidate(c.kind if len(segs) == len(c.segments) else ("single" if len(segs) == 1 else
                    ("cross_ep" if len({s.ep for s in segs}) > 1 else "compressed")), segs)
    if not (MIN_LEN <= new.duration <= MAX_LEN):
        problems.append(f"duration {new.duration}s outside 20-60")
        return c, problems
    new.id, new.parts, new.flags = c.id, dict(c.parts), sorted({f for b in new.beats for f in b.flags})
    new, notes = check_hook(new, v.get("hook", ""))
    return new, problems + notes


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def find_hook_beat(c: Candidate, hook: str):
    """Earliest beat in the clip whose text matches the model's quoted hook (first line of it)."""
    h = _norm(hook)
    if not h:
        return None
    import difflib
    for b in c.beats:
        t = _norm(b.text)
        if not t:
            continue
        if (len(t) >= 8 and t[:40] in h) or (len(h) >= 8 and h[:40] in t) \
                or (len(h) >= 8 and difflib.SequenceMatcher(None, t, h[:len(t) + 20]).ratio() >= 0.6):
            return b
    return None


def check_hook(c: Candidate, hook: str):
    """Enforce 'hook in the first 3 s'. If the hook starts later, move the start to it when the clip
    still lasts >= 20 s; otherwise flag it. Returns (candidate, notes)."""
    hb = find_hook_beat(c, hook)
    if hb is None:
        return c, ["hook_unverified: quoted hook not found in the clip"]
    first = c.segments[0]
    offset = hb.start - first.start
    if hb.ep != first.ep or hb not in first.beats:
        return c, [f"hook_late: hook is not in the first segment"]
    if offset <= 3.0:
        return c, []
    trimmed = [b for b in first.beats if b.start >= hb.start - 0.01]
    fixed = Candidate(c.kind, [Segment(first.ep, trimmed)] + c.segments[1:])
    if fixed.duration >= MIN_LEN:
        fixed.id, fixed.parts, fixed.flags = c.id, c.parts, c.flags
        return fixed, [f"auto_fix: start moved {offset:.1f} s later to the hook"]
    return c, [f"hook_late: hook starts {offset:.1f} s in and trimming would drop below 20 s"]


def judge_all(cands, eps, show_title, provider, model, outdir: Path, responses_dir: Path | None = None, log=print):
    """Returns list of dicts {cand, verdict, problems, raw}. Writes every prompt + raw response to outdir."""
    pdir = outdir / "judge_prompts"
    rdir = outdir / "judge_raw"
    cdir = Path(os.environ.get("PROMO_JUDGE_CACHE", outdir / "judge_cache"))
    for d in (pdir, rdir, cdir):
        d.mkdir(parents=True, exist_ok=True)
    results = []
    stats = {"cache_hits": 0, "calls": 0}
    for c in cands:
        p = build_prompt(c, eps, show_title)
        key = prompt_key(p, provider, model)
        p["cache_key"] = key
        (pdir / f"{c.id}.json").write_text(json.dumps(p, indent=1))
        raw, verdict, problems = None, None, []
        try:
            cached = cdir / f"{key}.json"
            if cached.exists():  # identical prompt + model answered before: reuse, don't pay twice
                raw = cached.read_text()
                stats["cache_hits"] += 1
            elif provider == "file":
                f = (responses_dir or rdir) / f"{c.id}.json"
                if not f.exists():
                    problems.append("no response file yet")
                else:
                    raw = f.read_text()
            elif provider in PROVIDERS:
                fn, default = PROVIDERS[provider]
                raw = fn(p, model or default)
                stats["calls"] += 1
            if raw:
                (rdir / f"{c.id}.json").write_text(raw)
                if not cached.exists():
                    cached.write_text(raw)
            if raw:
                verdict = parse_json(raw)
        except Exception as ex:  # network, quota, bad JSON: never crash the run
            problems.append(f"{type(ex).__name__}: {str(ex)[:160]}")
        final = c
        if verdict:
            final, more = apply_verdict(c, verdict, eps, p["beat_ids"])
            problems += more
        results.append({"cand": final, "rule_cand": c, "verdict": verdict, "problems": problems})
        log(f"  judged {c.id}: {'ok' if verdict and not problems else problems}")
    log(f"  judge: {stats['calls']} model calls, {stats['cache_hits']} cache hits")
    return results
