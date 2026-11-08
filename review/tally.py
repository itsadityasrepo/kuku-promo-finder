"""Un-blind and tally a graded blind review.   python review/tally.py my_grades.csv
Verdict per clip: PASS = all four ✓ · PARTIAL = any ~ and no ✗ · FAIL = any ✗."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

key = json.loads((Path(__file__).parent / "blind_key_DO_NOT_OPEN_BEFORE_GRADING.json").read_text())
rows = list(csv.DictReader(open(sys.argv[1])))
crit = ["hook", "cliff", "standalone", "cuts"]
by_run = defaultdict(lambda: {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "ungraded": 0, "per_check_ok": defaultdict(int)})
for r in rows:
    marks = [r[c] for c in crit]
    v = "ungraded" if "" in marks else "FAIL" if "broken" in marks else "PARTIAL" if "weak" in marks else "PASS"
    for src in key[r["clip"]]:
        t = by_run[src["run"]]
        t[v] += 1
        for c in crit:
            t["per_check_ok"][c] += r[c] == "ok"
out = {run: {**{k: v for k, v in t.items() if k != "per_check_ok"}, "per_check_ok": dict(t["per_check_ok"])}
       for run, t in by_run.items()}
print(json.dumps(out, indent=1))
(Path(__file__).parent / "blind_review_tally.json").write_text(json.dumps(out, indent=1))
print("saved review/blind_review_tally.json (docs/build_doc.py reads it)")
