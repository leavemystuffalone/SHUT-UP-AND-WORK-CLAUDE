"""
Stop hook: refuse a reply that talks when it was told not to, that pads,
or that re-argues something already settled.

WHAT IT DOES. Reads the last assistant message out of the session
transcript and blocks it if:

    silence is ON and the reply is over FREE_WORDS
      and you did not ask a question                  -> blocked
    silence is ON, you asked, and it is over
      ANSWER_WORDS                                    -> blocked
    it is over SHORT_ENOUGH and repeats a phrase you
      listed as settled                               -> blocked
    it is over TOO_LONG, whatever it says             -> blocked

A blocked reply is never sent. The reason goes back to the model and the
answer is rewritten first.

WHAT IT DELIBERATELY DOES NOT DO. It does not block short messages, and
it does not block one clause naming a settled point -- that is what you
want. The paragraph is the failure, not the mention.

FAIL OPEN, ALWAYS. Unreadable transcript, unknown payload shape, missing
field, bad stdin -- every one exits 0 and allows the message. A hook that
breaks your session is worse than the padding it exists to stop.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import silence
except Exception:                    # fail open -- see the module note
    silence = None


def last_text(path: str, role: str) -> str:
    """
    The most recent message of one role in a JSONL transcript.

    Tool results arrive as user-role rows too, so anything whose content
    is not plain text is skipped -- a tool result is not somebody asking.
    """
    text = ""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("type") != role:
                continue
            parts = (row.get("message") or {}).get("content")
            if isinstance(parts, str):
                if parts.strip():
                    text = parts
            elif isinstance(parts, list):
                got = [p.get("text", "") for p in parts
                       if isinstance(p, dict) and p.get("type") == "text"]
                if any(g.strip() for g in got):
                    text = "\n".join(got)
    return text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # Never fight a block that is already in progress.
    if payload.get("stop_hook_active"):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.exists(path):
        return 0

    try:
        text = last_text(path, "assistant")
    except Exception:
        return 0
    if not text.strip():
        return 0

    # A TABLE IS NOT NARRATION, AND A WORD COUNT CANNOT TELL THEM APART.
    #
    # You ask for a chart and then watch it refused for length. The rows
    # ARE the answer, and there is no shorter way to say twenty numbers.
    # Same for a fenced block: it is a command to run or a file to read,
    # not talking. Both are removed before counting, so what is measured
    # is the prose around them -- which is the thing the limits exist
    # for. A reply that is ALL table counts as nearly nothing, which is
    # correct.
    body = re.sub(r"```.*?```", " ", text, flags=re.S)
    body = " ".join(ln for ln in body.splitlines()
                    if not ln.lstrip().startswith("|"))

    words = len(body.split())
    low = text.lower()
    reason = ""
    silence_rule = False

    if silence is not None:
        free = silence.limit("free_words", silence.FREE_WORDS)
        answer = silence.limit("answer_words", silence.ANSWER_WORDS)
        too_long = silence.limit("too_long", silence.TOO_LONG)
        short_enough = silence.limit("short_enough", silence.SHORT_ENOUGH)
        settled = silence.limit("settled", silence.SETTLED)
    else:
        free, answer, too_long, short_enough, settled = 12, 60, 450, 120, []

    # THE SWITCH, CHECKED FIRST AND ON ITS OWN TERMS. Everything below
    # measures how LONG a reply is, which is not the same question.
    if silence is not None and words > free:
        try:
            on = silence.is_on()
        except Exception:
            on = False
        if on:
            try:
                asked = silence.asked_something(last_text(path, "user"))
            except Exception:
                asked = True         # fail open: never swallow an answer
            if not asked:
                reason = (
                    f"BLOCKED -- SILENCE IS ON and this reply is {words} "
                    "words. No question was asked. End the turn with no "
                    "text at all and keep working; if the work is "
                    "finished, say nothing. Turning silence off is the "
                    "human's action (`python quiet.py off`), never yours.")
                silence_rule = True
            elif words > answer:
                reason = (
                    "BLOCKED -- SILENCE IS ON. A question was asked, so an "
                    f"answer is allowed, but this is {words} words against "
                    f"a {answer} limit. Answer in one or two sentences and "
                    "stop. No context, no recap, no what-this-means.")
                silence_rule = True

    hits = [c for c in settled if c in low]
    if not reason and hits and words > short_enough:
        reason = (
            f"BLOCKED -- this reply is {words} words and re-argues points "
            "already settled: " + ", ".join(f'"{h}"' for h in hits[:4])
            + ". They are known and already priced into how this is read. "
              "Rewrite: lead with the answer, keep the caveat to at most "
              "one clause, and cut the rest.")

    if not reason and words > too_long:
        reason = (
            f"BLOCKED -- this reply is {words} words, over the {too_long} "
            "ceiling. Every word is charged against a usage limit and long "
            "explanations do not get read. Rewrite: the answer, any "
            "numbers with their sample and source, and nothing else.")

    # A BLOCK COSTS TWO REPLIES. THE SILENCE RULE NO LONGER BUYS ONE.
    #
    # A Stop hook cannot unsend. The reply is generated and rendered
    # before the hook is asked, so refusing one shows you the long
    # version AND the rewrite -- twice the words the limit exists to
    # save. For the two LENGTH rules that is still worth paying: a
    # 500-word wall replaced by three lines is a net saving. For the
    # silence rule it is not, because it fires on replies of a dozen to
    # a hundred words, where the rewrite costs more than the overrun.
    #
    # So silence is enforced BEFORE the reply, by remind.py, which is
    # free because it runs first -- and recorded here rather than
    # refused. The switch itself is unchanged and still yours.
    if reason and silence_rule:
        try:
            with open(os.path.join(os.path.dirname(__file__),
                                   "no_repeat.log"), "a",
                      encoding="utf-8") as fh:
                fh.write(f"{words} words past the silence limit, allowed"
                         " -- a block here would cost two replies" + chr(10))
        except Exception:
            pass
        reason = ""

    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
