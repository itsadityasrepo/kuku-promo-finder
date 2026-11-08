"""Close the loop: learn the posting weights from what editors actually accept.

python -m promo_finder.learn editor_feedback.csv [more.csv ...] --out weights.json
then: python -m promo_finder run show.zip --weights weights.json

Input = the CSV exported from cut_sheet.html (one row per clip the editor accepted or rejected,
with the same features the ranker uses). Fits a small logistic regression with numpy. With fewer than
~30 decisions the fit is noisy, so it is blended toward the hand-set weights.
Later the label can be real performance (e.g. CTR above median) instead of accept/reject.
"""
from __future__ import annotations

import argparse
import csv
import json

from .rank import STRATEGIES

FEATS = ["quality", "rule", "premise", "title", "hard_risk", "mild_risk", "spoiler", "extra_segments"]
FIXED = ["hard_risk", "mild_risk"]


def fit(X, y, l2=1.0, steps=3000, lr=0.1):
    import numpy as np
    X, y = np.asarray(X, float), np.asarray(y, float)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    w, b = np.zeros(Z.shape[1]), 0.0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        w -= lr * (Z.T @ (p - y) / len(y) + l2 * w / len(y))
        b -= lr * float((p - y).mean())
    return w / sd  # back to the original feature scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--out", default="weights.json")
    ap.add_argument("--base", default="funnel", choices=list(STRATEGIES))
    a = ap.parse_args()
    X, y = [], []
    for path in a.csv:
        for r in csv.DictReader(open(path)):
            if r["decision"] not in ("accept", "reject"):
                continue
            X.append([float(r.get(f, 0) or 0) for f in FEATS])
            y.append(1.0 if r["decision"] == "accept" else 0.0)
    n = len(y)
    if n < 6 or len(set(y)) < 2:
        raise SystemExit(f"Need at least 6 decisions with both accepts and rejects (got {n}).")
    raw = fit(X, y)
    learned = {f: float(v) for f, v in zip(FEATS, raw)}
    base = STRATEGIES[a.base]
    # put the learned weights on the same overall scale as the hand-set ones (signs are kept)
    scale = sum(abs(v) for v in learned.values()) / max(sum(abs(base.get(f, 0)) for f in FEATS), 1e-9)
    learned = {f: v / (scale or 1) for f, v in learned.items()}
    trust = min(1.0, n / 30)  # with little data, stay close to the hand-set weights
    blended = {f: round(trust * learned[f] + (1 - trust) * base.get(f, 0), 4) for f in FEATS}
    for f in FIXED:  # ad-policy penalties are a policy choice, not something to learn from a few clicks
        blended[f] = base[f]
    json.dump(blended, open(a.out, "w"), indent=1)
    print(f"{n} decisions ({int(sum(y))} accepted). Trust in data: {trust:.0%}.")
    for f in FEATS:
        print(f"  {f:15s} hand-set {base.get(f, 0):+.3f}  learned {learned[f]:+.3f}  -> used {blended[f]:+.3f}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
