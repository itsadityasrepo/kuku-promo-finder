# Design notes

The decisions behind the tool, and what I considered instead.

**Problem 1, framed around the promo editor.** It's the only problem with real data and an output that can be checked line by line. The tool doesn't pick the final promo. It turns "watch every episode" into "review a ranked post list" and points to what needs a second look.

**The AI picks line IDs, code produces timestamps.** If you ask a model for timestamps, it makes them up. Here the judge can only choose from the IDs of lines it was shown. Code converts IDs to times and checks the result. Across every judge answer collected, none used an ID that wasn't in its prompt.

**Rules first, AI second.** Rules are free, fast and repeatable, and they run with no key (the interview laptop may not have one). But they miss quiet lines that land hard without any shock word, such as a calm reveal. So the rules only shortlist, and the judge sees the best candidate from **every** episode, not just the rules' top 20.

**The judge gets no story summary.** An earlier version gave it each episode's logline, so its "makes sense to a stranger" score was meaningless. It still sees the show title and the 30 s before the clip, so that score is optimistic. The blind review is the real check on it.

**Hard checks in code.** Every clip is 20–60 s. No cut lands inside a sentence the script splits across two lines; an early version cut 6 of 60 clips mid-sentence, and the fix came from reading the line after every cut. The hook must start within 3 s, or the start moves to it. A clip that fails these checks can't enter the post list.

**Posting order is a hypothesis, so the tool offers two.** Public data on DramaBox's US ads shows one creative taking ~75% of the top-10 impressions. Spend piles onto whichever clip wins. So the first wave should be several *different* moments (one per story moment), and the order is something to test, not something to argue about. `funnel` puts clips from the first 5 episodes first, because a new viewer reaches that payoff fastest. `peak` puts the strongest moments first. I couldn't find public data on where the ad tap lands, so this needs an A/B test.

**Hand-set weights, with a way to replace them.** The scoring weights are my guesses. `sensitivity.py` shows how much the ranking depends on them. `learn.py` re-fits them from the editor's Accept/Reject decisions, which is how the tool improves across shows.

**A smoke test on something I didn't tune on.** All my tuning happened on the Kuku show, so its results flatter the tool. I had Claude write a small 4-episode show in a different genre, with 3 planted promos and 4 traps. The answers were recorded before the tool ran on it. It's weak evidence: the same AI wrote the show, the answer key and the word lists, and only 8 candidates compete. It shows the tool doesn't break on a new genre, nothing more.

**Things I chose not to build:** music, captions, editing, a chat interface, a video model. The brief asks for moments and cut points. A vision pass on the first 3 s is the first thing I'd add.
