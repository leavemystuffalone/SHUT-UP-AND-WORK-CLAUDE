"""
PreToolUse hook: refuse a long prose Write and send it to a subagent.

WHAT IT DOES. Reads the Write about to happen and blocks it if:

    the file is prose (.md / .txt / .rst / no extension)
      AND the content is over LONG_WRITE_WORDS
      AND the file does not already exist                -> blocked

The reason handed back tells the model to spawn a subagent, have IT
write the file, and return only the path.

WHY. A long thing written in the main window is paid for twice: once as
output, and again as input on every following turn, because it stays in
context and is re-sent. Writing it to a file yourself saves nothing --
the whole text passes through the window on its way to disk. A subagent
composes it in ITS window and hands back a filename.

MEASURED at 500 words on 26 sessions / 17,822 assistant turns: 302
writes diverted, 24.6M tokens kept out of context. At 250 the rule
diverts 434 more for 9M -- mostly ordinary code writes a cold subagent
would handle worse. CEILING: caching and the subagent's own cold start
are uncounted. `measure_subagent.py` is the sweep.

WHAT IT DELIBERATELY DOES NOT BLOCK:

  - CODE. A .py / .ts / .json file is not prose and the rule has no
    business there, however long it is.
  - EDITS. Editing an existing document means it is already in context;
    diverting it to a cold agent costs more than it saves. Only a NEW
    prose file is refused.
  - anything the model has already been told to write here -- passing
    `--long-write-ok` in the content, or setting the limit to 0, turns
    it off without uninstalling.

FAIL OPEN, ALWAYS. Unknown payload, missing field, bad stdin, an
unreadable config -- every one exits 0 and allows the write. A hook
that breaks your session is worse than the tokens it exists to save.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import silence
except Exception:                    # fail open -- see the module note
    silence = None

LONG_WRITE_WORDS = 500
PROSE_EXTENSIONS = (".md", ".txt", ".rst", ".markdown", "")
ESCAPE = "--long-write-ok"


def is_prose(path: str) -> bool:
    """True for a document, false for code. Extension only -- deliberate.

    Guessing prose from content would misfire on a docstring-heavy
    module, and a wrong block is worse than a missed one here.
    """
    return os.path.splitext(path)[1].lower() in PROSE_EXTENSIONS


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Write":
        return 0

    tool = payload.get("tool_input") or {}
    path = tool.get("file_path") or ""
    content = tool.get("content") or ""
    if not path or not isinstance(content, str):
        return 0

    limit = LONG_WRITE_WORDS
    if silence is not None:
        try:
            limit = int(silence.limit("long_write_words", LONG_WRITE_WORDS))
        except Exception:
            limit = LONG_WRITE_WORDS
    if limit <= 0:                   # switched off in the config
        return 0

    if ESCAPE in content:
        return 0
    if not is_prose(path):
        return 0

    # An existing file is already in context; diverting an edit to a
    # cold agent costs more than it saves.
    try:
        if os.path.exists(path):
            return 0
    except Exception:
        return 0

    words = len(content.split())
    if words <= limit:
        return 0

    reason = (
        "BLOCKED -- this is a %d-word prose file and the limit is %d. "
        "Writing it here costs twice: once as output, then again as "
        "input on every following turn, because the whole text stays "
        "in this context window and is re-sent. Writing it to disk "
        "yourself saves nothing -- it passes through the window either "
        "way.\n\n"
        "Spawn a subagent, have IT write %s, and report back only the "
        "path in one line. If this genuinely must be written here, put "
        "%s somewhere in the content and it will pass."
        % (words, limit, path, ESCAPE))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
