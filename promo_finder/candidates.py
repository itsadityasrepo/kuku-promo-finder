"""Generate and score promo candidates from scored beats.

Three shapes, all built only from real beat boundaries (never mid-line):
  single      one continuous stretch, 20-60 s
  compressed  2-3 segments from one long arc (60-150 s) squeezed under 60 s, the
              way ReelShort/DramaBox ads jump-cut a scene
  cross_ep    the same, but the arc crosses an episode boundary where the next
              episode "picks up directly" (recap lines are dropped)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .parse import Beat, Episode, fmt

MIN_LEN, MAX_LEN = 20.0, 60.0
SWEET_LO, SWEET_HI = 25.0, 45.0
HOOK_TH, CLIFF_TH = 2.0, 1.8


@dataclass
class Segment:
    ep: int
    beats: list  # list[Beat], content beats only

    @property
    def start(self): return self.beats[0].start

    @property
    def end(self): return self.beats[-1].end

    @property
    def dur(self): return round(self.end - self.start, 2)

    def to_dict(self):
        return {"episode": self.ep, "start": fmt(self.start), "end": fmt(self.end),
                "start_s": self.start, "end_s": self.end,
                "first_beat": self.beats[0].id, "last_beat": self.beats[-1].id}


@dataclass
class Candidate:
    kind: str
    segments: list
    score: float = 0.0
    parts: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    id: str = ""

    @property
    def duration(self): return round(sum(s.dur for s in self.segments), 2)

    @property
    def beats(self): return [b for s in self.segments for b in s.beats]

    @property
    def hook_beat(self): return max([b for b in self.beats if b.start - self.segments[0].start < 3.0] or self.beats[:1],
                                    key=lambda b: b.hook)

    @property
    def cliff_beat(self): return self.segments[-1].beats[-1]

    def coverage(self):
        return {(s.ep, int(t)) for s in self.segments for t in range(int(s.start), int(s.end) + 1)}


def content(beats):
    return [b for b in beats if b.kind != "camera"]


def _score(c: Candidate, names: set[str], title_words: set[str]) -> None:
    bs = c.beats
    first = c.segments[0].start
    hook3 = max((b.hook for b in bs if b.start - first < 3.0), default=0)
    cliff = c.cliff_beat.cliff
    dens = sum(b.intensity for b in bs) / max(len(bs), 1)
    peaks = sum(1 for b in bs if b.intensity >= 2.2)
    d = c.duration
    len_pen = max(0, SWEET_LO - d) + max(0, d - SWEET_HI)
    # dead air: seconds with no dialogue/action inside segments
    talk = sum(min(b.end, s.end) - max(b.start, s.start) for s in c.segments for b in s.beats if b.kind in ("dialogue", "action"))
    dead = max(0.0, 1 - talk / max(d, 1))
    heard = {n for b in bs if b.kind == "dialogue" for n in names if n in b.text}
    debt = max(0, len(heard) - 3)
    seg_pen = 0.5 * (len(c.segments) - 1)
    # soft tail: if the cut lands after a gentle/soft beat, the viewer feels resolution
    score = 1.0 * hook3 + 1.2 * cliff + 0.8 * dens + 0.15 * min(peaks, 8) - 0.03 * len_pen - 1.0 * dead \
        - 0.15 * debt - seg_pen
    text = " ".join(b.text for b in bs).lower()
    title_hit = sorted(w for w in title_words if w in text)
    flags = sorted({f for b in bs for f in b.flags})
    if c.parts.get("relaxed") if c.parts else False:
        score -= 1.0
    c.score = round(score, 3)
    c.flags = flags
    c.parts = {**(c.parts or {}), "hook3": round(hook3, 2), "cliff": round(cliff, 2), "density": round(dens, 2), "peaks": peaks,
               "len_pen": round(len_pen, 1), "dead_air": round(dead, 2), "names_heard": sorted(heard),
               "segments": len(c.segments), "title_words": title_hit}


def _singles(cb: list[Beat], ep: int, relax: float = 0.0):
    out = []
    starts = [i for i, b in enumerate(cb) if b.hook >= HOOK_TH - relax]
    ends = [j for j, b in enumerate(cb) if b.cliff >= CLIFF_TH - relax]
    for i in starts:
        for j in ends:
            if j <= i:
                continue
            d = cb[j].end - cb[i].start
            if d < MIN_LEN:
                continue
            if d > MAX_LEN:
                break
            out.append(Candidate("single", [Segment(ep, cb[i:j + 1])]))
    return out


def _grow(cb, i, lo, hi, forward=True):
    """Take beats from index i forward (or backward) until length >= lo, never past hi."""
    if forward:
        j = i
        while j + 1 < len(cb) and cb[j + 1].end - cb[i].start <= hi and cb[j + 1].ep == cb[i].ep:
            j += 1
            if cb[j].end - cb[i].start >= lo and cb[j].cliff >= CLIFF_TH:
                break
        return i, j
    j = i
    while j - 1 >= 0 and cb[i].end - cb[j - 1].start <= hi and cb[j - 1].ep == cb[i].ep:
        j -= 1
        if cb[i].end - cb[j].start >= lo and cb[j].hook >= 1.0:
            break
    # don't start a segment on a dangling reply
    while j < i and cb[j].hook < 0.5:
        j += 1
    return j, i


def _compressed(cb: list[Beat], kind: str):
    out = []
    starts = [i for i, b in enumerate(cb) if b.hook >= HOOK_TH + 0.5]
    ends = [j for j, b in enumerate(cb) if b.cliff >= CLIFF_TH + 0.5]
    for i in starts:
        for j in ends:
            span = cb[j].end - cb[i].start
            if span <= MAX_LEN or span > 150:
                continue
            a0, a1 = _grow(cb, i, 6, 18, True)
            c0, c1 = _grow(cb, j, 8, 22, False)
            if c0 <= a1 + 1:
                continue
            segs = [(a0, a1)]
            budget = MAX_LEN - 2 - (cb[a1].end - cb[a0].start) - (cb[c1].end - cb[c0].start)
            # middle: hottest contiguous run that fits the budget
            best, bscore = None, 0
            for m0 in range(a1 + 1, c0):
                if cb[m0].hook < 0.8:
                    continue
                tot = 0
                for m1 in range(m0, c0):
                    if cb[m1].end - cb[m0].start > budget or cb[m1].ep != cb[m0].ep:
                        break
                    tot += cb[m1].intensity
                    if cb[m1].end - cb[m0].start >= 5 and tot > bscore:
                        best, bscore = (m0, m1), tot
            if best and budget >= 6:
                segs.append(best)
            segs.append((c0, c1))
            # never end an inner segment inside a sentence the script split across two beats
            fixed = []
            for k, (s0, s1) in enumerate(segs):
                while cb[s1].cliff <= -2 and s1 + 1 < len(cb) and cb[s1 + 1].ep == cb[s1].ep:
                    s1 += 1
                if fixed and s0 <= fixed[-1][1]:
                    s0 = fixed[-1][1] + 1
                if s0 <= s1:
                    fixed.append((s0, s1))
            segs = fixed
            # split any segment that crosses an episode boundary
            final = []
            for s0, s1 in segs:
                run = [cb[s0]]
                for b in cb[s0 + 1:s1 + 1]:
                    if b.ep != run[-1].ep:
                        final.append(Segment(run[0].ep, run))
                        run = [b]
                    else:
                        run.append(b)
                final.append(Segment(run[0].ep, run))
            c = Candidate(kind, final)
            if MIN_LEN <= c.duration <= MAX_LEN:
                out.append(c)
    return out


def _cross_track(prev: Episode, nxt: Episode):
    """Final scene of prev + first scene of nxt, with nxt's recap lines removed."""
    note = (nxt.continuity + " " + nxt.scenes.get(1, {}).get("heading", "")).lower()
    if not any(k in note for k in ("picks up directly", "continuous", "immediately after", "moments later")):
        return None
    tail = content([b for b in prev.beats if b.scene == max(prev.scenes or {0: 0})])
    head = content([b for b in nxt.beats if b.scene == min(nxt.scenes or {1: 0})])
    recent = [b.text.lower() for b in tail[-15:]]
    head = [b for b in head if not any(difflib.SequenceMatcher(None, b.text.lower(), r).ratio() > 0.6 for r in recent)]
    if len(tail) < 3 or len(head) < 3:
        return None
    return tail + head


def generate(eps: list[Episode], names: set[str], title_words: set[str]):
    cands = []
    for e in eps:
        cb = content(e.beats)
        singles = _singles(cb, e.num)
        if not singles:  # quiet episode: relax thresholds so every episode is still judged
            singles = [c for c in _singles(cb, e.num, relax=1.0)]
            for c in singles:
                c.parts["relaxed"] = True
        cands += singles
        cands += _compressed(cb, "compressed")
    for a, b in zip(eps, eps[1:]):
        if b.num != a.num + 1:
            continue
        track = _cross_track(a, b)
        if track:
            cands += [c for c in _compressed(track, "cross_ep") if len({s.ep for s in c.segments}) > 1]
    for c in cands:
        _score(c, names, title_words)
    return cands


def dedupe(cands, iou=0.5):
    kept = []
    for c in sorted(cands, key=lambda x: -x.score):
        cov = c.coverage()
        if all(len(cov & k.coverage()) / len(cov | k.coverage()) < iou for k in kept):
            kept.append(c)
    return kept


def shortlist(cands, extra=10, per_ep=2, premise_eps=5, premise_cap=3):
    """Best candidate from EVERY episode (so no episode is skipped by the rules' blind spots),
    plus the next `extra` best overall (max `per_ep` per episode). Sent to the model judge."""
    out, per = [], {}
    for c in cands:  # cands sorted by score desc
        key = c.segments[0].ep
        if key not in per:
            per[key] = 1
            out.append(c)
    # premise episodes get up to `premise_cap` candidates: they are the cheapest promos for a new viewer
    for c in cands:
        key = c.segments[0].ep
        if key <= premise_eps and c not in out and per.get(key, 0) < premise_cap:
            per[key] = per.get(key, 0) + 1
            out.append(c)
    for c in cands:
        if extra <= 0:
            break
        key = c.segments[0].ep
        if c in out or per.get(key, 0) >= per_ep:
            continue
        per[key] += 1
        out.append(c)
        extra -= 1
    out.sort(key=lambda x: -x.score)
    for n, c in enumerate(out, 1):
        c.id = f"P{n:02d}"
    return out
