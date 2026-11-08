"""How much does the ranking depend on my hand-set weights?

python -m promo_finder.sensitivity <run_dir> [--trials 500] [--spread 0.3]

Every posting weight AND every quality weight (hook/cliff/standalone/emotion) is multiplied by a random
factor in [1-spread, 1+spread], the clips are re-ranked, and we count how often the original top picks survive.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .rank import STRATEGIES, W, order_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--trials", type=int, default=500)
    ap.add_argument("--spread", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    data = json.loads((Path(a.run) / "promos_ranked.json").read_text())
    rows, strategy = data["promos"], data["meta"].get("strategy", "funnel")
    base_w = STRATEGIES[strategy]
    base = order_rows([dict(r) for r in rows], base_w)
    top = lambda rs, n: [r["id"] for r in rs if r["wave"] != "bench"][:n]
    b5, b10, b1 = set(top(base, 5)), set(top(base, 10)), top(base, 1)[0]
    rnd = random.Random(a.seed)
    keep5 = keep10 = first_in_top3 = 0
    appear = {}
    for _ in range(a.trials):
        w = {k: v * rnd.uniform(1 - a.spread, 1 + a.spread) for k, v in base_w.items()}
        qw = {k: v * rnd.uniform(1 - a.spread, 1 + a.spread) for k, v in W.items()}
        trial = []
        for r in rows:
            r2 = json.loads(json.dumps(r))
            if r2["scores"]:
                tot = sum(qw.values())
                r2["features"]["quality"] = sum(qw[k] * float(r2["scores"].get(k, 3)) for k in qw) / 5 / tot
            trial.append(r2)
        ranked = order_rows(trial, w)
        t5, t10 = set(top(ranked, 5)), set(top(ranked, 10))
        keep5 += len(t5 & b5) / max(len(b5), 1)
        keep10 += len(t10 & b10) / max(len(b10), 1)
        first_in_top3 += b1 in top(ranked, 3)
        for i in t10:
            appear[i] = appear.get(i, 0) + 1
    res = {"trials": a.trials, "spread": a.spread, "strategy": strategy,
           "avg_share_of_top5_kept": round(keep5 / a.trials, 3),
           "avg_share_of_top10_kept": round(keep10 / a.trials, 3),
           "original_no1_stays_in_top3": round(first_in_top3 / a.trials, 3),
           "share_of_trials_each_clip_is_in_top10": {k: round(v / a.trials, 2) for k, v in
                                                     sorted(appear.items(), key=lambda x: -x[1])}}
    out = Path(a.run) / "eval"
    out.mkdir(exist_ok=True)
    (out / "sensitivity.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "share_of_trials_each_clip_is_in_top10"}, indent=1))


if __name__ == "__main__":
    main()
