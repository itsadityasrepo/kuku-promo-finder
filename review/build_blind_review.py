"""Blind review: mixes the post lists of two (or more) runs, hides which run each clip came from,
shuffles them, and writes review/blind_review.html (grade in the browser, export CSV) plus a sealed key.

python review/build_blind_review.py <run_dir> <run_dir> [...] --input <show.zip>
python review/tally.py review/my_grades.csv          # un-blinds and tallies, after grading
"""
import argparse
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from promo_finder.parse import fmt, load_show  # noqa: E402

RUBRIC = [("hook", "Hook lands in the first 3 s for someone who has never seen the show"),
          ("cliff", "Cuts at an unresolved moment (the next line is NOT the answer)"),
          ("standalone", "Makes sense with zero context"),
          ("cuts", "Clean cut points: no half-sentence, no dangling opener")]

ap = argparse.ArgumentParser()
ap.add_argument("runs", nargs="+")
ap.add_argument("--input", required=True)
ap.add_argument("--top", type=int, default=10)
ap.add_argument("--seed", type=int, default=11)
a = ap.parse_args()
eps = {e.num: e for e in load_show(a.input)}

clips, key = {}, {}
for run in a.runs:
    P = json.loads((Path(run) / "promos_ranked.json").read_text())["promos"]
    for p in [p for p in P if p["wave"] != "bench"][:a.top]:
        sig = tuple((s["episode"], s["start_s"], s["end_s"]) for s in p["segments"])
        clips.setdefault(sig, p)
        key.setdefault(str(sig), []).append({"run": Path(run).name, "rank": p["rank"], "id": p["id"]})
order = list(clips)
random.Random(a.seed).shuffle(order)
cards, sealed = [], {}
for n, sig in enumerate(order, 1):
    cid = f"C{n:02d}"
    sealed[cid] = key[str(sig)]
    lines = []
    for ep, s0, s1 in sig:
        lines.append(f"<div class=seg>Episode {ep} · {fmt(s0)} → {fmt(s1)}</div>")
        for b in eps[ep].beats:
            if s0 - 0.01 <= b.start <= s1 and b.start < s1:
                who = b.speaker if b.kind == "dialogue" else b.kind.upper()
                lines.append(f"<div class={b.kind}><span>{fmt(b.start - s0)}</span> <b>{html.escape(who)}</b> {html.escape(b.text)}</div>")
        last = max((b for b in eps[ep].beats if b.start < s1), key=lambda b: b.idx)
        nxt = next((b for b in eps[ep].beats[last.idx + 1:] if b.kind != "camera"), None)
        if nxt and (ep, s0, s1) == sig[-1]:
            lines.append(f"<div class=after>After the cut: <b>{html.escape(nxt.speaker or nxt.kind.upper())}</b> {html.escape(nxt.text)}</div>")
    radios = "".join(
        f"<fieldset><legend>{html.escape(t)}</legend>" + "".join(
            f"<label><input type=radio name={cid}-{k} value={v}> {lab}</label>" for v, lab in
            (("ok", "✓ yes"), ("weak", "~ weak"), ("broken", "✗ no"))) + "</fieldset>" for k, t in RUBRIC)
    dur = sum(s1 - s0 for _, s0, s1 in sig)
    cards.append(f"<article id={cid}><h2>{cid} <small>{dur:.1f} s · {len(sig)} segment{'s' if len(sig) > 1 else ''}</small></h2>"
                 f"<div class=script>{''.join(lines)}</div>{radios}<input class=note id={cid}-note placeholder='note (optional)'></article>")

(Path(__file__).parent / "blind_key_DO_NOT_OPEN_BEFORE_GRADING.json").write_text(json.dumps(sealed, indent=1))
page = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Blind promo review</title>
<style>:root{{--bg:#f6f6f3;--card:#fff;--ink:#1b1c1a;--mute:#666a63;--line:#dfe1da;--acc:#245c73}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151615;--card:#1f201e;--ink:#e9eae6;--mute:#a2a59d;--line:#353731;--acc:#7cb6cf}}}}
body{{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--ink);max-width:820px;margin:0 auto;padding:16px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:14px 0}}
h2{{margin:0 0 6px;font-size:17px}}small{{color:var(--mute);font-weight:400}}.script{{font-size:14px;max-height:340px;overflow:auto;border-left:3px solid var(--line);padding-left:10px}}
.script span{{font-family:ui-monospace,monospace;color:var(--mute);font-size:12px}}.camera,.sfx{{color:var(--mute);font-style:italic}}.seg{{font-weight:600;color:var(--acc);margin-top:6px}}
.after{{margin-top:6px;padding:6px 8px;background:var(--bg);border-radius:6px;color:var(--mute)}}fieldset{{border:0;padding:4px 0;margin:0}}legend{{font-size:14px;padding:0}}
label{{margin-right:14px;font-size:14px;white-space:nowrap}}.note{{width:100%;box-sizing:border-box;margin-top:6px;padding:6px;font:inherit;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px}}
.bar{{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
button{{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid var(--acc);background:var(--acc);color:#fff;cursor:pointer}}</style>
<h1>Blind promo review</h1>
<p>{len(order)} clips from two versions of the tool, mixed and unlabelled. Read each clip's script (times are from the clip's start) and the line right after the cut, then mark the four checks. Decide before you look anything up. When done, export and run <code>python review/tally.py</code> on the CSV.</p>
<div class=bar><span id=progress></span><button id=export>Export my grades (CSV)</button></div>
{''.join(cards)}
<script>
const IDS={json.dumps([f"C{n:02d}" for n in range(1, len(order) + 1)])},K={json.dumps([k for k, _ in RUBRIC])},S="blindreview";
let st={{}};try{{st=JSON.parse(localStorage.getItem(S)||"{{}}")}}catch(e){{}}
function save(){{try{{localStorage.setItem(S,JSON.stringify(st))}}catch(e){{}}}}
function prog(){{const done=IDS.filter(c=>K.every(k=>st[c+"-"+k])).length;document.getElementById("progress").textContent=done+" of "+IDS.length+" clips graded"}}
document.querySelectorAll("input[type=radio]").forEach(r=>{{if(st[r.name]===r.value)r.checked=true;r.onchange=()=>{{st[r.name]=r.value;save();prog()}}}});
document.querySelectorAll(".note").forEach(n=>{{n.value=st[n.id]||"";n.oninput=()=>{{st[n.id]=n.value;save()}}}});
document.getElementById("export").onclick=()=>{{let c="clip,"+K.join(",")+",note\\n";IDS.forEach(i=>{{c+=[i,...K.map(k=>st[i+"-"+k]||""),'"'+(st[i+"-note"]||"").replace(/"/g,'""')+'"'].join(",")+"\\n"}});
const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([c],{{type:"text/csv"}}));a.download="my_grades.csv";a.click()}};prog();
</script></html>"""
(Path(__file__).parent / "blind_review.html").write_text(page)
print(f"{len(order)} clips -> review/blind_review.html (key sealed in review/blind_key_DO_NOT_OPEN_BEFORE_GRADING.json)")
