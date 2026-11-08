"""Grade a run on the synthetic show against tests/ground_truth.json (written before any run).
python tests/score_planted.py <run_dir>"""
import json
import sys
from pathlib import Path

gt = json.loads((Path(__file__).parent / "ground_truth.json").read_text())
run = Path(sys.argv[1])
data = json.loads((run / "promos_ranked.json").read_text())
promos = data["promos"]
post = [p for p in promos if p["wave"] != "bench"]


def span(p):
    return p["segments"][0]["start_s"], p["segments"][-1]["end_s"]


def overlap(p, ep, w):
    tot = sum(max(0, min(s["end_s"], w[1]) - max(s["start_s"], w[0])) for s in p["segments"] if s["episode"] == ep)
    return tot / (w[1] - w[0])


res = {"planted_found_in_post_list": {}, "planted_found_anywhere": {}, "traps": {}}
for t in gt["planted_promos"]:
    f = t["found_if"]

    def hit(p):
        if p["segments"][-1]["episode"] != t["episode"]:
            return False
        a, b = span(p)
        ok = True
        if "overlap_with_window_at_least" in f:
            ok &= overlap(p, t["episode"], t["window"]) >= f["overlap_with_window_at_least"]
        if "first_cut_between" in f:
            ok &= f["first_cut_between"][0] <= a <= f["first_cut_between"][1]
        if "last_cut_between" in f:
            ok &= f["last_cut_between"][0] <= b <= f["last_cut_between"][1]
        return ok
    res["planted_found_in_post_list"][t["id"]] = next((p["id"] for p in post if hit(p)), None)
    res["planted_found_anywhere"][t["id"]] = next((p["id"] for p in promos if hit(p)), None)
for x in gt["traps"]:
    ep = x["episode"]
    if x["kind"] == "split_sentence":
        bad = [p["id"] for p in promos for s in p["segments"] if s["episode"] == ep and abs(s["end_s"] - x["no_segment_may_end_at"]) < 0.05]
    elif "no_post_list_promo_may_end_after" in x:
        bad = [p["id"] for p in post if p["segments"][-1]["episode"] == ep and span(p)[1] > x["no_post_list_promo_may_end_after"]]
    else:
        n = sum(1 for p in post if p["segments"][0]["episode"] == ep)
        bad = [f"{n} promos"] if n > x["max_post_list_promos_from_episode"] else []
    res["traps"][x["id"] + " " + x["kind"]] = "avoided" if not bad else f"FELL IN: {bad}"
found = sum(v is not None for v in res["planted_found_in_post_list"].values())
avoided = sum(v == "avoided" for v in res["traps"].values())
res["summary"] = f"planted promos found in post list: {found}/{len(gt['planted_promos'])} · traps avoided: {avoided}/{len(gt['traps'])}"
(run / "planted_test_score.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
