"""
Install quiet-claude into a project or into your home directory.

    python install.py                 this project (./.claude)
    python install.py --global        every project (~/.claude)
    python install.py --status        what is installed where
    python install.py --uninstall     remove the hooks and settings
    python install.py --no-claude-md  hooks only, leave CLAUDE.md alone

WHAT IT WRITES

    .claude/hooks/silence.py          the switch and the limits
    .claude/hooks/no_repeat.py        the Stop hook that blocks
    .claude/hooks/remind.py           the UserPromptSubmit hook
    .claude/hooks/quiet.config.json   your limits, yours to edit
    .claude/settings.json             the two hook entries, MERGED
    CLAUDE.md                         the working agreement

WHAT IT WILL NOT DO. It never overwrites an existing CLAUDE.md or an
existing quiet.config.json -- your edits survive a re-install. Every
other file is refreshed. settings.json is merged key by key, and the two
hook entries are matched by their command, so running this twice does
not give you the hook twice.

A NEW HOOK DOES NOT FIRE IN THE SESSION THAT INSTALLED IT. Restart
Claude Code, or open /hooks once, and it is live.
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_HOOKS = os.path.join(HERE, "hooks")
HOOK_FILES = ("silence.py", "no_repeat.py", "remind.py")

STOP_CMD = 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/no_repeat.py"'
PROMPT_CMD = 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/remind.py"'

DEFAULT_CONFIG = {
    "free_words": 12,
    "answer_words": 60,
    "too_long": 450,
    "short_enough": 120,
    "settled": [],
    "_settled_note": (
        "Phrases you have already accepted and do not want re-argued. "
        "A reply over short_enough words that repeats one is blocked; "
        "one clause naming it is always allowed."),
    "_reminder_note": (
        'Set "reminder" to your own text to change what is injected '
        'before every reply, or to "" to switch that hook off.'),
}


def root(is_global: bool) -> str:
    return os.path.expanduser("~") if is_global else os.getcwd()


def _global_cmd(path: str, name: str) -> str:
    """
    A global install has no $CLAUDE_PROJECT_DIR to stand on -- that
    variable points at whatever project is open, which is exactly where
    the hooks are NOT. So the home install carries an absolute path.
    """
    return f'python "{os.path.join(path, ".claude", "hooks", name)}"'


def install(is_global: bool, write_md: bool) -> int:
    base = root(is_global)
    hooks = os.path.join(base, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)

    for name in HOOK_FILES:
        shutil.copyfile(os.path.join(SRC_HOOKS, name),
                        os.path.join(hooks, name))

    cfg = os.path.join(hooks, "quiet.config.json")
    if not os.path.exists(cfg):
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump(DEFAULT_CONFIG, fh, indent=2)

    stop = _global_cmd(base, "no_repeat.py") if is_global else STOP_CMD
    prompt = _global_cmd(base, "remind.py") if is_global else PROMPT_CMD
    settings_path = os.path.join(base, ".claude", "settings.json")
    merge_settings(settings_path, stop, prompt)

    made_md = ""
    if write_md:
        dest = os.path.join(base, "CLAUDE.md")
        if os.path.exists(dest):
            made_md = f"CLAUDE.md already exists -- left alone. Add the " \
                      f"rules from {os.path.join(HERE, 'CLAUDE.md')}"
        else:
            shutil.copyfile(os.path.join(HERE, "CLAUDE.md"), dest)
            made_md = f"wrote {dest}"

    print()
    print(f"  installed to {os.path.join(base, '.claude')}")
    print(f"  hooks       {', '.join(HOOK_FILES)}")
    print(f"  settings    {settings_path}")
    print(f"  limits      {cfg}")
    if made_md:
        print(f"  {made_md}")
    print()
    print("  RESTART Claude Code -- a new hook does not fire in the")
    print("  session that installed it.")
    print()
    print("  then:  python quiet.py --test     prove it blocks")
    print("         python quiet.py on         silence")
    print()
    return 0


def merge_settings(path: str, stop: str, prompt: str) -> None:
    """
    Add the two hook entries without touching anything else in the file,
    and without adding them twice. An unreadable settings.json RAISES
    rather than being overwritten with a fresh one -- rewriting a file
    you failed to read is how a config gets erased.
    """
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
        if raw:
            data = json.loads(raw)          # deliberately not caught
            if not isinstance(data, dict):
                raise ValueError(f"{path} is not a JSON object")

    hooks = data.setdefault("hooks", {})
    for event, cmd, timeout in (("Stop", stop, 15),
                                ("UserPromptSubmit", prompt, 10)):
        entries = hooks.setdefault(event, [])
        already = any(h.get("command") == cmd
                      for e in entries if isinstance(e, dict)
                      for h in (e.get("hooks") or [])
                      if isinstance(h, dict))
        if not already:
            entries.append({"hooks": [{"type": "command",
                                       "command": cmd,
                                       "timeout": timeout}]})

    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def uninstall(is_global: bool) -> int:
    base = root(is_global)
    hooks = os.path.join(base, ".claude", "hooks")
    gone = []
    for name in HOOK_FILES + ("quiet.config.json", "silence.json"):
        p = os.path.join(hooks, name)
        if os.path.exists(p):
            os.remove(p)
            gone.append(name)

    path = os.path.join(base, ".claude", "settings.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for event in ("Stop", "UserPromptSubmit"):
            kept = []
            for e in (data.get("hooks", {}).get(event) or []):
                inner = [h for h in (e.get("hooks") or [])
                         if "no_repeat.py" not in str(h.get("command", ""))
                         and "remind.py" not in str(h.get("command", ""))]
                if inner:
                    e["hooks"] = inner
                    kept.append(e)
            if data.get("hooks", {}).get(event) is not None:
                data["hooks"][event] = kept
                if not kept:
                    del data["hooks"][event]
        if not data.get("hooks"):
            data.pop("hooks", None)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)

    print(f"\n  removed {', '.join(gone) if gone else 'nothing'} from "
          f"{hooks}")
    print("  CLAUDE.md left alone -- delete it yourself if you want it "
          "gone.\n")
    return 0


def status() -> int:
    print()
    for label, base in (("project", os.getcwd()),
                        ("global ", os.path.expanduser("~"))):
        hooks = os.path.join(base, ".claude", "hooks")
        there = os.path.exists(os.path.join(hooks, "no_repeat.py"))
        line = f"  {label}  {'INSTALLED' if there else 'not installed'}"
        if there:
            sys.path.insert(0, hooks)
            try:
                import importlib
                import silence
                importlib.reload(silence)
                line += f"   silence {'ON' if silence.is_on() else 'off'}"
            except Exception:
                line += "   (config unreadable)"
            finally:
                sys.path.pop(0)
        print(line + f"   {hooks}")
    print()
    return 0


def main() -> int:
    args = [a.lower() for a in sys.argv[1:]]
    if "--status" in args:
        return status()
    is_global = "--global" in args
    if "--uninstall" in args:
        return uninstall(is_global)
    return install(is_global, "--no-claude-md" not in args)


if __name__ == "__main__":
    raise SystemExit(main())
