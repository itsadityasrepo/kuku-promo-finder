"""Builds demo/Promo_Finder.ipynb: a self-contained Colab notebook that carries the tool inside it
(no git clone needed) plus the synthetic test show, so anyone can run it without Kuku's scripts."""
import base64
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted((ROOT / "promo_finder").rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            z.write(p, p.relative_to(ROOT))
    for p in sorted((ROOT / "tests").rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            z.write(p, p.relative_to(ROOT))
PKG = base64.b64encode(buf.getvalue()).decode()


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s.strip().splitlines(True)}


def code(s):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip().splitlines(True)}


cells = [
    md("""# Promo Finder
Reads a microdrama's timestamped screenplays and returns a ranked **promo cut sheet**: for each clip, the episode, the start and end of every segment, the hook, the cliffhanger, why it works, and the posting order.

**Run all cells** (Runtime → Run all). By default it runs on a small built-in test show, so you can see it work without any confidential scripts. To use your own show, set `USE_DEMO_SHOW = False` in step 2 and upload a `.zip` of the episode `.txt` files.

The tool works without any API key (rules only). To add the AI judge, set `PROVIDER` in step 2 and paste a key when asked. The key stays in this session only."""),
    md("## 1 · Load the tool"),
    code(f"""import base64, io, zipfile, sys, os, subprocess
PKG = "{PKG}"
zipfile.ZipFile(io.BytesIO(base64.b64decode(PKG))).extractall("/content/promo_finder_app" if os.path.isdir("/content") else "promo_finder_app")
APP = "/content/promo_finder_app" if os.path.isdir("/content") else os.path.abspath("promo_finder_app")
subprocess.run([sys.executable, "tests/make_synthetic_show.py"], cwd=APP, check=True, capture_output=True)
print("Tool loaded:", sorted(os.listdir(os.path.join(APP, "promo_finder"))))"""),
    md("## 2 · Settings"),
    code("""USE_DEMO_SHOW = True        # False = upload your own .zip of episode .txt files
STRATEGY = "funnel"         # "funnel" = premise episodes first · "peak" = strongest moments first
PROVIDER = "heuristic"      # "heuristic" (no key) · "gemini" · "openai" (any OpenAI-compatible API) · "anthropic"
MODEL = ""                  # blank = default for the provider, e.g. gemini-3.5-flash-lite
OPENAI_BASE_URL = ""        # only for openai-compatible endpoints other than OpenAI (Groq, OpenRouter, Kuku's own API)"""),
    md("## 3 · Choose the show"),
    code("""INPUT = os.path.join(APP, "tests/synthetic_show/The Waitress Was His Wife")
if not USE_DEMO_SHOW:
    try:
        from google.colab import files
        up = files.upload()               # pick the .zip of screenplays
        INPUT = os.path.abspath(next(iter(up)))
    except ImportError:
        INPUT = input("Path to the show's .zip or folder: ")
print("Input:", INPUT)"""),
    md("## 4 · Find the promos"),
    code("""env = dict(os.environ)
KEYS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
if PROVIDER in KEYS and not env.get(KEYS[PROVIDER]):
    from getpass import getpass
    env[KEYS[PROVIDER]] = getpass(f"{KEYS[PROVIDER]}: ")
if OPENAI_BASE_URL:
    env["OPENAI_BASE_URL"] = OPENAI_BASE_URL
OUT = os.path.join(APP, "out")
cmd = [sys.executable, "-m", "promo_finder", "run", INPUT, "--out", OUT, "--provider", PROVIDER, "--strategy", STRATEGY]
if MODEL:
    cmd += ["--model", MODEL]
r = subprocess.run(cmd, cwd=APP, env=env, capture_output=True, text=True)
print(r.stdout[-3000:], r.stderr[-2000:])"""),
    md("## 5 · The cut sheet\nAccept or reject each promo; **Export my decisions** downloads a CSV that `python -m promo_finder.learn` uses to re-fit the ranking."),
    code("""from IPython.display import HTML, display
display(HTML(open(os.path.join(OUT, "cut_sheet.html")).read()))"""),
    md("## 6 · Checks"),
    code("""r = subprocess.run([sys.executable, "-m", "promo_finder.evaluate", OUT, INPUT], cwd=APP, capture_output=True, text=True)
print(r.stdout[:2500])
if USE_DEMO_SHOW:   # the test show has an answer key written before the tool was run on it
    r = subprocess.run([sys.executable, "tests/score_planted.py", OUT], cwd=APP, capture_output=True, text=True)
    print(r.stdout[-700:])"""),
    md("## 7 · Download all outputs"),
    code("""import shutil
z = shutil.make_archive(os.path.join(APP, "promo_outputs"), "zip", OUT)
try:
    from google.colab import files; files.download(z)
except ImportError:
    print("Saved:", z)"""),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"}, "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}
out = ROOT / "demo" / "Promo_Finder.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(out, round(out.stat().st_size / 1024), "KB")
