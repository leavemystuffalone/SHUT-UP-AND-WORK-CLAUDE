"""What sending long writes to a subagent would have saved.

The companion to measure_savings.py, which measures the OUTPUT side --
words never spoken. This measures the INPUT side: a long thing written
into the main window is re-sent as input on every turn that follows it,
for the rest of the session.

    cost of one long write = its own output
                           + its size x every turn after it

A subagent composes it in its own window and returns a filename, so the
main window pays neither. The question this answers is where to put the
threshold: too low and it exiles ordinary code edits to a cold agent
that has to re-read the repo; too high and the long ones still land in
the window.

WHAT IT MEASURES
  Every Write / NotebookEdit tool call and every assistant text block
  in your transcripts, sized in characters, multiplied by the number of
  assistant turns that came after it in the same session. That product
  is what a subagent would have kept out of the window.

WHAT IT DOES NOT MEASURE
  - CACHING. Repeated input hits the prompt cache at a large discount,
    so the dollar saving is much smaller than the token count here.
    This is a TOKEN figure, not a bill.
  - COMPACTION. A long session is summarised, which retires old text
    early. Sessions that compacted are over-counted.
  - THE SUBAGENT'S OWN COST. It starts cold and re-reads what it needs,
    which is a real cost this does not net off.
  - Edits, which are diffs against a file already in context.

  So: a CEILING on the saving, in tokens, not in money.

    python measure_subagent.py
    python measure_subagent.py --thresholds
"""
import json
import os
import sys
import glob

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
CHARS_PER_TOKEN = 4.0
WORD_THRESHOLDS = [100, 250, 500, 1000, 2000, 5000]
WRITE_TOOLS = ("Write", "NotebookEdit")


def _blocks(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return c if isinstance(c, list) else []


def scan(path):
    """Return (list of long items, total assistant turns).

    An item is (index_of_turn, chars, words, kind).
    """
    items = []
    turn = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "assistant":
                continue
            turn += 1
            for b in _blocks(row.get("message") or {}):
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    if b.get("name") in WRITE_TOOLS:
                        c = (b.get("input") or {}).get("content", "")
                        if isinstance(c, str) and c:
                            items.append((turn, len(c), len(c.split()),
                                          "write"))
                elif b.get("type") == "text":
                    t = b.get("text", "")
                    if t:
                        items.append((turn, len(t), len(t.split()), "reply"))
    return items, turn


def carried(items, total_turns, min_words, horizon):
    """Tokens a subagent would have kept out of the main window.

    `horizon` caps how many following turns a piece of text is assumed
    to survive in context before compaction retires it. Without a cap
    the arithmetic assumes nothing is ever summarised away, which for a
    2,600-turn session is wrong by orders of magnitude.
    """
    own = 0.0
    resent = 0.0
    n = 0
    for turn, chars, words, _kind in items:
        if words < min_words:
            continue
        n += 1
        own += chars
        after = max(0, total_turns - turn)
        if horizon:
            after = min(after, horizon)
        resent += chars * after
    return n, own / CHARS_PER_TOKEN, resent / CHARS_PER_TOKEN


def main():
    show_thresholds = "--thresholds" in sys.argv
    horizon = 0
    for a in sys.argv[1:]:
        if a.startswith("--horizon="):
            horizon = int(a.split("=", 1)[1])
    files = sorted(glob.glob(os.path.join(ROOT, "*", "*.jsonl")))
    if not files:
        print("no transcripts found under " + ROOT)
        return 1

    sessions = []
    all_chars = 0
    for p in files:
        items, turns = scan(p)
        if turns:
            sessions.append((items, turns))
            all_chars += sum(i[1] for i in items)

    if not sessions:
        print("no assistant turns in %d files" % len(files))
        return 1

    total_turns = sum(t for _i, t in sessions)
    print("SAMPLE   %d sessions, %s assistant turns" % (
        len(sessions), "{:,}".format(total_turns)))
    print("SOURCE   %s" % ROOT)
    print("STATUS   CEILING -- caching and the subagent's own cold")
    print("         start are uncounted; compaction only if you pass")
    print("         --horizon=N (turns a write survives in context)")
    if horizon:
        print("HORIZON  %d turns" % horizon)
    print("")

    rows = WORD_THRESHOLDS if show_thresholds else [500]
    print("%8s %8s %12s %14s %14s" % (
        "min", "hits", "own output", "re-sent input", "total tokens"))
    for mw in rows:
        n = own = res = 0.0
        for items, turns in sessions:
            a, b, c = carried(items, turns, mw, horizon)
            n += a
            own += b
            res += c
        print("%8d %8d %12s %14s %14s" % (
            mw, n,
            "{:,}".format(int(own)),
            "{:,}".format(int(res)),
            "{:,}".format(int(own + res))))

    print("")
    print("'hits' is how many writes/replies the rule would divert.")
    print("The re-sent column is the whole point: it is what a long")
    print("thing costs AFTER it is written, just by sitting there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
