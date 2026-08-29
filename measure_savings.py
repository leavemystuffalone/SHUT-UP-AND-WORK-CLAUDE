"""What the quiet hooks would have saved, measured on real transcripts.

Reads Claude Code session .jsonl files and answers one question:
how much of the money spent went on assistant PROSE, as opposed to
tool calls, and how much of that prose the hooks would have blocked.

WHAT IT MEASURES
  output tokens   from message.usage.output_tokens -- the billed
                  number, not an estimate
  prose share     text blocks / (text + tool_use blocks), by
                  characters, applied to the billed output tokens
  blockable       prose in replies the silence hook would have
                  refused: over 12 words, or over 60 after a question

WHAT IT DOES NOT MEASURE
  - the input side. A blocked reply is also never re-sent as input on
    later turns, so the real saving is LARGER than the number here.
    How much larger depends on how early in the session it was said,
    and this does not model that.
  - whether the work would still have got done. It assumes the tool
    calls are unchanged and only the prose goes.
  - cache discounts. Output tokens are never cached, so the output
    figure is exact; the uncounted input side would be discounted.

    python measure_savings.py
    python measure_savings.py --by-session
"""
import json
import os
import sys
import glob

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
FREE_WORDS = 12
ANSWER_WORDS = 60


def _blocks(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    if isinstance(c, list):
        return c
    return []


def scan(path):
    """One session -> counts. Returns None if it holds no assistant turns."""
    out_tokens = 0
    text_chars = 0
    tool_chars = 0
    blockable_chars = 0
    turns = 0
    asked = False          # did the user's last message end in a question
    rows = 0

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rows += 1
            kind = row.get("type")

            if kind == "user":
                m = row.get("message") or {}
                txt = "".join(
                    b.get("text", "") for b in _blocks(m)
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if txt.strip():
                    asked = "?" in txt
                continue

            if kind != "assistant":
                continue

            m = row.get("message") or {}
            usage = m.get("usage") or {}
            out_tokens += usage.get("output_tokens", 0) or 0
            turns += 1

            reply_text = ""
            for b in _blocks(m):
                if not isinstance(b, dict):
                    continue
                t = b.get("type")
                if t == "text":
                    reply_text += b.get("text", "")
                elif t == "tool_use":
                    tool_chars += len(json.dumps(b.get("input", "")))
                elif t == "thinking":
                    pass  # billed, but the hooks never touch it

            text_chars += len(reply_text)
            words = len(reply_text.split())
            limit = ANSWER_WORDS if asked else FREE_WORDS
            if words > limit:
                # what survives is the limit; the rest is what the hook
                # would have refused
                keep = limit / float(words)
                blockable_chars += len(reply_text) * (1.0 - keep)

    if not turns:
        return None
    return {
        "path": path,
        "rows": rows,
        "turns": turns,
        "out_tokens": out_tokens,
        "text_chars": text_chars,
        "tool_chars": tool_chars,
        "blockable_chars": blockable_chars,
    }


def main():
    by_session = "--by-session" in sys.argv
    files = sorted(glob.glob(os.path.join(ROOT, "*", "*.jsonl")))
    if not files:
        print("no transcripts found under " + ROOT)
        return 1

    rolled = []
    for p in files:
        s = scan(p)
        if s:
            rolled.append(s)

    if not rolled:
        print("no assistant turns in %d files" % len(files))
        return 1

    T = sum(s["out_tokens"] for s in rolled)
    TX = sum(s["text_chars"] for s in rolled)
    TL = sum(s["tool_chars"] for s in rolled)
    BL = sum(s["blockable_chars"] for s in rolled)
    turns = sum(s["turns"] for s in rolled)
    total_chars = TX + TL

    if by_session:
        print("%-40s %7s %7s %6s %6s" % (
            "session", "turns", "output", "prose", "blockd"))
        for s in sorted(rolled, key=lambda r: -r["out_tokens"]):
            c = s["text_chars"] + s["tool_chars"]
            if not c:
                continue
            print("%-40s %7d %7d %5.1f%% %5.1f%%" % (
                os.path.basename(s["path"])[:40],
                s["turns"], s["out_tokens"],
                100.0 * s["text_chars"] / c,
                100.0 * s["blockable_chars"] / c))
        print("")

    print("SAMPLE   %d sessions, %d assistant turns, %s output tokens"
          % (len(rolled), turns, "{:,}".format(T)))
    print("SOURCE   %s" % ROOT)
    print("STATUS   MEASURED on the output side, FLOOR overall --")
    print("         blocked text is also never re-sent as input, and")
    print("         that saving is not counted here")
    print("")
    if total_chars:
        print("prose share of output      %5.1f%%   (%s of %s chars)" % (
            100.0 * TX / total_chars,
            "{:,}".format(TX), "{:,}".format(total_chars)))
        print("what the hook would block  %5.1f%%   of all output" % (
            100.0 * BL / total_chars))
        print("tokens that is, roughly    %s of %s" % (
            "{:,}".format(int(T * BL / total_chars)), "{:,}".format(T)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
