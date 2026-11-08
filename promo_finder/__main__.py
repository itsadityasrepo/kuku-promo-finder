"""CLI:  python -m promo_finder run <show-folder-or-zip> [--provider heuristic|gemini|openai|anthropic|file] [--model NAME]

heuristic  rules only, no key, deterministic (default)
gemini     GEMINI_API_KEY (free tier works)
openai     OPENAI_API_KEY (+ OPENAI_BASE_URL for Groq/OpenRouter/Ollama/any compatible API)
anthropic  ANTHROPIC_API_KEY
file       writes prompts to <out>/judge_prompts; reads answers from --responses DIR (offline / manual / batch)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

from .candidates import dedupe, generate, shortlist
from .features import configure_lexicon, score_episode, show_names
from .judge import judge_all
from .parse import load_show, validate, fmt
from .rank import build_rows, story_moments, write_outputs

STOP = {"a", "an", "the", "he", "she", "was", "is", "i", "my", "of", "and", "to", "her", "his", "scripts", "episode"}


def guess_title(inp: Path) -> str:
    """Show title = the folder the screenplays live in (inside a zip or on disk), else the file/zip name."""
    import zipfile
    if inp.is_file() and inp.suffix.lower() == ".zip":
        with zipfile.ZipFile(inp) as z:
            dirs = {n.split("/")[0] for n in z.namelist() if n.lower().endswith(".txt") and "/" in n and not n.startswith("__MACOSX")}
        if len(dirs) == 1:
            return dirs.pop()
    if inp.is_dir():
        subs = {p.parent for p in inp.rglob("*.txt")}
        if len(subs) == 1:
            return subs.pop().name
    return re.sub(r"[-_]scripts.*$", "", inp.stem).replace("_", " ")


def main():
    ap = argparse.ArgumentParser(prog="promo_finder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("input")
    r.add_argument("--out", default="outputs")
    r.add_argument("--provider", default="heuristic", choices=["heuristic", "gemini", "openai", "anthropic", "file"])
    r.add_argument("--model", default=None)
    r.add_argument("--responses", default=None, help="dir of <ID>.json answers for --provider file")
    r.add_argument("--title", default=None, help="show title (default: folder/zip name)")
    r.add_argument("--promise", default=None, help="comma-separated title-promise keywords (default: last word of title)")
    r.add_argument("--strategy", default="funnel", choices=["funnel", "peak"],
                   help="funnel = premise episodes first; peak = strongest moments first (A/B test both)")
    r.add_argument("--lexicon", default=None, help="comma-separated genre packs to add (default: auto-detect)")
    r.add_argument("--weights", default=None, help="posting weights JSON from `python -m promo_finder.learn`")
    r.add_argument("--extra", type=int, default=10, help="judge this many candidates beyond 1-per-episode")
    a = ap.parse_args()

    t0 = time.time()
    inp = Path(a.input)
    title = a.title or guess_title(inp)
    # Microdrama titles put the twist last ("...Secretly a Billionaire", "...She's the CEO"): that word is the promise
    # a promo should deliver. Override with --promise "duke,heir".
    title_words = set(a.promise.lower().split(",")) if a.promise else {re.sub(r"[^a-z]", "", title.split()[-1].lower())}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    eps = load_show(inp)
    v = validate(eps)
    print(f"[1/5] parsed {v['episodes']} episodes, {v['beats']} beats, {len(v['issues'])} issues")
    packs, pack_hits = configure_lexicon(eps, a.lexicon.split(",") if a.lexicon else None)
    print(f"      genre packs: {packs or 'none'} (matches per episode: {pack_hits})")
    for e in eps:
        score_episode(e)
    names = show_names(eps)
    cands = generate(eps, names, title_words)
    dd = dedupe(cands)
    sl = shortlist(dd, extra=a.extra)
    print(f"[2/5] {len(cands)} candidates -> {len(dd)} after dedupe -> {len(sl)} shortlisted (every episode covered)")

    with open(out / "all_candidates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "rule_score", "duration_s", "segments", "hook_beat", "cliff_beat", "parts", "flags"])
        for c in dd:
            w.writerow([c.kind, c.score, c.duration, " + ".join(f"Ep{s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in c.segments),
                        c.hook_beat.text, c.cliff_beat.text, json.dumps(c.parts), ",".join(c.flags)])

    epmap = {e.num: e for e in eps}
    if a.provider == "heuristic":
        results = [{"cand": c, "rule_cand": c, "verdict": None, "problems": []} for c in sl]
        print("[3/5] judge skipped (heuristic provider)")
    else:
        print(f"[3/5] judging {len(sl)} candidates with {a.provider} {a.model or '(default model)'}")
        results = judge_all(sl, epmap, title, a.provider, a.model, out,
                            Path(a.responses) if a.responses else None)
    if a.provider not in ("heuristic", "file"):
        failed = sum(1 for r in results if not r["verdict"])
        if failed:
            print(f"WARNING: {failed}/{len(results)} judge calls failed (see judge_problems); those promos fall back to rules")
        if results and failed == len(results):
            print("ERROR: every judge call failed (check API key / model name). Writing rules-only output and exiting 2.")
    judged_ok = sum(1 for r in results if r["verdict"]) if a.provider != "heuristic" else 0
    if a.provider == "file" and not judged_ok:
        print("WARNING: no judge answers found (--responses); this output is rules-only")
    rows, rejected = build_rows(results, title, title_words, story_moments(eps), a.strategy)
    if a.weights:
        from .rank import order_rows
        rows = order_rows(rows, json.loads(Path(a.weights).read_text()))
    print(f"[4/5] ranked {len(rows)} promos, {len(rejected)} rejected by judge")
    label = a.provider if (a.provider == "heuristic" or judged_ok) else f"rules only (judge {a.provider} returned nothing)"
    meta = {"show": title, "provider": label, "judged_ok": judged_ok, "model": a.model, "strategy": a.strategy, "lexicon_packs": packs, "episodes": len(eps), "candidates": len(cands),
            "deduped": len(dd), "judged": len(sl) if a.provider != "heuristic" else 0, "seconds": round(time.time() - t0, 1),
            "spoken_names": sorted(names), "title_words": sorted(title_words), "parse_issues": v["issues"]}
    write_outputs(rows, rejected, out, meta)
    print(f"[5/5] wrote {out}/cut_sheet.md, cut_sheet.html, promos_ranked.csv/json in {meta['seconds']} s")
    if a.provider not in ("heuristic", "file") and results and all(not r["verdict"] for r in results):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
