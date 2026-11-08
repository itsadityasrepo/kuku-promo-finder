"""Test suite. No pytest needed:  python tests/run_tests.py  [path/to/kuku_input_pack.zip]

Covers: parsing, word matching, the split-sentence guard, the judge validator (invented IDs, length,
hook-in-3s auto-fix), the three real API connectors against a local fake server, and the planted-promo
held-out test show.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from promo_finder.candidates import Candidate, Segment, content  # noqa: E402
from promo_finder.features import _has, LEX, configure_lexicon, score_episode  # noqa: E402
from promo_finder.judge import apply_verdict, build_prompt, judge_all  # noqa: E402
from promo_finder.parse import load_show  # noqa: E402

SYN = ROOT / "tests" / "synthetic_show" / "The Waitress Was His Wife"
passed, failed = 0, []


def check(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name} {detail}")


if not SYN.exists():
    subprocess.run([sys.executable, str(ROOT / "tests" / "make_synthetic_show.py")], check=True)

print("parsing")
eps = load_show(SYN)
check("synthetic show: 4 episodes, 94 beats", len(eps) == 4 and sum(len(e.beats) for e in eps) == 94)
if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
    k = load_show(sys.argv[1])
    check("Kuku pack: 50 episodes, 3727 beats", len(k) == 50 and sum(len(e.beats) for e in k) == 3727)

print("word matching")
check("'hang' does not match 'change'", _has("People change their minds", ["hang$"]) == 0)
check("'betray' matches 'betrayed'", _has("she was betrayed", ["betray"]) == 1)
check("'fire$' does not match 'fireplace'", _has("by the fireplace", ["fire$"]) == 0)
packs, _ = configure_lexicon(eps)
check("genre auto-detect picks 'modern' for the CEO show", packs == ["modern"], packs)

print("split-sentence guard")
for e in eps:
    score_episode(e)
ep2 = {e.num: e for e in eps}[2]
split = next(b for b in ep2.beats if b.text.endswith("company..."))
check("a line that continues in the next beat can never be a cut point", split.cliff <= -2, split.cliff)

print("judge validator")
ep1 = {e.num: e for e in eps}[1]
cb = content(ep1.beats)
base = Candidate("single", [Segment(1, [b for b in cb if 36 <= b.start <= 64])])
base.id = "T"
p = build_prompt(base, {e.num: e for e in eps}, "test")
check("prompt carries no episode summary (standalone must be judged cold)", "LOGLINE" not in p["user"] and
      "charity gala, waitress Mia is humiliated" not in p["user"])
ids = {b.start: b.id for b in ep1.beats}
_, probs = apply_verdict(base, {"is_promo": True, "segments": [["E1-B999", ids[66]]]}, {1: ep1}, p["beat_ids"])
check("invented beat ID is rejected", any("unknown beat id" in x for x in probs), probs)
_, probs = apply_verdict(base, {"is_promo": True, "segments": [[ids[8], ids[74]]]}, {1: ep1}, p["beat_ids"])
check("clip longer than 60 s is rejected", any("outside 20-60" in x for x in probs), probs)
new, probs = apply_verdict(base, {"is_promo": True, "segments": [[ids[26], ids[63]]],
                                  "hook": "Vanessa slaps Mia hard across the face"}, {1: ep1}, p["beat_ids"])
check("hook 5 s in -> start auto-moved to the hook", any(x.startswith("auto_fix: start moved") for x in probs)
      and abs(new.segments[0].start - 31.0) < 0.01, (probs, new.segments[0].start))
new, probs = apply_verdict(base, {"is_promo": True, "segments": [[ids[31], ids[63]]],
                                  "hook": "Vanessa slaps Mia hard across the face"}, {1: ep1}, p["beat_ids"])
check("valid verdict passes untouched", not probs and new.duration == 35.0, (probs, new.duration))
_, probs = apply_verdict(base, {"is_promo": True, "segments": [[ids[31], ids[63]]], "hook": "x"}, {1: ep1}, p["beat_ids"])
check("a vague hook quote is flagged, not silently matched", any(x.startswith("hook_unverified") for x in probs), probs)


print("API connectors against a local fake server")
ANSWER = {"is_promo": True, "segments": [], "hook": "Vanessa slaps Mia hard across the face", "cliffhanger": "y", "why": "z",
          "scores": {"hook": 4, "cliffhanger": 4, "standalone": 3, "emotion": 4}}
seen = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append((self.path.split("?")[0], body))
        txt = json.dumps(ANSWER)
        if "chat/completions" in self.path:
            out = {"choices": [{"message": {"content": txt}}]}
        elif "generateContent" in self.path:
            out = {"candidates": [{"content": {"parts": [{"text": txt}]}}]}
        else:
            out = {"content": [{"type": "text", "text": txt}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


srv = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}"
env_keep = dict(os.environ)
_cache = tempfile.mkdtemp()
os.environ.update({"PROMO_JUDGE_CACHE": _cache, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
                   "OPENAI_BASE_URL": url + "/v1", "OPENAI_API_KEY": "k", "PROMO_GEMINI_URL": url,
                   "GEMINI_API_KEY": "k", "PROMO_ANTHROPIC_URL": url, "ANTHROPIC_API_KEY": "k"})
ANSWER["segments"] = [[ids[31], ids[63]]]
with tempfile.TemporaryDirectory() as td:
    for prov in ("openai", "gemini", "anthropic"):
        res = judge_all([base], {1: ep1}, "test", prov, None, Path(td) / prov, log=lambda *a: None)
        r = res[0]
        check(f"{prov}: request sent, JSON parsed, verdict applied",
              r["verdict"] and r["verdict"]["scores"]["hook"] == 4 and abs(r["cand"].segments[0].start - 31) < .01,
              r["problems"])
paths = [s[0] for s in seen]
check("hit the right endpoints", any("chat/completions" in x for x in paths) and any("generateContent" in x for x in paths)
      and any(x.endswith("/v1/messages") for x in paths), paths)
os.environ.clear()
os.environ.update(env_keep)
srv.shutdown()

print("held-out planted test (rules only)")
with tempfile.TemporaryDirectory() as td:
    subprocess.run([sys.executable, "-m", "promo_finder", "run", str(SYN), "--out", td], cwd=ROOT, check=True,
                   capture_output=True)
    out = subprocess.run([sys.executable, str(ROOT / "tests" / "score_planted.py"), td], capture_output=True, text=True)
    summ = json.loads(out.stdout)["summary"]
    check(f"planted show: {summ}", "3/3" in summ and "4/4" in summ, summ)

print(f"\n{passed} passed, {len(failed)} failed" + (f": {failed}" if failed else ""))
sys.exit(1 if failed else 0)
