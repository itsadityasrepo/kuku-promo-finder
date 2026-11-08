"""Automatic quality checks on a finished run.

python -m promo_finder.evaluate <run_dir> <show-folder-or-zip> [--compare <other_run_dir>]
Writes <run_dir>/eval/metrics.json and eval/report.md. Nothing here needs a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .features import score_episode
from .parse import load_show


def spearman(a, b):
    def ranks(x):
        o = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for k, i in enumerate(o):
            r[i] = k
        return r
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    d = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return round(1 - 6 * d / (n * (n * n - 1)), 3)


def cov(segs):
    return {(s["episode"], t) for s in segs for t in range(int(s["start_s"]), int(s["end_s"]) + 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("input")
    ap.add_argument("--compare", default=None)
    a = ap.parse_args()
    run = Path(a.run)
    data = json.loads((run / "promos_ranked.json").read_text())
    P, R = data["promos"], data["rejected"]
    eps = {e.num: e for e in load_show(a.input)}
    for e in eps.values():
        score_episode(e)
    beat = {b.id: b for e in eps.values() for b in e.beats}
    last_content = {n: [b for b in e.beats if b.kind != "camera"][-1].id for n, e in eps.items()}

    m = {"promos": len(P), "rejected_by_judge": len(R)}
    durs = [p["duration_s"] for p in P]
    m["duration_in_20_60"] = sum(19 <= d <= 61 for d in durs)
    m["duration_in_25_45_sweet_spot"] = sum(25 <= d <= 45 for d in durs)
    first = [beat[p["segments"][0]["first_beat"]] for p in P]
    m["opens_on_dialogue_or_action"] = sum(b.kind in ("dialogue", "action", "sfx") for b in first)
    m["opens_on_strong_hook_beat(rule_hook>=2)"] = sum(b.hook >= 2 for b in first)
    m["opens_on_dangling_reply"] = sum(b.kind == "dialogue" and b.text.lower().startswith(("...", "and ", "but ", "because")) for b in first)
    m["ends_on_episode_final_beat"] = sum(p["segments"][-1]["last_beat"] == last_content[p["segments"][-1]["episode"]] for p in P)
    def splits(bid):
        b = beat[bid]
        e = eps[b.ep]
        nxt = next((x for x in e.beats[b.idx + 1:] if x.kind != "camera"), None)
        return b.kind == "dialogue" and b.text.rstrip().endswith(("...", "…")) and nxt is not None and \
            nxt.kind == "dialogue" and (nxt.speaker == b.speaker or nxt.text.lstrip().startswith(("...", "…")))
    m["cuts_mid_sentence"] = sum(splits(s["last_beat"]) for p in P for s in p["segments"])
    post = [p for p in P if p.get("wave", "") != "bench"]
    m["post_list_size"] = len(post)
    m["post_list_failing_own_gates"] = [p["id"] for p in post if p.get("gate_failures")]
    m["post_list_multi_segment"] = sum(len(p["segments"]) > 1 for p in post)
    m["auto_fixes_applied"] = sum(1 for p in P for x in p.get("judge_problems", []) if x.startswith("auto_fix"))
    m["multi_segment"] = sum(len(p["segments"]) > 1 for p in P)
    m["cross_episode"] = sum(len({s["episode"] for s in p["segments"]}) > 1 for p in P)
    m["ad_policy_flagged"] = sum(p["ad_policy_risk"] not in ("none", "", None) for p in P)
    m["episodes_in_top10"] = sorted({p["segments"][0]["episode"] for p in P[:10]})
    m["source_counts"] = {}
    for p in P:
        m["source_counts"][p["source"]] = m["source_counts"].get(p["source"], 0) + 1
    probs = [x for p in P for x in p.get("judge_problems", [])]
    m["judge_problems"] = probs
    # judge vs rules: boundary moves and rank agreement
    moved = []
    for p in P:
        if p["source"] != "model":
            continue
        rs, js = p["rule_segments"], p["segments"]
        moved.append({"id": p["id"], "start_shift_s": round(js[0]["start_s"] - rs[0]["start_s"], 1) if js[0]["episode"] == rs[0]["episode"] else None,
                      "end_shift_s": round(js[-1]["end_s"] - rs[-1]["end_s"], 1) if js[-1]["episode"] == rs[-1]["episode"] else None,
                      "segments_rule": len(rs), "segments_judge": len(js)})
    if moved:
        kept = [x for x in moved if x["start_shift_s"] == 0 and x["end_shift_s"] == 0 and x["segments_rule"] == x["segments_judge"]]
        m["judge_kept_rule_boundaries_exactly"] = len(kept)
        m["judge_moved_boundaries"] = len(moved) - len(kept)
        m["median_abs_start_shift_s"] = sorted(abs(x["start_shift_s"] or 0) for x in moved)[len(moved) // 2]
        m["median_abs_end_shift_s"] = sorted(abs(x["end_shift_s"] or 0) for x in moved)[len(moved) // 2]
        m["judge_resegmented"] = sum(x["segments_rule"] != x["segments_judge"] for x in moved)
        mp = [p for p in P if p["source"] == "model"]
        m["spearman_rule_score_vs_judge_quality"] = spearman([p["rule_score"] for p in mp], [p["quality"] for p in mp])
        # do rules predict rejection?
        if R:
            import statistics as st
            m["mean_rule_score_accepted"] = round(st.mean(p["rule_score"] for p in mp), 2)
            m["mean_rule_score_rejected"] = round(st.mean(x["rule_score"] for x in R), 2)
    # naive baseline: "last 40 s of every episode"
    soft = 0
    for n, e in eps.items():
        lb = beat[last_content[n]]
        if lb.cliff < 1.2:
            soft += 1
    m["naive_baseline_last40s_soft_endings"] = f"{soft}/{len(eps)} episodes end on a low-cliff beat (cliff<1.2)"
    if a.compare:
        o = json.loads((Path(a.compare) / "promos_ranked.json").read_text())["promos"]
        def overlap(x, ys):
            cx = cov(x["segments"])
            return any(len(cx & cov(y["segments"])) / len(cx | cov(y["segments"])) > 0.3 for y in ys)
        m["top10_overlap_with_compare"] = sum(overlap(x, o[:10]) for x in P[:10])
        m["top10_compare_eps"] = sorted({p["segments"][0]["episode"] for p in o[:10]})
    out = run / "eval"
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps({"metrics": m, "boundary_moves": moved}, indent=1))
    lines = ["# Automatic checks", ""] + [f"- **{k}**: {v}" for k, v in m.items() if k != "judge_problems"]
    if probs:
        lines += ["", "## Judge output problems (caught by validation)", ""] + [f"- {x}" for x in probs]
    (out / "report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
