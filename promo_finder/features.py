"""Rule-based beat scoring. Cheap, deterministic, explainable.

Each beat gets:
  hook      - how likely this beat stops a scroll if it plays in the first 3 s
  cliff     - how unresolved/tense the moment is if the clip cuts right after it
  intensity - general dramatic heat (used for density + compression)
  flags     - ad-policy flags for the editor
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .parse import Beat, Episode

_HERE = Path(__file__).parent
LEX = json.loads((_HERE / "lexicons.json").read_text())
_CORE = json.loads(json.dumps(LEX))
PACK_KEYS = ("physical_shock", "reveal_words", "threat_words")


def available_packs():
    return sorted(p.stem for p in (_HERE / "lexicon_packs").glob("*.json"))


def configure_lexicon(eps, packs=None, min_hits_per_episode=1.0):
    """Reset to the genre-neutral core, then add genre packs: the ones named in `packs`, or (if None)
    every pack whose words appear at least `min_hits_per_episode` times per episode in the scripts."""
    for k in list(LEX):
        LEX[k] = json.loads(json.dumps(_CORE[k]))
    _PAT.clear()
    text = " ".join(b.text.lower() for e in eps for b in e.beats)
    chosen, hits = [], {}
    for name in available_packs():
        pack = json.loads((_HERE / "lexicon_packs" / f"{name}.json").read_text())
        n = sum(len(_pat(w).findall(text)) for k in PACK_KEYS for w in pack.get(k, []))
        hits[name] = round(n / max(len(eps), 1), 2)
        if (packs is None and hits[name] >= min_hits_per_episode) or (packs and name in packs):
            chosen.append(name)
            for k in PACK_KEYS:
                LEX[k] = LEX[k] + pack.get(k, [])
    return chosen, hits


_PAT = {}


def _pat(w: str):
    if w not in _PAT:
        if w.endswith("$"):
            _PAT[w] = re.compile(r"(?<![a-z])" + re.escape(w[:-1]) + r"(?![a-z])")
        else:
            _PAT[w] = re.compile(r"(?<![a-z])" + re.escape(w))
    return _PAT[w]


def _has(text: str, words) -> int:
    t = text.lower()
    return sum(1 for w in words if _pat(w).search(t))


def _tag_arousal(tags: str) -> float:
    t = tags.lower()
    hi = _has(t, LEX["high_arousal_tags"])
    lo = _has(t, LEX["low_arousal_tags"])
    return max(-1.0, min(2.0, hi * 0.8 - lo * 0.6))


def score_beat(b: Beat, next_b: Beat | None, is_last_in_scene: bool, is_last_in_ep: bool) -> None:
    text = b.text
    tl = text.lower()
    phys = _has(tl, LEX["physical_shock"])
    reveal = _has(tl, LEX["reveal_words"])
    threat = _has(tl, LEX["threat_words"])
    cm = _has(tl, LEX["cliff_markers"])
    soft = _has(tl, LEX["soft_end_markers"])

    hook = cliff = inten = 0.0
    if b.kind == "dialogue":
        ar = _tag_arousal(b.tags)
        words = len(text.split())
        excl = text.count("!")
        q = text.rstrip().endswith("?")
        hook = 1.0 + ar + 0.6 * min(excl, 2) + 0.8 * reveal + 0.6 * threat
        if words <= 8:
            hook += 0.5          # short punchy lines land in 3 s
        if words > 22:
            hook -= 0.8          # speeches don't hook
        if any(tl.startswith(d) for d in LEX["dangling_start"]):
            hook -= 1.5          # starts mid-thought: a cold viewer is lost
        cliff = 0.6 + 0.7 * q + 0.9 * threat + 0.8 * reveal + 0.4 * excl + 0.5 * max(ar, 0)
        if text.rstrip().endswith("...") and not text.lstrip().startswith("..."):
            cliff += 0.8         # interrupted / trailing line
        inten = 1.0 + ar + 0.5 * excl + 0.5 * reveal + 0.5 * threat
    elif b.kind == "action":
        hook = 0.6 + 1.3 * phys + 0.4 * reveal
        cliff = 0.3 + 0.6 * phys + 0.8 * cm - 0.8 * soft
        inten = 0.6 + 1.0 * phys
    elif b.kind == "sfx":
        hook = 0.4 + 1.0 * phys + 0.5 * _has(tl, ["gasp", "crash", "scream", "explos", "slap", "punch"])
        cliff = 0.3 + 1.2 * cm + 0.5 * phys - 0.8 * soft
        inten = 0.5 + 0.8 * phys + 0.5 * cm
    else:  # camera: only carries descriptive signal
        hook = 0.2 + 0.6 * phys
        cliff = 0.1 + 0.8 * cm - 0.6 * soft
        inten = 0.3 + 0.4 * phys

    # Cliff is only real if the next beat doesn't immediately answer it inside the same moment
    if next_b is not None and next_b.kind == "dialogue" and next_b.start - b.end < 0.4 and b.kind == "dialogue" \
            and next_b.speaker != b.speaker:
        cliff -= 0.3
    # Split sentence: "...your grandfather saved my father's company..." / "...and the price was..."
    # The script breaks one sentence across two beats; cutting between them is a mid-line cut.
    if b.kind == "dialogue" and text.rstrip().endswith(("...", "…")) and next_b is not None \
            and next_b.kind == "dialogue" and (next_b.speaker == b.speaker or next_b.text.lstrip().startswith(("...", "…"))):
        cliff = -2.0
        flags_split = True
    else:
        flags_split = False
    if is_last_in_scene:
        cliff += 0.4
    if is_last_in_ep:
        cliff += 0.6 if soft == 0 else -0.4

    flags = []
    for k, words in LEX["safety"].items():
        if _has(tl, words):
            flags.append(k)
    b.hook, b.cliff, b.intensity, b.flags = round(hook, 2), round(cliff, 2), round(max(inten, 0), 2), flags


def score_episode(ep: Episode) -> None:
    beats = ep.beats
    last_idx_by_scene = {}
    for b in beats:
        last_idx_by_scene[b.scene] = b.idx
    # "last" = last non-camera beat, since camera beats are just framing
    content = [b for b in beats if b.kind != "camera"]
    last_content = content[-1].idx if content else -1
    for i, b in enumerate(beats):
        nxt = next((x for x in beats[i + 1:] if x.kind != "camera"), None)
        score_beat(b, nxt, b.idx == last_idx_by_scene.get(b.scene), b.idx == last_content)


def show_names(eps: list[Episode]) -> set[str]:
    """Proper names a viewer would *hear*: capitalised words mid-sentence in dialogue, seen 3+ times."""
    c = Counter()
    for e in eps:
        for b in e.beats:
            if b.kind != "dialogue":
                continue
            for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,})\b", b.text):
                c[m.group(1)] += 1
    common = {"The", "This", "That", "You", "Your", "What", "And", "But", "Lady", "Lord", "Sir", "Mother",
              "Father", "God", "Please", "Enough", "Now", "Then", "She", "His", "Her", "They", "Who", "Why",
              "How", "When", "Where", "Not", "Yes", "Guards", "Crown", "Duke", "Duchess", "Majesty", "Grace",
              "High", "Royal", "Council", "Manor", "Dowager", "Priest", "Constable", "Church", "Heaven", "Lordship", "Ladyship"}
    return {w for w, n in c.items() if n >= 3 and w not in common}
