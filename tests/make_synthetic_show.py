"""Writes the synthetic held-out test show (modern CEO revenge, 4 episodes) in Kuku's screenplay format.
The answer key is tests/ground_truth.json, written before this show was ever run through the tool."""
from pathlib import Path

SHOW = "The Waitress Was His Wife"
C, A, S = "CAMERA", "ACTION", "SOUND FX"

EPISODES = [
 (1, "At a charity gala, waitress Mia is humiliated by her former sister-in-law until a CEO claims her as his wife.",
  "First episode. Establishes Mia's humiliation and the secret marriage.",
  [("INT. HOTEL BALLROOM – NIGHT", [
   (C, 0, 4, "Wide shot of a glittering charity gala, chandeliers and champagne towers."),
   (A, 1, 4, "Mia, in a cheap waitress uniform, carries a tray of glasses through the rich guests."),
   ("VANESSA (Mocking, Cruel)", 5, 8, "Look who's serving drinks. My ex-sister-in-law."),
   ("MIA (Quiet)", 8, 11, "Please, Vanessa. I just need this job."),
   ("VANESSA (Gloating)", 11, 14, "Then do it properly."),
   (A, 14, 16, "Vanessa tips her champagne slowly down the front of Mia's uniform."),
   (S, 16, 18, "Guests gasp and giggle."),
   ("MIA (Hurt, Shaking)", 18, 22, "Why do you hate me this much?"),
   ("VANESSA (Venomous)", 22, 26, "Because you still wear his ring."),
   (C, 26, 30, "Slow push in on Mia's trembling hand and the plain silver ring."),
   (A, 31, 32.5, "Vanessa slaps Mia hard across the face; the tray crashes to the floor."),
   (S, 31.2, 32.8, "A sharp slap, then glass shattering."),
   ("MIA (Stunned, Whispering)", 33, 36, "You hit me."),
   ("VANESSA (Triumphant, Cruel)", 36, 41, "Security! Throw this thief out before she steals the silverware!"),
   (A, 41, 44, "Two guards grab Mia by the arms and drag her toward the exit."),
   ("MIA (Desperate)", 44, 47, "Let go of me! I didn't steal anything!"),
   (A, 47, 51, "The ballroom doors swing open; a tall man in a black suit walks in and the room falls silent."),
   (S, 51, 54, "Footsteps echo across the marble floor."),
   ("VANESSA (Shocked)", 54, 57, "Mr. Blackwood? The CEO is here?"),
   ("BLACKWOOD (Cold, Commanding)", 57, 61, "Take your hands off my wife."),
   (S, 61, 63, "The whole crowd gasps."),
   ("VANESSA (Horrified)", 63, 66, "Your... wife?"),
   (C, 66, 70, "Close-up on Mia, frozen, cheek still red."),
   ("MIA (Confused, Breathless)", 70, 74, "I have never seen this man in my life."),
   ("BLACKWOOD (Calm, Certain)", 74, 80, "You signed the papers three years ago. You just never read them."),
   (A, 80, 84, "He takes off his coat and places it gently over Mia's soaked shoulders."),
   ("BLACKWOOD (Soft, Warm)", 84, 90, "Come. We are going home."),
   (C, 90, 95, "They walk out together into the night as the image gently fades."),
  ])]),
 (2, "Daniel explains the secret marriage, until Vanessa arrives claiming to carry his child.",
  "Picks up directly from Episode 1.",
  [("INT. BLACKWOOD PENTHOUSE – NIGHT", [
   (C, 0, 4, "Wide shot of a vast, minimalist penthouse."),
   (A, 0.5, 4, "Mia stands in the middle of the room, still in her soaked uniform."),
   ("MIA (Angry)", 4, 8, "Explain. Now. Who are you really?"),
   ("BLACKWOOD (Calm)", 8, 13, "Daniel Blackwood. Your grandfather saved my father's company..."),
   ("BLACKWOOD (Calm)", 13, 17, "...and the price was that I would protect you, by marriage."),
   ("MIA (Disbelieving)", 17, 21, "So I'm a debt you paid off?"),
   ("BLACKWOOD (Gentle)", 21, 25, "You're the only person I was ever told to keep safe."),
   (A, 25, 30, "Mia's phone buzzes; she reads the screen and goes pale."),
   ("MIA (Frightened)", 30, 34, "It's my sister. She says Vanessa knows where I am."),
   ("BLACKWOOD (Reassuring)", 34, 40, "No one gets past this door."),
   (S, 40, 44, "Three hard knocks on the front door."),
  ]), ("INT. PENTHOUSE HALLWAY – CONTINUOUS", [
   (C, 44, 48, "The front door swings open."),
   (A, 45, 48, "Vanessa stands in the doorway holding a folder, smiling."),
   ("VANESSA (Smug, Venomous)", 48, 52, "I'm pregnant, Daniel. And the baby is yours."),
   (S, 52, 54, "Mia's glass slips from her hand and shatters."),
   ("MIA (Devastated)", 54, 57, "Is that true?"),
   ("VANESSA (Gloating)", 57, 62, "Ask him where he was the night of the merger party."),
   (A, 62, 66, "Vanessa slaps the folder against Daniel's chest."),
   ("VANESSA (Threatening)", 66, 72, "Here's the DNA test. Sign the divorce papers, or I take this to every newspaper in the city."),
   (C, 72, 74, "Close on Daniel, jaw tight."),
   ("MIA (Pleading, Breaking)", 74, 78, "Daniel. Tell me she's lying."),
   (S, 78, 80, "Silence. A clock ticking."),
   ("BLACKWOOD (Cold)", 80, 83, "Open the folder."),
   (A, 83, 90, "Mia opens the folder with trembling hands; her face drains of colour."),
   ("MIA (Shocked, Whispering)", 90, 95, "This isn't his name on the test."),
   (C, 95, 100, "Smash cut to black."),
  ])]),
 (3, "The DNA test exposes Vanessa; she is arrested, and Mia and Daniel share a quiet night.",
  "Picks up directly from Episode 2.",
  [("INT. PENTHOUSE HALLWAY – CONTINUOUS", [
   (C, 0, 4, "Close on the DNA report in Mia's hands."),
   ("MIA (Steady)", 1, 5, "The father on this test is Richard Hale. Your own boss."),
   ("VANESSA (Panicked)", 5, 9, "That's a mistake. That's a mistake!"),
   ("BLACKWOOD (Cold)", 9, 14, "Security already has the footage from the merger party. You were never in my suite."),
   (A, 14, 18, "Two security guards step in and take Vanessa by the arms."),
   ("VANESSA (Defeated, Sobbing)", 18, 22, "Please. I had no choice. He made me do it."),
   ("BLACKWOOD (Firm)", 22, 27, "Then you can tell that to the police."),
   (A, 27, 31, "The guards lead Vanessa away down the hallway."),
   ("MIA (Relieved, Tearful)", 31, 36, "It's over. It's really over."),
   ("BLACKWOOD (Gentle)", 36, 41, "It is. Nobody will hurt you again."),
  ]), ("EXT. PENTHOUSE BALCONY – NIGHT", [
   (C, 41, 45, "Wide shot of the city lights."),
   (A, 42, 47, "Mia and Daniel stand side by side at the railing, the city glittering below."),
   ("MIA (Soft, Warm)", 47, 52, "Thank you for believing me."),
   ("BLACKWOOD (Tender)", 52, 57, "I always will."),
   (A, 57, 62, "Mia rests her head on his shoulder and smiles."),
   ("MIA (Playful)", 62, 68, "So. Do I have to call you Mr. Blackwood at home?"),
   ("BLACKWOOD (Amused, Warm)", 68, 73, "Only when you're angry with me."),
   (A, 73, 80, "They both laugh softly as the night breeze moves her hair."),
   (C, 80, 88, "Slow pull back from the balcony, the couple small against the skyline, fading to black."),
  ])]),
 (4, "Two weeks later, Mia takes over Hale's company, and Hale plants a doubt about her grandfather's death.",
  "Two weeks after Episode 3.",
  [("INT. HALE TOWER BOARDROOM – DAY", [
   (C, 0, 4, "Glass boardroom, twelve executives around a long table."),
   (A, 1, 5, "Mia walks into the boardroom; every head turns."),
   ("RICHARD HALE (Mocking, Smug)", 5, 9, "The waitress? Who let the help into my board meeting?"),
   ("MIA (Calm, Cold)", 9, 13, "Your new majority shareholder did."),
   (S, 13, 15, "Murmurs ripple around the table."),
   ("RICHARD HALE (Incredulous)", 15, 19, "You? You own nothing."),
   ("MIA (Steely)", 19, 24, "My grandfather left me thirty-one percent of this company. Daniel just bought me the rest."),
   (A, 24, 28, "Mia drops a signed contract onto the table in front of Hale."),
   ("RICHARD HALE (Enraged, Shouting)", 28, 32, "Get out of my building!"),
   ("MIA (Cold)", 32, 36, "It's my building now. And you're fired."),
   (S, 36, 38, "A pen clatters onto the glass table."),
   (A, 38, 42, "Hale leans in close, his voice dropping to a whisper."),
   ("RICHARD HALE (Menacing, Whispering)", 42, 47, "Your grandfather didn't die of a heart attack, Mia."),
   (S, 47, 49, "A low, ominous drone."),
   ("MIA (Shaken)", 49, 53, "What did you just say?"),
   ("RICHARD HALE (Sinister)", 53, 58, "Ask your husband what he really paid for that company."),
   (C, 58, 62, "Close on Mia, frozen."),
   (A, 62, 66, "Daniel enters the boardroom behind her."),
   ("BLACKWOOD (Concerned)", 66, 70, "Mia? What did he say to you?"),
   ("MIA (Cold, Suspicious)", 70, 75, "Nothing. Let's go."),
   (C, 75, 82, "She walks past him without looking back. Cut to black."),
  ])]),
]


def ts(x):
    m, s = divmod(x, 60)
    return f"{int(m):02d}:{s:05.2f}"


def write(out: Path):
    d = out / SHOW
    d.mkdir(parents=True, exist_ok=True)
    for num, log, cont, scenes in EPISODES:
        lines = [f"EPISODE NUMBER: Episode {num}", f"EPISODE LOGLINE: {log}", f"CONTINUITY NOTES: {cont}", "",
                 "--- SCRIPT START ---", ""]
        for k, (head, beats) in enumerate(scenes, 1):
            lines += [f"SCENE {k:02d}", f"Scene heading: {head}", f"Scene start: {ts(beats[0][1])}",
                      f"Scene end: {ts(max(b[2] for b in beats))}", "", "Actions and dialogue:", ""]
            for label, a, b, text in beats:
                lines += [f"**{label}:**", f"Start: ({ts(a)}) | End: ({ts(b)})",
                          f'"{text}"' if label not in (C, A, S) else text, ""]
        (d / f"episode-{num:03d}.txt").write_text("\n".join(lines))
    return d


if __name__ == "__main__":
    print(write(Path(__file__).parent / "synthetic_show"))
