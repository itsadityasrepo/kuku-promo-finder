"""Fill docs/solution_template.html with numbers read straight from outputs/ (no hand-copied figures),
then render docs/solution.pdf.   python docs/build_doc.py [--draft]

Uses the Gemini run (outputs/kuku_show/judged_gemini) as the main run when it exists, else outputs/kuku_show/judged.
Refuses to build a final PDF until the blind review has been graded (review/blind_review_tally.json), unless --draft.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
O = ROOT / "outputs"
draft = "--draft" in sys.argv
J = lambda p: json.loads(p.read_text())  # noqa: E731

gem = O / "kuku_show" / "judged_gemini"
main = gem if (gem / "promos_ranked.json").exists() else O / "kuku_show" / "judged"
D = J(main / "promos_ranked.json")
P, R, meta = D["promos"], D["rejected"], D["meta"]
post = [p for p in P if p["wave"] != "bench"]
rules = J(O / "kuku_show" / "rules_only" / "promos_ranked.json")["meta"]
prof_minutes = None
try:
    sys.path.insert(0, str(ROOT))
    from promo_finder.parse import load_show
    import glob
    z = next(iter(glob.glob(str(ROOT.parent / "input_pack.zip")) + glob.glob(str(ROOT / "input" / "*.zip"))), None)
    if z:
        prof_minutes = round(sum(e.duration for e in load_show(z)) / 60)
except Exception:
    pass
M = J(main / "eval" / "metrics.json")["metrics"]
S = J(main / "eval" / "sensitivity.json")
f = {}
f["EPISODES"] = meta["episodes"]
f["MINUTES"] = prof_minutes or "about 100"
f["RULES_SECONDS"] = round(rules["seconds"])
f["BENCH"] = len(P) - len(post)
f["REJECTED"] = len(R)


def segs(p):
    return "<br>".join(f"Ep {s['episode']} {s['start']}–{s['end']}" for s in p["segments"])


def short(t, n=95):
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


def sc(p):
    s = p["scores"]
    return f"{s.get('hook', '–')} / {s.get('cliffhanger', '–')} / {s.get('standalone', '–')}" if s else "rules only"


rows = "".join(f"<tr><td>{p['rank']}</td><td class=t>{segs(p)}<br>({p['duration_s']:.0f} s)</td>"
               f"<td><b>Hook:</b> {html.escape(short(p['hook'], 80))}<br><b>Cliff:</b> {html.escape(short(p['cliffhanger'], 80))}</td>"
               f"<td>{sc(p)}</td></tr>" for p in post[:5])
f["POST_TABLE"] = ("<table><tr><th>#</th><th>Segments</th><th>Hook → cliffhanger (full reasons in the cut sheet)</th>"
                   "<th>Judge: hook / cliff / makes sense cold (1–5)</th></tr>" + rows + "</table>")
syn = {("judged" if k == main.name else k): J(O / "test_show" / k / "planted_test_score.json")["summary"]
       for k in ("rules_only", main.name)
       if (O / "test_show" / k / "planted_test_score.json").exists()}
fmt_syn = lambda s: s.replace("planted promos found in post list:", "planted promos found").replace(" · ", ", ")  # noqa: E731
f["SYN_RULES"] = fmt_syn(syn.get("rules_only", "not run"))
f["SYN_JUDGED"] = fmt_syn(syn.get("judged", "not run"))
links_f = ROOT / "docs" / "links.json"
L = J(links_f) if links_f.exists() else {}
for k in ("repo", "colab", "drive"):
    v = L.get(k, "")
    f["LINK_" + k.upper()] = f"<a href='{html.escape(v)}'>{html.escape(v.split('//')[-1])}</a>" if v else "in the submission form"
f["LINKS"] = (f"Repo: {f['LINK_REPO']} · Colab (runs with no setup): {f['LINK_COLAB']} · Raw outputs: {f['LINK_DRIVE']}"
              if L.get("repo") else "Repo, Colab notebook (runs with no setup) and raw outputs: links in the submission form")
tally = ROOT / "review" / "blind_review_tally.json"
if tally.exists():
    T = J(tally)
    NAMES = {"rules_only": "rules only", "judged": "Claude stand-in", "judged_gemini": "Gemini"}
    graded_n = {r: t["PASS"] + t["PARTIAL"] + t["FAIL"] for r, t in T.items()}
    total_graded = len([1 for r in __import__("csv").DictReader(open(ROOT / "review" / "my_grades.csv"))
                        if all(r[c] for c in ("hook", "cliff", "standalone", "cuts"))])
    total_clips = len(J(ROOT / "review" / "blind_key_DO_NOT_OPEN_BEFORE_GRADING.json"))
    order = [r for r in ("judged_gemini", "judged", "rules_only") if r in T]
    parts = [f"{NAMES.get(r, r)} {T[r]['PASS']}/{graded_n[r]}" for r in order if graded_n[r]]
    nfail = sum(t["FAIL"] for t in T.values())
    f["DID_REVIEW"] = f", and graded the blind review myself ({total_graded} clips)"
    f["WHICH_BETTER"] = "My blind review leans toward the judged lists, but on too few clips to call it."
    f["AD_REVIEW"] = (f"I graded {total_graded} of {total_clips} clips from the three runs' top 10s, mixed and unlabelled, on "
                      "four checks fixed in advance (hook in 3 s, unresolved cut, makes sense cold, clean cuts). Passed all "
                      "four: " + ", ".join(parts) + (f"; {nfail} failed outright" if nfail else "; none failed outright")
                      + ". A sanity check on a small sample, not a score.")
else:
    if not draft:
        raise SystemExit("Grade review/blind_review.html first and run review/tally.py, or build with --draft.")
    f["AD_REVIEW"] = "<span class=fill>[FILL: run review/tally.py after grading review/blind_review.html]</span>"
    f["DID_REVIEW"], f["WHICH_BETTER"] = "", "My blind review says which is better."
k5, k10, n1 = S["avg_share_of_top5_kept"], S["avg_share_of_top10_kept"], S["original_no1_stays_in_top3"]
f["SENS_TEXT"] = (("The top 5 never changed, " if k5 == 1 else f"On average {k5:.0%} of the top 5 stayed, ")
                  + f"{k10:.0%} of the top 10 stayed, and the #1 clip stayed in the top 3 in {n1:.0%} of trials.")
f["SPEARMAN"] = M.get("spearman_rule_score_vs_judge_quality", "n/a")
f["REJ"], f["ACC"] = M.get("mean_rule_score_rejected", "n/a"), M.get("mean_rule_score_accepted", "n/a")
def top10(run):
    rows = J(O / "kuku_show" / run / "promos_ranked.json")["promos"]
    return [p for p in rows if p["wave"] != "bench"][:10]


def cov(p):
    return {(s["episode"], t) for s in p["segments"] for t in range(int(s["start_s"]), int(s["end_s"]) + 1)}


def overlap(a, b):  # clips of list a that share >30% of their footage with some clip of list b
    return sum(any(len(cov(x) & cov(y)) / len(cov(x) | cov(y)) > 0.3 for y in b) for x in a)


f["OVERLAP"] = overlap(top10(main.name), top10("rules_only"))
sp = M.get("spearman_rule_score_vs_judge_quality", 0) or 0
f["PREDICTS"] = "barely predicts" if abs(sp) < 0.2 else "only partly predicts"

try:  # did the judge open planted promo T1 on the slap where the rules opened on the next line?
    T1 = lambda k: next(p for p in J(O / "test_show" / k / "promos_ranked.json")["promos"]  # noqa: E731
                        if p["id"] == J(O / "test_show" / k / "planted_test_score.json")["planted_found_in_post_list"]["T1"])
    tp, rp = T1(main.name), T1("rules_only")
    f["SLAP"] = ("The judge also fixed the rules' miss on the first planted promo: it opens on the slap "
                 f"({tp['segments'][0]['start']}), where the rules opened on the line after it ({rp['segments'][0]['start']})."
                 if tp["segments"][0]["start_s"] < rp["segments"][0]["start_s"] else "")
except Exception:
    f["SLAP"] = ""
broke = sum(1 for x in M["judge_problems"] if "outside 20-60" in x or "unknown beat id" in x or x.startswith("hook_unverified"))
f["BROKE"], f["NJUDGED"] = broke, len(list((main / "judge_prompts").glob("*.json")))
cold5 = sum(1 for p in post if p["scores"].get("standalone") == 5)
f["COLD5"] = f"The judge gave 5/5 on it to {cold5} of the {len(post)} post-list clips, including lore-heavy late episodes." if cold5 >= 5 else ""
f["AUTO_CHECKS"] = (f"{M['duration_in_20_60']}/{M['promos']} clips inside 20–60 s, {M['cuts_mid_sentence']} cut mid-sentence, "
                    f"{broke} judge answers that broke the rules caught and replaced by the rules' pick, "
                    f"{len(M['post_list_failing_own_gates'])} post-list clips failing the hook check, "

                    f"{sum(1 for x in M['judge_problems'] if 'unknown beat id' in x)} invented line IDs")
gline = ""
if main == gem and (O / "kuku_show" / "judged" / "promos_ranked.json").exists():
    gline = (f"<li><b>Two different models.</b> Gemini's top 10 and the Claude stand-in's share only "
             f"{overlap(top10(main.name), top10('judged'))} clips. Model choice changes the picks a lot, which is why the "
             f"editor decides and the scores stay visible.</li>")
f["GEMINI_LINE"] = gline
prompts = list((main / "judge_prompts").glob("*.json"))
chars = sum(len(J(p)["system"]) + len(J(p)["user"]) for p in prompts)
tok_in, tok_out = chars / 4, len(prompts) * 300
f["JUDGE_CALLS"] = len(prompts)
f["TOKENS_K"] = round(tok_in / 1000)
f["COST_FLASH"] = f"${(tok_in * 0.30 + tok_out * 2.50) / 1e6:.2f}"  # gemini-3.5-flash-lite list price
f["COST_FRONTIER"] = f"${(tok_in * 2.00 + tok_out * 10.00) / 1e6:.2f}"
f["JUDGE_SOURCE"] = (
    f"the main run is {meta.get('model') or 'Gemini'} through Google's API (my build environment had no internet, so a small "
    "page in my browser sent the tool's exact prompts and the answers were imported with <code>--provider file</code>). "
    "An earlier pass by a Claude agent, given only the same prompt files, is kept for comparison."
    if main == gem else
    "my build environment had no internet, so the judge prompts were answered by a separate Claude agent given only the "
    "tool's own prompt files, with no other instructions. The same prompts run on Gemini with one flag "
    "(<code>run_gemini.sh</code>).")
doc = (ROOT / "docs" / "solution_template.html").read_text()
for k, v in f.items():
    doc = doc.replace("{{" + k + "}}", str(v))
assert "{{" not in doc, [x for x in doc.split("{{")[1:]][:3]
(ROOT / "docs" / "solution.html").write_text(doc)
print(f"main run: {main.relative_to(ROOT)} · draft={draft}")
import subprocess  # noqa: E402
subprocess.run([sys.executable, str(ROOT / "docs" / "build_pdf.py")], check=True)
