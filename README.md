# Docs Repair

Docs Repair is two audits that clean standing documentation — the README, the docs/ folder, the runbook — by finding and removing the text that accumulates in it without anyone choosing it:

- **metadiscourse-audit** removes what *human revision* leaves behind: text whose subject is the document, its author or its reader rather than the thing it documents.
- **ai-slop-audit** removes what *AI sessions* leave behind: generation residue and the machine register.

```diff
- An earlier draft of this doc said the timeout was 30s. It is 10s.
+ The timeout is 10s.
```

```diff
- I've updated the install script to handle Windows paths as well.
+ The install script handles Windows paths.
```

Both audits share one architecture. A dependency-free scanner produces a `file:line` inventory of candidates; the skill triages each against the surrounding paragraph into a verdict — cut, fold, move, verify, or keep — with a concrete rewrite; and a deliberately narrow `--fix` applies only the rewrites whose removal cannot lose a fact. Everything else waits for a human to decide what the surviving fact is.

## Quickstart

In Claude Code:

```
/plugin marketplace add benjaminsky/docs-repair
/plugin install docs-repair@benjaminsky-skills
```

Cloud sessions have no `/plugin` prompt — there, the environment's setup
script does the same job, covered under [Claude Code on the
web](#claude-code-on-the-web).

Then describe the problem in your own words, and ask for the findings list first:

> Audit `docs/` and `README.md` for metadiscourse. Give me the findings list —
> don't edit anything yet.

> Most of `docs/` was written by coding-agent sessions and it shows. De-slop
> it — list first, and check whether the things it documents actually exist.

Every finding comes back as `file:line`, the verbatim text, a class, a verdict,
and the rewrite. Then approve a slice:

> Apply the class 0 findings. Show me the diff for anything you move rather
> than cut.

Class 0 is each audit's objective tier — iteration artifacts and misplaced
caveats on one side, chat residue and phantom links on the other — so the
first slice is the one you will almost always accept; everything below it is
taste and deserves a look before it lands. And point either audit at a **doc
set**, not one file: the corpus-wide passes and the density ranking only mean
anything across a corpus, and they are the outputs that tell you where to
edit next.

No agent, no install — each scanner is a single dependency-free Python file.
From your project's root:

```bash
git clone https://github.com/benjaminsky/docs-repair /tmp/dr
python3 /tmp/dr/skills/metadiscourse-audit/scripts/scan.py docs README.md
python3 /tmp/dr/skills/ai-slop-audit/scripts/scan.py docs README.md
```

Each prints its candidates by `file:line`, and its last lines tell you how
many `--fix` can rewrite mechanically. Other routes — [any agent that reads
AGENTS.md](#any-agent-that-reads-agentsmd), [plain skills with no plugin
machinery](#claude-code), [CI](#no-agent-at-all) — are under
[Installation](#installation).

## Which audit, when

By origin. Revision debris in docs people wrote — "previously X, now Y",
dated status stamps, caveats wedged mid-paragraph — is metadiscourse-audit's
territory. Docs a coding agent generated or heavily edited — chat turns
committed as documentation, completion reports, links to files that were
never created, "comprehensive" on every page — is ai-slop-audit's.

On a corpus with both histories, run both. They compose: a model writes
"it's worth noting" as readily as a person revising, and revision debris
accumulates in generated docs once humans start editing them. A line flagged
by both is one finding, not two.

## How both audits work

Each audit starts by reading your project's own rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, a style guide, whatever you use. Projects encode conventions that *require* text an audit would otherwise strip — evidence tags, versioned rule sets, emoji used as a declared system, a marketing page whose register was chosen. Whatever it finds there is protected for the rest of the run.

Then it separates your records from your standing documents. A document is either the events or a projection of them, never both. A dated plan, spec, ADR or changelog is an event: written once, read as of its date, and its "previously / now" language is its content. A session hand-off note saved under `plans/` with a date in its name is an event too, however it was authored. Those are left alone. A README or a runbook is a projection of those events onto now, and that is what gets audited.

Only then does it scan. Both scanners over-report on purpose — a false positive costs one glance, a miss leaves the artifact in place for another year — so output is candidates, not verdicts, and each skill ships a reference of the false-positive families that account for most discards. Both end with a **density table** (candidates per 100 lines, per file — where to edit first) and a `clean:` line (what a later rewrite must not regress), and each has a corpus-wide pass no single file can show: repeated superlatives for one, repeated sentences for the other.

## What metadiscourse-audit finds

A document arguing with its own history:

```diff
- _Changed in `rules/2026-04-b`: state X was previously inferred from a passed
- date; it now requires a recorded event._
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

A caveat wedged into the sentence it qualifies:

```diff
- The window measures back from the end date, not the start date. The start
- date would be tighter — goods ship at construction start, not eighteen months
- later — but that column is sparsely populated, and an anchor that is usually
- absent produces a mostly blank report. Revisit if a future month fills it in.
+ The window measures back from the end date, not the start date.[^anchor]
```

A heading that argues instead of naming, a section that announces how many
bullets are about to follow, an attitude marker rating your attention instead
of telling you something:

```diff
- ## Format stability — measured, not assumed
+ ## Format stability
```

```diff
- Two priors worth defending explicitly:
+ Two priors:
```

```diff
- Worth a glance while the file is open: are the milestone columns dates?
+ Check that the milestone columns hold dates, not status strings.
```

And the one that only shows up across a whole doc set: four different files each claiming to hold the single most important thing. They cancel. Three become ordinary claims and one keeps the crown.

Three rules shape the verdicts. Caveats are never cut, only moved: a risk or a hedge is content, and the failure is that it interrupts the sentence you came for instead of sitting in a footnote. Cross-references stay while the status claims around them go — `(issue #14)` never rots, and "has not been made" is the part only the tracker knows. And a superlative is information exactly once.

## What ai-slop-audit finds

A chat turn committed as documentation:

```diff
- I've updated the install script to handle Windows paths as well.
+ The install script handles Windows paths.
```

```diff
- Hope this helps! Let me know if you have any questions.
```

A completion report pasted where a description belongs:

```diff
- ## Summary of Changes
-
- The following changes were made in this update: the scheduler was
- refactored to use a worker pool. All 47 tests pass.
+ The scheduler dispatches through a worker pool.
```

A link to a file that was never created — the one fabrication tell with a
fully objective test, so the scanner checks it against the filesystem:

```
docs/setup.md:20  [phantom relative link]
    See [the configuration reference](./configuration.md) for the full option list.
```

The register — inflation that either becomes the number or disappears, and
the vocabulary with a plain word underneath:

```diff
- Relay leverages a robust caching layer for lightning-fast responses.
+ Relay caches hot partitions; p99 read latency is 3 ms.
```

And the manner: prose whose *shape* was chosen for effect, where the effect
is all it delivers — the rule of three with one measured item, fragment
cadence, "Here's the thing:", a rhetorical question its own next sentence
answers, the analogy nobody needed.

```diff
- Here's the thing: Relay is fast, reliable, and effortless to operate.
+ Relay delivers a batch in 3 ms at p99. One operator runs six clusters.
```

No pattern separates a cadence from a person, so this one arrives only from
reading — and it carries the audit's strongest guard, because it is the class
most likely to damage writing that was fine. A chosen voice is a convention
and stays; a human author's style is not a finding; and no document is ever
levelled wholesale, because the verdicts are per sentence.

Emoji-decorated headings, empty scaffolded sections, walls of `**Term**:
description` bullets where a table belongs — and **echoes**: the same
sentence regenerated into three files, because sessions don't read sibling
docs. The scanner catches echoes at two granularities, verbatim sentences
and near-verbatim paragraphs, both deterministically.

And the redundancy no vocabulary betrays: prose that restates what the code
already does. A generated doc narrates the implementation it was written
beside, which is true when written and unowned after — nothing updates it
when the function changes. The test is a hypothetical edit: if someone
changed the code and left the line alone, would the line be wrong? Then the
code owns it.

```diff
- The `parse_row` function takes a row and returns a dict. It loops over the
- configured columns and coerces each value to the column's declared type.
+ A column absent from the header is an error: a silently missing column
+ looked identical to a null in the 2026-02 incident.
```

Comments are held to the same standard — `# increment the retry counter`
above `retries += 1` goes; the comment naming the bug it works around stays.
And the same redundancy at file scale: a **plan** whose work has merged is
spent, and misleads on top of it, because a plan reads as intent and a
finished one gets taken for outstanding work. Delete merged plans, keep
specs — a spec states what the system must do and outlives the code that
implements it.

What no scan can check, the skill does with the code open: generated prose
asserts with equal confidence what it verified and what it assumed, so the
load-bearing claims get checked against the code, and a documented feature
that doesn't exist leads the report — it outranks fifty "seamlessly"s.

## A worked run

The repository ships planted fixtures, so you can see real output before
pointing either audit at your own docs. From the root of your clone:

```bash
export SCAN=$PWD/skills/metadiscourse-audit/scripts/scan.py
export SLOP=$PWD/skills/ai-slop-audit/scripts/scan.py
cd evals/fixtures/repo-a
python3 "$SCAN" docs CLAUDE.md
```

The head of the output is the classes with objective tests:

```
=== class 0a — 5 candidate(s) ===
docs/ingest.md:5  [prior-state reference]
    _Changed in `ingest/2026-04-b`: the delimiter was previously assumed to be a
docs/sources.md:8  [prior-state reference]
    An earlier version of this section said six of nine feeds needed OCR. That was

=== class 0c — 1 candidate(s) ===
docs/ingest.md:21  [dated status stamp]
    **Status 2026-05-02:** the batch job has not been made idempotent (issue #14).
```

The tail is the part that only works corpus-wide — collisions, density, and
the clean list:

```
=== density — candidates per 100 lines ===
    63.0  docs/ingest.md  (17 in 27 lines)
    38.5  docs/sources.md  (5 in 13 lines)

clean: CLAUDE.md

22 candidate(s) across 3 file(s).
2 of these are mechanical — --fix applies them, --fix --dry-run shows the rewrites first.
Skipped 1 point-in-time record(s) — dated plans, specs, ADRs, changelogs.
```

Density says where to start editing. `clean:` is what a later rewrite must
not regress. The skipped record is the ADR, left alone by design. `--fix
--dry-run` shows the mechanical subset before anything is applied.

`repo-c` is the same arrangement for the slop scanner — chat residue, a
completion report, two phantom links, an empty section and a cross-file echo,
with a clean `CLAUDE.md` beside them:

```bash
cd ../repo-c
python3 "$SLOP" docs CLAUDE.md
```

## Installation

### Claude Code

The two `/plugin` commands in the [Quickstart](#quickstart) are the whole install. They give you `/docs-repair:metadiscourse-audit` and `/docs-repair:ai-slop-audit`, and Claude will reach for them on its own when you describe the problem. Update later with `/plugin marketplace update benjaminsky-skills`.

If you would rather keep them as plain skills with no plugin machinery, clone the repository and run the installer:

```bash
git clone https://github.com/benjaminsky/docs-repair
cd docs-repair && ./install.sh
```

That installs every skill to `~/.claude/skills/<name>` (pass `--skill metadiscourse-audit` for just one). Pass `--project` to install into the current repo instead, `--link` to symlink so `git pull` updates them in place, or `--uninstall` to remove them. It will not overwrite a directory it did not create.

### Claude Code on the web

`/plugin` is a terminal command, so cloud sessions cannot install anything interactively, and `~/.claude` does not carry over from your machine. Install from the environment's setup script instead. One environment covers every cloud session you start from it — the web, `claude --cloud`, the mobile and desktop apps, and routines — across all your repositories.

Open the environment settings at [claude.ai/code](https://claude.ai/code) and put this in **Setup script**:

```bash
#!/bin/bash
command -v claude >/dev/null || export PATH="/opt/claude-code/bin:$PATH"
claude plugin marketplace add benjaminsky/docs-repair || true
claude plugin install docs-repair@benjaminsky-skills || true
```

The `PATH` fallback is there because setup scripts run as root under a non-login shell, where `claude` is not otherwise found. It resolves through `command -v` first, so it does nothing on an image that already puts `claude` on the path, and the directory it falls back to carries no version in its name. The `|| true` matters more: a setup script that exits non-zero stops the session from starting at all.

A setup script is skipped whenever a cached environment exists, so a new version arrives when the cache rebuilds rather than on your next session.

To scope the skills to one repository rather than every cloud session, commit the same two keys to that repository's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "benjaminsky-skills": {
      "source": { "source": "github", "repo": "benjaminsky/docs-repair" }
    }
  },
  "enabledPlugins": { "docs-repair@benjaminsky-skills": true }
}
```

### Any agent that reads AGENTS.md

`AGENTS.md` is the portable route — Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf and Zed all read it. Clone the repository somewhere your agent can see, then point at the skills from your `AGENTS.md`:

```bash
git clone https://github.com/benjaminsky/docs-repair .agent/docs-repair
```

```markdown
## Documentation

When asked to clean up, tighten or de-cruft docs, follow
`.agent/docs-repair/skills/metadiscourse-audit/SKILL.md`.
When asked to strip AI slop or AI voice from docs, follow
`.agent/docs-repair/skills/ai-slop-audit/SKILL.md`.
```

Each `SKILL.md` is plain Markdown with YAML frontmatter and no tool-specific syntax, so nothing needs translating. The `references/` files are loaded on demand, only when a finding is ambiguous.

Cursor's own `.cursor/rules/*.mdc` format expects MDC files rather than a skill directory, so use the `AGENTS.md` route there too — Cursor reads it natively.

### No agent at all

The scanners are plain command-line tools. Python 3 standard library, no dependencies, no install step:

```bash
git clone https://github.com/benjaminsky/docs-repair ~/src/docs-repair
export MDA=~/src/docs-repair/skills/metadiscourse-audit/scripts/scan.py
export ASA=~/src/docs-repair/skills/ai-slop-audit/scripts/scan.py
```

Run them from the root of the project you are auditing. The corpus arguments
(`docs`, `README.md`) resolve against your working directory, not against the
clone — which is why the scripts are addressed by absolute path and the corpus
by relative one:

```bash
cd ~/src/my-project
python3 "$MDA" docs README.md
python3 "$ASA" docs README.md
```

Each reports candidates grouped by class. A human decides what to do with
them. The flags are shared:

```bash
python3 "$MDA" docs --class 0      # the objective classes only
python3 "$ASA" docs --json         # machine-readable
python3 "$MDA" docs src --code     # also scan code comments
python3 "$ASA" docs --check        # exit 1 on any finding
python3 "$MDA" docs --fix --dry-run
```

Code comments collect the same debris — `# previously five` beside a
constant, `# I've bumped this to handle the new load` above the bump.
`--code` extends a scan to source-file comments; a source file named on the
command line needs no flag. TODO and FIXME lines are left alone — a TODO is
a tracker item living in code, and its "not yet" is its content.

For CI, gate on the objective classes alone:

```bash
python3 "$MDA" docs --class 0 --check
python3 "$ASA" docs --class 0 --check
```

`--fix` applies only the rewrites whose removal cannot lose a fact: stripping a "worth …" wrapper, deleting a pleasantry line, removing emoji from a heading. Expect single digits across a large corpus, often zero. It never rewrites a source file — comment extraction is heuristic, so those findings stay in human hands. Everything else needs someone to decide what the surviving fact is, and keeping `--fix` that narrow is what makes it safe to run unattended.

## What they will not do

They will not touch your records. Dated plans, specs, ADRs, RFCs and changelogs are excluded by default — an exclusion from scanning, not a verdict that they should be kept; the one record the slop audit will propose deleting is a plan whose work has already merged. On two real repositories, record documents accounted for 175 of 234 and 117 of 121 of all raw findings — left in, they bury everything that matters.

They will not strip your conventions. If your rules say that stated and inferred are never blurred, your evidence tags are load-bearing. If you version your rule sets, the version identifiers are load-bearing. If your emoji are a declared system, they stay. Each audit reads those rules before it scans anything.

They are not general prose linters, and neither is a humanizer: pasting a draft into chat to "make it sound human" is a rewrite job, not an audit. They do not find documentation that has gone stale relative to your code, generate changelogs, reconcile contradictory content, translate, proofread, or clean up code itself — comments are in scope, the code around them is not. And nothing here counts punctuation: em dashes are not evidence of anything.

## What is in here

`skills/metadiscourse-audit/` and `skills/ai-slop-audit/` are the skills: each `SKILL.md` is the workflow your agent follows, each `references/` file holds the full taxonomy with worked examples and the false-positive families, and each `scripts/scan.py` is the scanner, with its tests beside it. At the repo root, `.claude-plugin/` holds the plugin and marketplace manifests, and `evals/` carries task prompts with planted fixtures plus trigger-eval sets for tuning the skill descriptions.

## Licence

MIT.
