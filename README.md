# Metadiscourse Audit

Metadiscourse Audit finds and removes the text in your documentation whose subject is the document, its author, or its reader, rather than the thing the document is actually about.

## Quickstart

Give your agent the audit: [Claude Code](#claude-code), [any agent that reads AGENTS.md](#any-agent-that-reads-agentsmd), or [no agent at all](#no-agent-at-all).

Once it is installed, the run that works is two prompts rather than one. Ask
for the inventory first:

> Audit `docs/` and `README.md` for metadiscourse. Give me the findings list —
> don't edit anything yet.

You get `file:line`, the verbatim text, a class, a verdict and a rewrite for
each. Then approve a slice of it:

> Apply the class 0 and 0.5 findings. Show me the diff for anything you move
> rather than cut.

Splitting it this way is worth the extra turn: class 0 and 0.5 are the two
classes with objective tests, so they arrive fastest and are the ones you will
almost always accept, while the staging classes below them are taste and
deserve a look before they land. Point it at a **doc set**, not one file — the
collision pass and the density ranking only mean anything across a corpus, and
both are the outputs that tell you where to edit next.

## How it works

Most metadiscourse is not a drafting problem. It arrives through revision. A fact changes, and the new fact gets appended next to the old one instead of replacing it — so the document starts narrating how it reached its current state instead of just stating it. Every one of those appends was correct when it was written, which is why nobody catches them, and why the densest files in your repo are the ones you have edited most.

The audit starts by reading your project's own rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, a style guide, whatever you use. Projects encode conventions that *require* this kind of text, and stripping them is the main way an audit like this does damage. Whatever it finds there is protected for the rest of the run.

Then it separates your records from your standing documents. A document is either the events or a projection of them, never both. A dated plan, spec, ADR or changelog is an event: written once, read as of its date, and its "previously / now" language is its content. Those are left alone. A README or a runbook is a projection of those events onto now, and that is what gets audited.

Only then does it scan. You get a list of findings, each with a `file:line`, the text itself, a class, a verdict — cut, fold, move, or keep — and a concrete rewrite. Ask for the list first if you want to approve before anything changes, or let it apply the edits.

Two rules shape the verdicts. Caveats are never cut, only moved: a risk or a hedge is content, and the failure is that it interrupts the sentence you came for instead of sitting in a footnote. And a superlative is information exactly once — when four documents each claim to hold the single most important thing, they cancel.

## What it finds

A document arguing with its own history:

```diff
- _Changed in `rules/2026-04-b`: state X was previously inferred from a passed
- date; it now requires a recorded event._
```

```diff
- An earlier draft of this doc said the timeout was 30s. It is 10s.
+ The timeout is 10s.
```

```diff
- The parser now handles doubled quotes.
+ The parser handles doubled quotes.
```

A deleted behaviour that mattered to whoever upgraded, and to nobody since:

```diff
- Migrations are the source of truth for the schema (it is no longer
- auto-created on first request).
+ Migrations are the source of truth for the schema.
```

A date stamped into a paragraph, promising an update that never comes:

```diff
- **Status 2026-04-02:** the batch job has not been made idempotent (issue #14).
+ Making the batch job idempotent is the obvious next change (issue #14).
```

The cross-reference stays. Only the claim about its state goes, because that is the part the tracker already knows and the paragraph does not.

A caveat wedged into the sentence it qualifies:

```diff
- The window measures back from the end date, not the start date. The start
- date would be tighter — goods ship at construction start, not eighteen months
- later — but that column is sparsely populated, and an anchor that is usually
- absent produces a mostly blank report. Revisit if a future month fills it in.
+ The window measures back from the end date, not the start date.[^anchor]
```

A section that announces how many bullets are about to follow:

```diff
- Two priors worth defending explicitly:
+ Two priors:
```

The count stays — sometimes it carries the argument, as in "two *independent* defences". The wrapper goes.

A heading that argues instead of naming:

```diff
- ## The distinction that decides the whole design
+ ## The model maps columns; code reads cells
```

```diff
- ## Format stability — measured, not assumed
+ ## Format stability
```

An attitude marker rating your attention instead of telling you something:

```diff
- Worth a glance while the file is open: are the milestone columns dates?
+ Check that the milestone columns hold dates, not status strings.
```

And the one that only shows up across a whole doc set: four different files each claiming to hold the single most important thing. They cancel. Three become ordinary claims and one keeps the crown.

## Installation

### Claude Code

Add the marketplace, then install the plugin:

```
/plugin marketplace add benjaminsky/metadiscourse-audit
/plugin install benjaminsky@benjaminsky-skills
```

That gives you `/benjaminsky:metadiscourse-audit`, and Claude will reach for it on its own when you describe the problem. Update later with `/plugin marketplace update benjaminsky-skills`.

If you would rather keep it as a plain skill with no plugin machinery, clone it into your skills directory instead:

```bash
git clone https://github.com/benjaminsky/metadiscourse-audit
cd metadiscourse-audit && ./install.sh
```

That installs to `~/.claude/skills/metadiscourse-audit`. Pass `--project` to install into the current repo instead, `--link` to symlink so `git pull` updates it in place, or `--uninstall` to remove it. It will not overwrite a directory it did not create.

### Any agent that reads AGENTS.md

`AGENTS.md` is the portable route — Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf and Zed all read it. Clone the repository somewhere your agent can see, then point at the skill from your `AGENTS.md`:

```bash
git clone https://github.com/benjaminsky/metadiscourse-audit .agent/metadiscourse-audit
```

```markdown
## Documentation

When asked to clean up, tighten or de-cruft docs, follow
`.agent/metadiscourse-audit/skills/metadiscourse-audit/SKILL.md`.
```

`SKILL.md` is plain Markdown with YAML frontmatter and no tool-specific syntax, so nothing needs translating. `references/classes.md` is loaded on demand, only when a finding is ambiguous.

Cursor's own `.cursor/rules/*.mdc` format expects MDC files rather than a skill directory, so use the `AGENTS.md` route there too — Cursor reads it natively.

### No agent at all

The scanner is a plain command-line tool. Python 3 standard library, no dependencies, no install step:

```bash
git clone https://github.com/benjaminsky/metadiscourse-audit ~/src/metadiscourse-audit
export SCAN=~/src/metadiscourse-audit/skills/metadiscourse-audit/scripts/scan.py
```

Run it from the root of the project you are auditing. The corpus arguments
(`docs`, `README.md`) resolve against your working directory, not against the
clone — which is why the script is addressed by absolute path and the corpus by
relative one:

```bash
cd ~/src/my-project
python3 "$SCAN" docs README.md
```

It reports candidates grouped by class. A human decides what to do with them.

```bash
python3 "$SCAN" docs --class 0      # iteration artifacts only
python3 "$SCAN" docs --json         # machine-readable
python3 "$SCAN" docs --check        # exit 1 on any finding
python3 "$SCAN" docs --fix --dry-run
```

For CI, gate on iteration artifacts alone — that is the class with an objective test:

```bash
python3 "$SCAN" docs --class 0 --check
```

`--fix` applies only the rewrites whose removal cannot lose a fact: stripping a "worth …" wrapper, removing "it is worth noting that". Expect single digits across a large corpus, often zero. Everything else needs someone to decide what the surviving fact is, and keeping `--fix` that narrow is what makes it safe to run unattended.

## A worked run

The repository ships a planted fixture, so you can see real output before
pointing this at your own docs. From the root of your clone:

```bash
cd evals/fixtures/repo-a
python3 ../../../skills/metadiscourse-audit/scripts/scan.py docs CLAUDE.md
```

The head of the output is the two classes with objective tests:

```
=== class 0a — 5 candidate(s) ===
docs/ingest.md:5  [prior-state reference]
    _Changed in `ingest/2026-04-b`: the delimiter was previously assumed to be a
docs/sources.md:8  [prior-state reference]
    An earlier version of this section said six of nine feeds needed OCR. That was

=== class 0c — 1 candidate(s) ===
docs/ingest.md:19  [dated status stamp]
    **Status 2026-05-02:** the batch job has not been made idempotent (issue #14).
```

The tail is the part that only works corpus-wide:

```
collisions: none — no superlative or aphorism repeats across files

=== density — candidates per 100 lines ===
    64.0  docs/ingest.md  (16 in 25 lines)
    41.7  docs/sources.md  (5 in 12 lines)

clean: CLAUDE.md

21 candidate(s) across 3 file(s).
Skipped 1 point-in-time record(s) — dated plans, specs, ADRs, changelogs.
```

Density says where to start editing. `clean:` is what a later rewrite must not
regress. The skipped record is the ADR, left alone by design.

`--fix` on that fixture reports zero, which is the honest answer: every finding
in it needs someone to decide what the surviving fact is. It earns its keep on
plainer filler:

```
$ python3 "$SCAN" docs --fix --dry-run
docs/guide.md
  3: - It is worth noting that the parser accepts CSV and XLSX.
  3: + The parser accepts CSV and XLSX.
  5: - Two priors worth defending explicitly:
  5: + Two priors:
  10: - Please note that the cache is LRU.
  10: + The cache is LRU.

would apply 3 safe rewrite(s).
```

## What it will not do

It will not touch your records. Dated plans, specs, ADRs, RFCs and changelogs are excluded by default. On two real repositories, record documents accounted for 175 of 234 and 117 of 121 of all raw findings — left in, they bury everything that matters.

It will not strip your conventions. If your rules say that stated and inferred are never blurred, your evidence tags are load-bearing. If you version your rule sets, the version identifiers are load-bearing. It reads those rules before it scans anything.

It is not a general prose linter. It does not scrub AI writing voice out of freshly generated text, find documentation that has gone stale relative to your code, generate changelogs, reconcile contradictory content, translate, proofread, or clean up code.

## What is in here

`skills/metadiscourse-audit/` is the skill: `SKILL.md` is the workflow your agent follows, and `references/classes.md` holds the full taxonomy — twelve classes, worked examples drawn from four unrelated repositories, the rewrite for each, and the six families of false positive that account for most of what you will discard. `scripts/scan.py` is the scanner. At the repo root, `.claude-plugin/` holds the plugin and marketplace manifests, and `evals/` carries task prompts with planted fixtures plus a trigger eval set for tuning the skill description.

## Licence

MIT.
