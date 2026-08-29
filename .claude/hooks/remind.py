"""
UserPromptSubmit hook: put the rules in front of every reply.

A CLAUDE.md is read once at the start of a session and then competes
with everything else in context. These are the rules that get broken, so
they are re-stated on every single turn, where they cannot be forgotten
between message 5 and message 90.

The text is `reminder` in quiet.config.json. Set it to "" to switch this
off without uninstalling anything.

Fails open on any error -- a hook that breaks your session is worse than
the behaviour it was written to stop.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import silence
except Exception:
    silence = None

DEFAULT = """RULES FOR THIS REPLY. Follow them before anything else.

1. IF SILENCE IS ON, SAY NOTHING. A Stop hook blocks any reply over 12
   words unless a question was asked, and any answer over 60 words.
   Turning it off is the human's action, never yours.

2. LEAD WITH THE ANSWER. No recap, no restating the request, no listing
   what you are about to do, no "why this matters". When corrected, take
   it in one line and carry on. Do not open a reply by naming the rule
   you are following -- that is a header, not an answer.

   STOP TALKING IS NOT STOP WORKING. A question asked mid-task is
   answered in a sentence or two and the work carries on silently. Only
   stop working when you are told to.

3. EVERY NUMBER CARRIES ITS SAMPLE, ITS SOURCE AND ITS STATUS
   (MEASURED / PUBLISHED / FLOOR / CEILING / ASSUMED), beside the number
   and not in a footnote. Name the population.

4. COUNT IT, DON'T QUOTE IT. A figure written in a doc or a note is a
   snapshot. Read anything that moves from source before you use it.

5. DON'T RE-DERIVE WHAT IS SETTLED, and never let "we could not measure
   it" become "the answer is zero" -- write UNRESOLVED."""


def main() -> int:
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    text = DEFAULT
    if silence is not None:
        got = silence.config().get("reminder", None)
        if isinstance(got, str):
            text = got
    if not text.strip():
        return 0
    try:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            }
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
