# quiet-claude

**A working agreement for Claude Code, plus the hooks that enforce the
parts it will otherwise forget.**

Claude Code narrates. It recaps work you watched it do, explains fixes
you did not ask about, restates your request back to you, and offers
three options at length instead of picking one. All of it is charged
against your usage limit, and none of it gets read.

You can write "stop explaining" in a `CLAUDE.md`. It works for about
twenty messages.

So this repo is two things:

1. **`CLAUDE.md`** -- the working agreement. Silence by default, lead
   with the answer, every number carries its sample and source, count it
   rather than quote it, hand long mechanical jobs back as a script.
2. **Three hooks** -- because a note is advice, and advice loses to
   reflex. The rules that cost the most are checked by something that
   runs.

## Install

```bash
git clone https://github.com/leavemystuffalone/SHUT-UP-AND-WORK-CLAUDE
cd SHUT-UP-AND-WORK-CLAUDE
python install.py            # this project
python install.py --global   # every project
```

Then **restart Claude Code**. A new hook does not fire in the session
that installed it.

```bash
python quiet.py --test       # drive the real hook, prove it blocks
python quiet.py on           # silence
python quiet.py off
python quiet.py              # what it is set to
python install.py --status
python install.py --uninstall
```

`install.py` merges into an existing `.claude/settings.json` key by key
and never adds the same hook twice. It will not overwrite a `CLAUDE.md`
you already have, and it will not overwrite your limits once you have
edited them.

## The switch

The word ceiling was the obvious thing to build and it is not the thing
that fails. What fails is this: you say "stop explaining", and every
reply afterwards is a two-hundred-word summary sitting comfortably under
any ceiling you set. The rule being broken is not *too long*. It is
*speaking at all after being told not to*, and asking the model to
remember is the approach that already failed.

`python quiet.py on` turns that into a check. While silence is on:

| the reply | what happens |
|---|---|
| nothing at all | allowed -- and it is the expected case while working |
| under 12 words | allowed. "Done." is not the failure |
| up to 60 words, and you asked a question | allowed |
| anything else | **blocked.** The turn ends with no text |

A blocked reply is never sent. The reason goes back to the model, which
rewrites or stays quiet. **Turning it off is your action** -- the block
reason says so, so the model cannot read the switch as a suggestion.

Off by default. Turn it on for a long unattended run, off when you want
to talk.

## What each hook does

| file | fires | does |
|---|---|---|
| `hooks/remind.py` | every prompt | injects the short rules ahead of the reply, so they cannot fade between message 5 and message 90 |
| `hooks/no_repeat.py` | every stop | reads the reply and blocks it if it breaks them |
| `hooks/silence.py` | -- | the switch, the limits, and the state file |

**Everything fails open.** Unreadable transcript, unknown payload,
missing field, bad stdin -- every path exits 0 and allows the message. A
hook that breaks your session is worse than the padding it exists to
stop.

## Your limits

`.claude/hooks/quiet.config.json`:

```json
{
  "free_words": 12,
  "answer_words": 60,
  "too_long": 450,
  "short_enough": 120,
  "settled": []
}
```

- **`too_long`** -- a hard ceiling on any reply, silence or not.
- **`settled`** -- phrases you have already accepted and do not want
  re-argued. A long reply repeating one is blocked; **one clause naming
  it is always allowed**, because the paragraph is the failure, not the
  mention. Fill this with whatever your project keeps re-litigating.
- **`reminder`** -- add it to replace the per-turn text with your own,
  or set it to `""` to switch that hook off without uninstalling.

Re-running `install.py` refreshes the hooks and leaves this file alone.

## What it actually saves

    python measure_savings.py
    python measure_savings.py --by-session

Reads your own Claude Code transcripts and reports how much of the
billed output went on prose rather than tool calls, and how much of
that the silence hook would have refused.

**Measured on this author's history: 9.9% of all output tokens --
SAMPLE 26 sessions, 17,789 assistant turns, 15.25M output tokens,
SOURCE `~/.claude/projects/*.jsonl`, MEASURED.** Per session it ranged
from 0.8% to 22%.

That is a **FLOOR**, not the whole saving: a reply that is never sent
is also never re-sent as input on every following turn, and the script
does not model the input side at all. It also assumes the tool calls
stay the same and only the talking goes.

Run it on your own history before believing the number. A session that
is mostly conversation will score far higher than one that is mostly
edits.

## The agreement itself

Read `CLAUDE.md`. The short version:

- **It stops talking.** No narration, no recaps, no "here is what I am
  about to do", no re-explaining a fix you watched it make.
- **It decides instead of asking**, and stops re-arguing conclusions you
  already settled.
- **Every number carries its sample, its source, and whether it was
  measured or assumed** -- beside the number, not in a footnote.
- **It checks before it reports** -- one real row, reconciled against a
  figure that already exists, with the boundary of what was actually
  checked stated out loud.
- **It stops mixing data up.** A number in a doc is a snapshot to
  re-count, not a fact to quote; "we could not measure it" never becomes
  "it is zero"; a field is not assumed to be what it is called.
- **It hands long mechanical jobs back to you as a one-command script**
  instead of burning your tokens grinding through them.
- **It sends long prose to a subagent to write**, so a 6,000-token
  essay never sits in the main window being re-sent every turn.

Delete any rule you disagree with. It works in pieces.

## Requirements

Python 3.8+ and Claude Code. Nothing else -- no dependencies, no
network, nothing leaves your machine.

## Licence

MIT.
