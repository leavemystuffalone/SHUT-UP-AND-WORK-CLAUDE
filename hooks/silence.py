"""
Shared state and config for the silence switch.

Set by `quiet.py`, read by the two hooks. Nothing here talks to Claude;
it only answers "is silence on" and "what are the limits".

WHY THIS EXISTS. A word ceiling catches VERBOSITY. It does not catch the
thing that actually goes wrong: you say "stop explaining", and every
reply afterwards is a two-hundred-word summary that sits comfortably
under the ceiling and sails through. The rule being broken is not "too
long" -- it is SPEAKING AT ALL when told not to, and asking the model to
remember is the approach that already failed.

So this is a switch YOU set, enforced mechanically.

    python quiet.py on      silence
    python quiet.py off
    python quiet.py         what it is set to now
    python quiet.py --test  drive the real hook and prove it blocks

WHAT SILENCE ALLOWS, deliberately narrow:

  - nothing at all. Ending a turn with no text is always allowed and is
    the expected case while work is happening.
  - anything under FREE_WORDS. "Done." is not the failure being stopped.
  - up to ANSWER_WORDS, and only when your last message actually asked
    something -- it has a question mark, or opens with an interrogative.

Everything else is blocked and the reason is handed back to the model,
so the turn ends with no text instead of being sent.

FAIL OPEN, ALWAYS. Unreadable file, missing key, bad JSON -- every one
answers "not silenced". A hook that breaks your session is worse than
the talking it was written to stop.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "silence.json")
CONFIG = os.path.join(HERE, "quiet.config.json")

# --- defaults. Override any of them in quiet.config.json --------------

# A short answer to a direct question still gets through while silenced.
ANSWER_WORDS = 60

# Below this, nothing is blocked at all. "Done." / "Yes, 33." / "Running."
FREE_WORDS = 12

# Hard ceiling on any reply, silence or not. Most padding lives here.
TOO_LONG = 450

# Above this, a reply that repeats one of your settled points is a
# lecture rather than a clause. Below it, one mention is allowed and is
# what you want -- the paragraph is the failure, not the mention.
SHORT_ENOUGH = 120

# Phrases you have already accepted and do not want re-argued. Empty by
# default: this is the one setting that is genuinely per-project.
SETTLED = []


def config() -> dict:
    try:
        with open(CONFIG, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}


def limit(name: str, fallback):
    """A configured limit, or the module default. Never raises."""
    got = config().get(name, None)
    if isinstance(fallback, list):
        return [str(x).lower() for x in got] if isinstance(got, list) \
            else fallback
    try:
        return int(got)
    except Exception:
        return fallback


def state() -> dict:
    try:
        with open(STATE, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}


def is_on() -> bool:
    return bool(state().get("on"))


def set_on(on: bool, note: str = "") -> dict:
    import datetime
    row = {"on": bool(on),
           "at": datetime.datetime.now().isoformat(timespec="seconds"),
           "note": note}
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(row, fh, indent=2)
    os.replace(tmp, STATE)
    return row


# --- was the last message actually asking something? ------------------

_INTERROGATIVE = ("what", "why", "how", "when", "where", "which", "who",
                  "is ", "are ", "do ", "does ", "did ", "can ", "could ",
                  "should ", "would ", "will ", "was ", "were ", "have ",
                  "has ", "tell me", "explain", "show me", "give me",
                  "list ", "?")


def asked_something(user_text: str) -> bool:
    """
    Did the last human message ask for an answer?

    Deliberately generous. A false YES costs at most ANSWER_WORDS; a
    false NO would swallow an answer you are waiting for. This switch
    exists for the case where you said stop and nothing stopped -- not
    to refuse to answer you.
    """
    t = (user_text or "").strip().lower()
    if not t:
        return False
    if "?" in t:
        return True
    return any(t.startswith(w) or ("\n" + w) in t for w in _INTERROGATIVE)
