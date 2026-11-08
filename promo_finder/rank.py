"""Turn judged candidates into a posting order + editor cut sheet."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from .parse import fmt

W = {"hook": 0.35, "cliffhanger": 0.30, "standalone": 0.25, "emotion": 0.10}
PREMISE_EPS = 5  # a click lands on Ep 1: promos from the first episodes pay off within minutes


def _transcript(c):
    out = []
    for s in c.segments:
        out.append(f"--- Ep {s.ep} {fmt(s.start)}-{fmt(s.end)} ---")
        for b in s.beats:
            who = f"{b.speaker}" if b.kind == "dialogue" else b.kind.upper()
            out.append(f"{fmt(b.start)} {who}: {b.text}")
    return out


def _heuristic_text(c):
    h, cl = c.hook_beat, c.cliff_beat
    kind = "line" if h.kind == "dialogue" else "action"
    why = (f"Opens on a {('high-intensity ' if h.hook >= 3 else '')}{kind}"
           f"{(' (' + h.tags + ')') if h.tags else ''} and cuts on "
           f"{'an unanswered question' if cl.text.rstrip().endswith('?') else 'an unresolved beat'}.")
    return {"hook": h.text, "cliffhanger": cl.text, "why": why, "hook_type": "rules", "editor_check":
            "Rules-only pick: watch the first 3 s and the cut point."}


HARD_RISK = {"sexual", "child", "graphic_violence", "sexual_content", "child_peril"}


def story_moments(eps):
    """beat id -> story-moment key. An episode that 'picks up directly' continues the previous
    episode's last scene, so a recap of Ep N's cliff in Ep N+1 is the SAME moment, not a new one."""
    key_of, prev_last = {}, None
    for e in sorted(eps, key=lambda x: x.num):
        note = (e.continuity + " " + e.scenes.get(min(e.scenes or {1: 0}), {}).get("heading", "")).lower()
        cont = any(k in note for k in ("picks up directly", "continuous", "immediately after"))
        first_scene = min(e.scenes) if e.scenes else 0
        for b in e.beats:
            # inherit only a key native to the previous episode: a recap links 2 episodes, it doesn't chain a whole arc
            inherit = cont and b.scene == first_scene and prev_last and prev_last.startswith(f"E{e.num - 1}S")
            k = prev_last if inherit else f"E{e.num}S{b.scene}"
            key_of[b.id] = k
        if e.beats:
            prev_last = key_of[e.beats[-1].id]
    return key_of


def build_rows(results, show_title, title_words, moment_of=None, strategy="funnel"):
    rows, rejected = [], []
    rs = [r["rule_cand"].score for r in results] or [0]
    lo, hi = min(rs), max(rs)
    for r in results:
        c, v, probs = r["cand"], r["verdict"], r["problems"]
        valid = bool(v) and v.get("is_promo", True) and not any(
            p.startswith(("unknown", "bad", "no valid", "duration", "segment", "segments")) for p in probs)
        if v and not v.get("is_promo", True):
            rejected.append({"id": c.id, "episode": c.segments[0].ep, "reason": v.get("why") or "model: no promo",
                             "rule_score": c.score, "rule_segments": [s.to_dict() for s in c.segments],
                             "editor_check": v.get("editor_check", "")})
            continue
        rule_q = (r["rule_cand"].score - lo) / (hi - lo or 1)
        if valid:
            sc = v.get("scores", {})
            q = sum(W[k] * float(sc.get(k, 3)) for k in W) / 5
            text = {k: v.get(k, "") for k in ("hook", "hook_type", "cliffhanger", "why", "editor_check")}
            source = "model"
        else:
            sc, q, text, source = {}, rule_q, _heuristic_text(c), "rules" + (" (judge fallback)" if v else "")
        ad = (v or {}).get("ad_policy_risk") or ("none" if not c.flags else ",".join(c.flags))
        spoil = (v or {}).get("spoiler_risk", "unknown")
        first_ep = c.segments[0].ep
        words = sorted(w for w in title_words if w in " ".join(b.text for b in c.beats).lower())
        risk_terms = set(str(ad).replace(" ", "").split(",")) | set(c.flags)
        feats = {"quality": q, "rule": rule_q, "premise": float(first_ep <= PREMISE_EPS), "title": float(bool(words)),
                 "hard_risk": float(bool(risk_terms & HARD_RISK)),
                 "mild_risk": float(not (risk_terms & HARD_RISK) and ad not in ("none", "", None)),
                 "spoiler": float(spoil == "high"), "extra_segments": float(len(c.segments) - 1)}
        reasons = []
        if feats["premise"]:
            reasons.append("premise episode: a viewer who taps through starts near the payoff")
        if words:
            reasons.append(f"delivers the title promise ({', '.join(words)})")
        if feats["hard_risk"]:
            reasons.append(f"ad-policy risk ({', '.join(sorted(risk_terms & HARD_RISK))}): a human must clear it first")
        elif feats["mild_risk"]:
            reasons.append(f"mild {ad} (slaps/punches are standard in this genre's ads): check the cut")
        if feats["spoiler"]:
            reasons.append("high spoiler risk")
        if len(c.segments) > 1:
            reasons.append(f"{len(c.segments)} segments: check each jump cut")
        # gate: a clip that fails the tool's own rules can't enter the post list
        gate = [p for p in probs if p.startswith(("hook_late", "hook_unverified"))]
        if v and not valid:
            gate.append("judge answer broke the rules; this is the rules' pick")
        if not (20.0 <= c.duration <= 60.0):
            gate.append("duration outside 20-60 s")
        rows.append({
            "id": c.id, "type": c.kind, "duration_s": c.duration,
            "quality": round(q, 3), "rule_score": r["rule_cand"].score, "source": source,
            "segments": [s.to_dict() for s in c.segments],
            "rule_segments": [s.to_dict() for s in r["rule_cand"].segments],
            "hook": text["hook"], "hook_type": text.get("hook_type", ""), "cliffhanger": text["cliffhanger"],
            "why": text["why"], "editor_check": text.get("editor_check", ""),
            "scores": sc, "ad_policy_risk": ad, "spoiler_risk": spoil, "flags": c.flags,
            "posting_reasons": reasons, "judge_problems": probs, "gate_failures": gate, "features": feats,
            "transcript": _transcript(c), "moment": (moment_of or {}).get(c.beats[0].id, f"E{first_ep}")})
    # two candidates can converge on the very same clip after the judge moves them: keep one
    uniq, seen_sig = [], {}
    for r in sorted(rows, key=lambda x: -x["quality"]):
        sig = tuple((s["episode"], s["start_s"], s["end_s"]) for s in r["segments"])
        if sig in seen_sig:
            seen_sig[sig].setdefault("merged_duplicates", []).append(r["id"])
            continue
        seen_sig[sig] = r
        uniq.append(r)
    return order_rows(uniq, STRATEGIES[strategy]), rejected


# Posting weights. They are hand-set starting points: `sensitivity.py` measures how much the
# ranking depends on them, and `learn.py` re-fits them from editor Accept/Reject feedback.
STRATEGIES = {
    # funnel: premise clips first (hypothesis: a tap that starts the viewer near the payoff converts better)
    "funnel": {"quality": 1.0, "rule": 0.06, "premise": 0.08, "title": 0.05, "hard_risk": -0.15,
               "mild_risk": -0.03, "spoiler": -0.05, "extra_segments": -0.03},
    # peak: strongest moments first, wherever they are in the series
    "peak": {"quality": 1.0, "rule": 0.06, "premise": 0.0, "title": 0.05, "hard_risk": -0.15,
             "mild_risk": -0.03, "spoiler": 0.0, "extra_segments": -0.03},
}
POST_LIST = 10


def order_rows(rows, weights):
    """Score with `weights`, then fill a post list of 10: gate-passing clips only, one per story moment.
    Everything else goes to the bench (alternate cuts of a moment are labelled as such)."""
    for r in rows:
        r["post_score"] = round(sum(weights.get(k, 0) * v for k, v in r["features"].items()), 3)
        r.pop("alt_cut_of", None)
        r["posting_reasons"] = [x for x in r["posting_reasons"] if not x.startswith("same story moment")]
    rows = sorted(rows, key=lambda x: -x["post_score"])
    post, bench, seen = [], [], {}
    for r in rows:
        m = r["moment"]
        if m in seen:
            r["alt_cut_of"] = seen[m]["id"]
            r["posting_reasons"].append(f"same story moment as {seen[m]['id']}: an A/B alternate cut")
        if len(post) < POST_LIST and m not in seen and not r["gate_failures"]:
            post.append(r)
        else:
            bench.append(r)
        seen.setdefault(m, r)
    ordered = post + bench
    for i, r in enumerate(ordered, 1):
        r["rank"] = i
        r["wave"] = ("post list - test wave 1" if i <= 5 else "post list - test wave 2") if i <= len(post) else "bench"
        if i <= len(post) and r["features"]["hard_risk"]:
            r["wave"] += " (clear ad policy first)"
    return ordered


def seg_str(r):
    return " + ".join(f"Ep{s['episode']} {s['start']}-{s['end']}" for s in r["segments"])


def write_outputs(rows, rejected, out: Path, meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    (out / "promos_ranked.json").write_text(json.dumps({"meta": meta, "promos": rows, "rejected": rejected}, indent=1))
    with open(out / "promos_ranked.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "wave", "id", "type", "segments", "duration_s", "hook", "cliffhanger", "why",
                    "hook", "cliff", "standalone", "emotion", "quality", "post_score", "ad_policy_risk",
                    "spoiler_risk", "source", "editor_check"])
        for r in rows:
            s = r["scores"]
            w.writerow([r["rank"], r["wave"], r["id"], r["type"], seg_str(r), r["duration_s"], r["hook"],
                        r["cliffhanger"], r["why"], s.get("hook", ""), s.get("cliffhanger", ""),
                        s.get("standalone", ""), s.get("emotion", ""), r["quality"], r["post_score"],
                        r["ad_policy_risk"], r["spoiler_risk"], r["source"], r["editor_check"]])
    post = [r for r in rows if r["wave"] != "bench"]
    bench = [r for r in rows if r["wave"] == "bench"]

    def md_block(r):
        segs = "\n".join(f"  - Segment {k}: Ep {s['episode']}  {s['start']} → {s['end']}" for k, s in enumerate(r["segments"], 1))
        return [f"### #{r['rank']} · {r['id']} · {r['duration_s']} s · {r['wave']}", segs,
                f"- **Hook:** {r['hook']}", f"- **Cliffhanger:** {r['cliffhanger']}", f"- **Why it works:** {r['why']}",
                f"- **Scores:** {r['scores'] or 'rules only'} · post score {r['post_score']}",
                f"- **Posting:** {'; '.join(r['posting_reasons']) or '-'}",
                f"- **Check before posting:** {r['editor_check'] or '-'}"
                + (f" · gate: {', '.join(r['gate_failures'])}" if r["gate_failures"] else ""), ""]
    md = [f"# Promo cut sheet · {meta['show']}", "",
          f"{meta['episodes']} episodes · strategy `{meta.get('strategy')}` · judge `{meta['provider']}` "
          f"{meta.get('model') or ''} · **{len(post)} to post**, {len(bench)} on the bench, {len(rejected)} rejected", "",
          "## Post list", ""]
    for r in post:
        md += md_block(r)
    md += ["## Bench (usable, lower priority, or an alternate cut)", ""]
    for r in bench:
        md += md_block(r)
    if rejected:
        md += ["## Rejected by the judge", ""] + [f"- {x['id']} Ep {x['episode']}: {x['reason']}" for x in rejected]
    (out / "cut_sheet.md").write_text("\n".join(md))

    def card(r):
        segs = "".join(f"<li>Ep {s['episode']} <b>{s['start']} → {s['end']}</b></li>" for s in r["segments"])
        tr = "<br>".join(html.escape(t) for t in r["transcript"])
        gate = f"<p class=warn>Gate: {html.escape(', '.join(r['gate_failures']))}</p>" if r["gate_failures"] else ""
        return f"""<section data-id="{r['id']}"><header><span class=rk>#{r['rank']}</span><span class=id>{r['id']}</span>
<span class=meta>{r['duration_s']} s · {html.escape(r['wave'])}</span></header><ol class=segs>{segs}</ol>
<p><b>Hook</b>{html.escape(r['hook'])}</p><p><b>Cliff</b>{html.escape(r['cliffhanger'])}</p><p><b>Why</b>{html.escape(r['why'])}</p>
<p class=m>Posting: {html.escape('; '.join(r['posting_reasons']) or '-')}<br>Check: {html.escape(r['editor_check'] or '-')}</p>{gate}
<details><summary>Script of this clip</summary><p class=t>{tr}</p></details>
<div class=fb><button data-v=accept>Accept</button><button data-v=reject>Reject</button><input placeholder="note (optional)"></div></section>"""
    rej = "".join(f"<li><b>{x['id']} · Ep {x['episode']}</b> {html.escape(x['reason'])}</li>" for x in rejected)
    feats = {r["id"]: r["features"] for r in rows}
    (out / "cut_sheet.html").write_text(f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Promo cut sheet</title><style>
:root{{--bg:#f7f5f0;--card:#fff;--ink:#1d1c1a;--mute:#6b675f;--line:#e4dfd5;--acc:#8a3b12;--ok:#1f6f43;--no:#9b2c2c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171614;--card:#211f1c;--ink:#ece8e1;--mute:#a19b90;--line:#36322c;--acc:#e08a5a;--ok:#5fbf8a;--no:#e07a7a}}}}
body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px;background:var(--bg);color:var(--ink)}}
h1{{font-size:22px;margin:8px 0 2px}}h2{{font-size:16px;margin:24px 0 6px;color:var(--acc)}}.sub{{color:var(--mute);margin:0 0 8px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:10px 0}}
section.accept{{border-color:var(--ok);box-shadow:inset 4px 0 0 var(--ok)}}section.reject{{opacity:.55;box-shadow:inset 4px 0 0 var(--no)}}
header{{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}.rk{{font-weight:700;font-size:18px}}.id{{font-family:ui-monospace,monospace;color:var(--mute)}}.meta{{color:var(--mute);font-size:13px}}
.segs{{margin:6px 0;padding-left:20px;font-family:ui-monospace,monospace;font-size:14px}}p{{margin:4px 0}}p b{{display:inline-block;min-width:52px;color:var(--mute);font-weight:600}}
.m{{color:var(--mute);font-size:13px}}.warn{{color:var(--no);font-size:13px}}.t{{font-family:ui-monospace,monospace;font-size:12px;color:var(--mute)}}
.fb{{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}}button{{font:inherit;padding:4px 12px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}}
.fb input{{flex:1;min-width:140px;font:inherit;padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}}
.bar{{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--line)}}
details.bench>summary{{cursor:pointer;color:var(--acc);font-weight:600;margin:20px 0 6px}}</style>
<h1>Promo cut sheet · {html.escape(meta['show'])}</h1>
<p class=sub>{meta['episodes']} episodes · {len(post)} to post · {len(bench)} on the bench · {len(rejected)} rejected · strategy {html.escape(str(meta.get('strategy')))} · judge {html.escape(meta['provider'])} {html.escape(meta.get('model') or '')}</p>
<div class=bar><span id=count class=m></span><button id=export>Export my decisions (CSV)</button><span class=m>Decisions feed <code>python -m promo_finder.learn</code>. If no file downloads, copy the text that appears.</span></div>
<textarea id=csvout hidden rows=6 style="width:100%;font:12px ui-monospace,monospace"></textarea>
<h2>Post list</h2>{''.join(card(r) for r in post)}
<details class=bench><summary>Bench: {len(bench)} more promos (lower priority or alternate cuts)</summary>{''.join(card(r) for r in bench)}</details>
<details class=bench><summary>Rejected by the judge: {len(rejected)}</summary><ul>{rej}</ul></details>
<script>
const FEATS={json.dumps(feats)};const KEY="cutsheet:"+{json.dumps(meta['show'])};let st={{}};
try{{st=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(st))}}catch(e){{}}}}
function paint(){{let a=0,r=0;document.querySelectorAll("section").forEach(s=>{{const d=st[s.dataset.id]||{{}};s.classList.toggle("accept",d.v=="accept");s.classList.toggle("reject",d.v=="reject");
const i=s.querySelector("input");if(i&&document.activeElement!==i)i.value=d.note||"";if(d.v=="accept")a++;if(d.v=="reject")r++}});document.getElementById("count").textContent=a+" accepted · "+r+" rejected"}}
document.querySelectorAll("section").forEach(s=>{{const id=s.dataset.id;s.querySelectorAll("button").forEach(b=>b.onclick=()=>{{st[id]=st[id]||{{}};st[id].v=st[id].v==b.dataset.v?"":b.dataset.v;save();paint()}});
s.querySelector("input").oninput=e=>{{st[id]=st[id]||{{}};st[id].note=e.target.value;save()}}}});
document.getElementById("export").onclick=()=>{{const cols=Object.keys(Object.values(FEATS)[0]||{{}});let csv="id,decision,note,"+cols.join(",")+"\\n";
for(const id in FEATS){{const d=st[id]||{{}};if(!d.v)continue;csv+=[id,d.v,'"'+(d.note||"").replace(/"/g,'""')+'"',...cols.map(c=>FEATS[id][c])].join(",")+"\\n"}}
const t=document.getElementById("csvout");t.hidden=false;t.value=csv;t.select();
try{{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{{type:"text/csv"}}));a.download="editor_feedback.csv";a.click()}}catch(e){{}}}};paint();
</script></html>""")
