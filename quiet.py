"""
The silence switch. You set it; a hook enforces it.

    python quiet.py on      silence
    python quiet.py off
    python quiet.py         what it is set to now
    python quiet.py --test  drive the real hook and prove it blocks

--- WHY ---

A word ceiling catches verbosity. It does not catch the failure that
actually costs you: you say "stop explaining", and every reply after
that is a two-hundred-word summary sitting comfortably under the
ceiling. The rule being broken is not "too long" -- it is speaking at
all after being told not to. Asking the model to remember is what
already failed.

--- WHAT SILENCE ALLOWS ---

    nothing at all              always. The expected case while working.
    under 12 words              always. "Done." is not the failure.
    up to 60 words              only when your last message asked
                                something.
    anything else               BLOCKED. The turn ends with no text.

Turning it off is yours. The hook will not do it, and the block reason
says so, so a model cannot read the switch as a suggestion.

--- WHERE IT LOOKS ---

`./.claude/hooks` first, then `~/.claude/hooks`, then a `hooks` folder
beside this file. Run it from your project and it finds the project's
install; run it anywhere and it finds the global one.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(os.getcwd(), ".claude", "hooks"),
    os.path.join(os.path.expanduser("~"), ".claude", "hooks"),
    os.path.join(HERE, "hooks"),
]


def _load():
    for path in CANDIDATES:
        if os.path.exists(os.path.join(path, "silence.py")):
            sys.path.insert(0, path)
            import silence                                # noqa: E402
            return silence, path
    print("\n  quiet-claude is not installed. Run:  python install.py\n")
    raise SystemExit(2)


silence, HOOKS = _load()


def show() -> int:
    st = silence.state()
    on = bool(st.get("on"))
    free = silence.limit("free_words", silence.FREE_WORDS)
    answer = silence.limit("answer_words", silence.ANSWER_WORDS)
    print()
    print(f"  silence is {'ON' if on else 'off'}"
          + (f"   (set {st.get('at')})" if st.get("at") else ""))
    if on:
        print(f"  allowed: nothing at all; under {free} words; up to "
              f"{answer} words when you asked a question")
    print(f"  hooks: {HOOKS}")
    print()
    return 0


def test() -> int:
    """
    Drive the real hook with a real payload. Reading it is not proof --
    a launcher that reads fine can still have never once worked.
    """
    import json
    import subprocess
    import tempfile

    hook = os.path.join(HOOKS, "no_repeat.py")
    was = bool(silence.state().get("on"))

    def run(assistant: str, user: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user",
                                 "message": {"content": user}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {
                "content": [{"type": "text", "text": assistant}]}}) + "\n")
        try:
            r = subprocess.run(
                [sys.executable, hook],
                input=json.dumps({"transcript_path": path,
                                  "stop_hook_active": False}),
                capture_output=True, text=True, timeout=30)
            return (r.stdout or "").strip()
        finally:
            os.unlink(path)

    long_reply = "word " * 200
    cases = []
    try:
        silence.set_on(True, "quiet.py --test")
        cases.append(("silenced, 200 words, nothing asked",
                      run(long_reply, "keep working"), True))
        cases.append(("silenced, under 12 words",
                      run("Done.", "keep working"), False))
        cases.append(("silenced, 40-word answer to a real question",
                      run("word " * 40, "how many are left?"), False))
        cases.append(("silenced, 200-word answer to a real question",
                      run(long_reply, "how many are left?"), True))
        cases.append(("silenced, empty reply",
                      run("", "keep working"), False))
        silence.set_on(False, "quiet.py --test")
        cases.append(("not silenced, 200 words",
                      run(long_reply, "keep working"), False))
        cases.append(("not silenced, 600 words -- over the ceiling",
                      run("word " * 600, "keep working"), True))
        cases.append(("garbage transcript path",
                      subprocess.run(
                          [sys.executable, hook],
                          input='{"transcript_path": "/nope/nope.jsonl"}',
                          capture_output=True, text=True,
                          timeout=30).stdout.strip(), False))
    finally:
        silence.set_on(was, "restored by quiet.py --test")

    print()
    bad = 0
    for what, out, want_block in cases:
        blocked = '"block"' in out
        ok = blocked == want_block
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {what:<46} "
              f"{'blocked' if blocked else 'allowed'}")
    print()
    print(f"  silence is {'ON' if silence.is_on() else 'off'} again")
    print()
    return 1 if bad else 0


def main() -> int:
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if arg in ("--test", "test"):
        return test()
    if arg in ("on", "off"):
        silence.set_on(arg == "on", "set by quiet.py")
        return show()
    if arg:
        print(f"  unknown: {arg!r}. Use on, off, or --test.")
        return 2
    return show()


if __name__ == "__main__":
    raise SystemExit(main())
