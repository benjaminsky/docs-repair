# metadiscourse-audit

A Claude Code skill that finds and removes **metadiscourse** from prose
documentation — text whose subject is the document, its author, or its reader
rather than the thing the document is about.

Most of it arrives through revision, not drafting. A fact changes, and the new
fact gets appended next to the old one instead of replacing it. Each append is
individually defensible; the cost compounds invisibly, and the densest files in
any repo are the ones that were revised most.

## What it finds

**Iteration artifacts** — the document narrating its own history:

```diff
- _Changed in `rules/2026-04-b`: state X was previously inferred from a passed
- date; it now requires a recorded event._
```

```diff
- migrations live in `migrations/` and are the source of truth for the schema
- (it is no longer auto-created on first request).
+ migrations live in `migrations/` and are the source of truth for the schema.
```

**Caveats in the main line** — content worth keeping, in the wrong place. A
qualification set inside the sentence it qualifies doubles the reader's work;
the same qualification as a footnote costs nothing until someone wants it.

**Staging tics** — announcing how many bullets follow, "it's worth noting",
headings that argue instead of naming, and the same superlative claimed in four
different files.

Every finding gets `file:line`, the verbatim text, a class, a verdict
(cut / fold / move / keep) and a concrete rewrite.

## Install

Clone into your personal skills directory:

```bash
git clone https://github.com/benjaminsky/metadiscourse-audit \
  ~/.claude/skills/metadiscourse-audit
```

Or per-project, so the whole team gets it:

```bash
git clone https://github.com/benjaminsky/metadiscourse-audit \
  .claude/skills/metadiscourse-audit
```

Claude picks it up on the next session. No dependencies — the scanner is Python
3 stdlib only.

## Use

Ask for it in your own words:

> the docs in ./docs have gotten crufty — they read like a changelog in places,
> can you clean them up?

> audit ./docs and tell me what's wrong with the writing. don't change anything
> yet, I want the list first

Or invoke it directly with `/metadiscourse-audit`.

The scanner also runs standalone:

```bash
python3 scripts/scan.py docs README.md      # candidates, grouped by class
python3 scripts/scan.py docs --class 0      # iteration artifacts only
python3 scripts/scan.py docs --json         # machine-readable
python3 scripts/scan.py docs --check        # exit 1 on any finding, for CI
python3 scripts/scan.py docs --fix --dry-run
```

`--fix` applies only rewrites whose removal cannot lose a fact — stripping a
"worth …" wrapper, removing "it is worth noting that". Expect single digits on
a large corpus, often zero. Everything valuable needs a human to decide what
the surviving fact is, and keeping `--fix` that narrow is what makes it safe to
run unattended.

## What it will not do

**It will not touch your records.** A document is either the events or a
projection of them, never both. A dated plan, spec, ADR, RFC or changelog is an
*event* — written once, read as of its date, and its "previously / now"
language is its content. Those are excluded by default. A README or runbook is
a *projection* of those events onto now, and that is what gets audited.

On two real repositories, record documents were 175 of 234 and 117 of 121 of
all raw findings. Left in, they bury everything that matters.

**It will not strip your conventions.** It reads `CLAUDE.md`, `AGENTS.md` and
any style guide first, and treats what it finds as protected. A repo whose
rules say "stated vs inferred is never blurred" needs its evidence tags; a repo
that versions its rules needs the version identifiers. Getting this wrong is
the main way an audit like this does damage.

## Layout

```
SKILL.md              the workflow Claude follows
references/           the twelve classes, with worked examples and rewrites
scripts/scan.py       the scanner — stdlib only, runs from any cwd
evals/                test cases for the skill body and for triggering
```

## Scope

This is for prose that has drifted through revision. It is not for scrubbing AI
writing voice out of freshly generated text, finding docs stale relative to
code, generating changelogs, reconciling contradictory content, translating,
proofreading, or cleaning up code.

## Licence

MIT. See [LICENSE](LICENSE).
