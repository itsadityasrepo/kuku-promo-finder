#!/usr/bin/env bash
# One command for the real-model run, its checks, and a comparison with the earlier judged run.
# Usage:  export GEMINI_API_KEY=...   (free key: https://aistudio.google.com/apikey)
#         bash run_gemini.sh path/to/input_pack.zip [model]
set -euo pipefail
ZIP="${1:?give the path to the input pack zip}"; MODEL="${2:-gemini-3.5-flash-lite}"
: "${GEMINI_API_KEY:?export GEMINI_API_KEY first}"
pip install -q requests
OUT=outputs/kuku_show/judged_gemini
python -m promo_finder run "$ZIP" --provider gemini --model "$MODEL" --out "$OUT"
python -m promo_finder.evaluate "$OUT" "$ZIP" --compare outputs/kuku_show/judged
python -m promo_finder.sensitivity "$OUT"
python -m promo_finder run "tests/synthetic_show/The Waitress Was His Wife" --provider gemini --model "$MODEL" --out outputs/test_show/judged_gemini
python tests/score_planted.py outputs/test_show/judged_gemini | tail -3
python review/build_blind_review.py outputs/kuku_show/rules_only outputs/kuku_show/judged "$OUT" --input "$ZIP"
echo "Done. Now open review/blind_review.html and grade the clips (about 20 minutes)."
