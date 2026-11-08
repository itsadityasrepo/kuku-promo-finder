"""Parse Kuku-style timestamped screenplays into structured beats.

Format handled (one .txt per episode):
    EPISODE NUMBER: Episode 1
    EPISODE LOGLINE: ...
    CONTINUITY NOTES: ...
    SCENE 01
    Scene heading: INT. CATHEDRAL – DAY
    Scene start: 00:00.00
    Scene end: 02:18.00
    **CAMERA:** / **ACTION:** / **SOUND FX:** / **SPEAKER (Tags):**
    Start: (00:11.30) | End: (00:13.10)
    "Line or description"
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

TS = r"(\d{1,2}):(\d{2})\.(\d{1,2})"
RE_EP = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.I)
RE_LOG = re.compile(r"EPISODE LOGLINE:\s*(.+)")
RE_CONT = re.compile(r"CONTINUITY NOTES:\s*(.+)")
RE_SCENE = re.compile(r"^SCENE\s+(\d+)", re.M)
RE_HEAD = re.compile(r"Scene heading:\s*(.+)")
RE_LABEL = re.compile(r"^\*\*(.+?):\*\*\s*$")
RE_TIME = re.compile(r"Start:\s*\(" + TS + r"\)\s*\|\s*End:\s*\(" + TS + r"\)")

NON_DIALOGUE = {"CAMERA", "ACTION", "SOUND FX", "SFX", "MUSIC", "TEXT", "TITLE", "SUPER", "VO"}


def to_sec(m, h: int) -> float:
    mm, ss, cc = int(m.group(h)), int(m.group(h + 1)), m.group(h + 2)
    return round(mm * 60 + ss + int(cc) / (10 ** len(cc)), 2)


def fmt(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


@dataclass
class Beat:
    id: str
    ep: int
    idx: int
    scene: int
    kind: str            # camera | action | sfx | dialogue | other
    speaker: str         # character name for dialogue, else ""
    tags: str            # emotion/delivery tags e.g. "Outraged, Accusing"
    text: str
    start: float
    end: float
    # filled by features.py
    hook: float = 0.0
    cliff: float = 0.0
    intensity: float = 0.0
    flags: list = field(default_factory=list)

    def as_line(self) -> str:
        who = f"{self.speaker} ({self.tags})" if self.kind == "dialogue" else self.kind.upper()
        return f"[{self.id}] {fmt(self.start)}-{fmt(self.end)} {who}: {self.text}"


@dataclass
class Episode:
    num: int
    logline: str
    continuity: str
    duration: float
    scenes: dict
    beats: list

    def to_dict(self):
        d = asdict(self)
        return d


def _clean_speaker(label: str):
    # "LADY JANE (Confused, Breathless)" / "MATRIARCH (O.S.) (Firm)"
    parens = re.findall(r"\(([^)]*)\)", label)
    name = re.sub(r"\([^)]*\)", "", label).strip()
    tags = [p for p in parens if p.upper() not in {"O.S.", "V.O.", "OFF-SCREEN", "CONT'D", "O.C."}]
    return name, ", ".join(tags)


def parse_text(raw: str, fallback_num: int = 0) -> Episode:
    m = RE_EP.search(raw)
    num = int(m.group(1)) if m else fallback_num
    log = (RE_LOG.search(raw) or [None, ""])[1] if RE_LOG.search(raw) else ""
    cont = RE_CONT.search(raw).group(1).strip() if RE_CONT.search(raw) else ""
    lines = raw.splitlines()
    beats, scenes = [], {}
    scene = 0
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        sm = RE_SCENE.match(ln)
        if sm:
            scene = int(sm.group(1))
            scenes[scene] = {"heading": ""}
            i += 1
            continue
        hm = RE_HEAD.match(ln)
        if hm and scene in scenes:
            scenes[scene]["heading"] = hm.group(1).strip()
        lm = RE_LABEL.match(ln)
        if lm:
            label = lm.group(1).strip()
            # find timestamp line and text (next non-empty lines)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            tm = RE_TIME.search(lines[j]) if j < len(lines) else None
            if not tm:
                i += 1
                continue
            k = j + 1
            text_lines = []
            while k < len(lines) and lines[k].strip() and not RE_LABEL.match(lines[k].strip()) \
                    and not RE_SCENE.match(lines[k].strip()) and not lines[k].startswith("---"):
                text_lines.append(lines[k].strip())
                k += 1
            text = " ".join(text_lines).strip().strip('"').strip("“”")
            upper = label.upper()
            if upper == "CAMERA":
                kind, spk, tags = "camera", "", ""
            elif upper == "ACTION":
                kind, spk, tags = "action", "", ""
            elif upper in {"SOUND FX", "SFX", "MUSIC"}:
                kind, spk, tags = "sfx", "", ""
            elif upper in NON_DIALOGUE:
                kind, spk, tags = "other", "", ""
            else:
                kind = "dialogue"
                spk, tags = _clean_speaker(label)
            idx = len(beats)
            beats.append(Beat(id=f"E{num}-B{idx}", ep=num, idx=idx, scene=scene, kind=kind,
                              speaker=spk, tags=tags, text=text,
                              start=to_sec(tm, 1), end=to_sec(tm, 4)))
            i = k
            continue
        i += 1
    duration = max((b.end for b in beats), default=0.0)
    return Episode(num=num, logline=log.strip(), continuity=cont, duration=duration,
                   scenes=scenes, beats=beats)


def load_show(path: str | Path) -> list[Episode]:
    """Load a folder of .txt screenplays, or a .zip containing them (any nesting)."""
    path = Path(path)
    texts = []
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".txt") and not n.startswith("__MACOSX"):
                    texts.append((n, z.read(n).decode("utf-8", errors="replace")))
    elif path.is_dir():
        for p in sorted(path.rglob("*.txt")):
            texts.append((p.name, p.read_text(encoding="utf-8", errors="replace")))
    else:
        texts.append((path.name, path.read_text(encoding="utf-8", errors="replace")))
    eps = []
    for n, (name, raw) in enumerate(texts, 1):
        fm = re.search(r"episode-(\d+)", name, re.I)
        eps.append(parse_text(raw, fallback_num=int(fm.group(1)) if fm else n))
    eps.sort(key=lambda e: e.num)
    return eps


def validate(eps: list[Episode]) -> dict:
    issues = []
    for e in eps:
        if not e.beats:
            issues.append(f"Ep{e.num}: no beats parsed")
        for b in e.beats:
            if b.end < b.start:
                issues.append(f"{b.id}: end<start")
            if not b.text:
                issues.append(f"{b.id}: empty text")
    return {"episodes": len(eps), "beats": sum(len(e.beats) for e in eps), "issues": issues}
