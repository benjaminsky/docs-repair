# Docs Repair

Docs Repair is three audits over standing documentation — the README, the docs/ folder, the runbook. Two of them remove the text that accumulates in it without anyone choosing it; the third asks whether what is left is true:

- **metadiscourse-audit** removes what *human revision* leaves behind: text whose subject is the document, its author or its reader rather than the thing it documents.
- **ai-slop-audit** removes what *AI sessions* leave behind: generation residue and the machine register.
- **lie-detector** samples the factual claims and tries to disprove them against the code, by a lottery anyone can recompute.

```diff
- An earlier draft of this doc said the timeout was 30s. It is 10s.
+ The timeout is 10s.
```

```diff
- I've updated the install script to handle Windows paths as well.
+ The install script handles Windows paths.
```

```diff
- The `--retries` flag defaults to 5.     ← src/relay.py:5  MAX_RETRIES = 3
+ The `--retries` flag defaults to 3.
```

The two cleanup audits share one architecture. A dependency-free scanner produces a `file:line` inventory of candidates; the skill triages each against the surrounding paragraph into a verdict — cut, fold, move, verify, or keep — with a concrete rewrite; and a deliberately narrow `--fix` applies only the rewrites whose removal cannot lose a fact. Everything else waits for a human to decide what the surviving fact is.

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

> I don't trust `docs/` any more. Fact-check twenty claims against the code,
> and pick them so I can prove to my team you didn't cherry-pick.

Every finding comes back as `file:line`, the verbatim text, a class, a verdict,
and the rewrite. Then approve a slice:

> Apply the class 0 findings. Show me the diff for anything you move rather
> than cut.

(lie-detector works differently — it draws a sample rather than listing findings; [what it does](#what-lie-detector-finds) is below.)

Class 0 is each cleanup audit's objective tier — iteration artifacts and misplaced
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
python3 /tmp/dr/skills/lie-detector/scripts/scan.py docs README.md -n 20
```

Each prints its candidates by `file:line`, and its last lines tell you how
many `--fix` can rewrite mechanically. Other routes — [any agent that reads
AGENTS.md](#any-agent-that-reads-agentsmd), [plain skills with no plugin
machinery](#claude-code), [CI](#no-agent-at-all) — are under
[Installation](#installation).

## Which audit, when

By the question. "Is this text doing any work?" is the cleanup audits;
"is this sentence true?" is lie-detector, and it is the one to run when
someone stops trusting a doc set rather than merely finding it tiresome.

Between the two cleanup audits, by origin. Revision debris in docs people wrote — "previously X, now Y",
dated status stamps, caveats wedged mid-paragraph — is metadiscourse-audit's
territory. Docs a coding agent generated or heavily edited — chat turns
committed as documentation, completion reports, links to files that were
never created, "comprehensive" on every page — is ai-slop-audit's.

Run lie-detector last, after the register is gone: a cleanup audit will
happily strip the wrapper off a false claim — "leverages a robust 30-second
timeout" becomes "the timeout is 30 seconds", tidier and still wrong — and a
fact-check over cleaned text produces findings about facts rather than
adjectives.

On a corpus with both histories, run both cleanup audits. They compose: a model writes
"it's worth noting" as readily as a person revising, and revision debris
accumulates in generated docs once humans start editing them. A line flagged
by both is one finding, not two.

## How the cleanup audits work

Each of the two starts by reading your project's own rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, a style guide, whatever you use. Projects encode conventions that *require* text an audit would otherwise strip — evidence tags, versioned rule sets, emoji used as a declared system, a marketing page whose register was chosen. Whatever it finds there is protected for the rest of the run.

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

Emoji-decorated headings, empty scaffolded sections, walls of `**Term**:
description` bullets where a table belongs — and **echoes**: the same
sentence regenerated into three files, because sessions don't read sibling
docs. The scanner catches echoes at two granularities, verbatim sentences
and near-verbatim paragraphs, both deterministically.

What no scan can check, the skill does with the code open: generated prose
asserts with equal confidence what it verified and what it assumed, so the
load-bearing claims get checked against the code, and a documented feature
that doesn't exist leads the report — it outranks fifty "seamlessly"s.

## What lie-detector finds

Claims the tree contradicts — and it finds them without letting anyone,
including itself, choose which claims get checked.

```
docs/relay.md:16  [A numeric or default]  id 54df497d89ca
    Relay retries a failed flush 5 times before parking the batch.
    → False. src/relay.py:5 — MAX_RETRIES = 3
```

The scanner extracts the **checkable** claims from a corpus — defaults and
limits, flags and paths and env vars, guarantees like "never" and "every",
version and platform requirements, behaviour on error — and then draws n of
them by lottery. Each claim gets a ticket, `sha256(seed || claim id)`; the
lowest tickets win. Publish the seed and the corpus digest, and anyone can
rerun the command and get your sample back:

```bash
python3 "$LIE" docs README.md -n 20 --seed drand:4210000 --json > audit.json
python3 "$LIE" docs README.md --verify audit.json      # DRAW REPRODUCES
```

That gives two properties worth keeping apart, because most "random samples"
only have the first. The draw is **verifiable** — anyone can recompute it.
It is **unbiasable** only if the seed came from outside: a drand round, a
beacon pulse, a string the person who asked for the audit picked. The
default seed is the corpus's own git HEAD, which the drawer could re-roll by
committing again, and the output says so in as many words rather than
implying a rigour it does not have.

The skill body does the part no scanner can. For each drawn claim it writes
the disproof test *before* opening the evidence — read the code first and
you will find a way to read the sentence as true — and then returns one of
four verdicts: **False** (with the refuting `file:line` quoted), **True**
(with the confirming one), **Unsupported** when nothing in the tree settles
it, and **Unfalsifiable** when the sentence asserts nothing checkable. That
last one is replaced from the **queue**, the next claim in draw order, never
by one the auditor liked better — which is the only reason the sample still
means anything after the swaps.

Absence of evidence is Unsupported, never False: the worst thing this audit
can do is call a claim a lie because a grep missed it. And a guarantee no
test would catch breaking gets reported even when it holds — it is not a lie today, it is a claim whose truth is
accidental.

Then it reports a rate rather than a verdict:

```bash
python3 "$LIE" --interval 2 18
2 false in 18 drawn.
Corpus false-claim rate: 11% observed, 95% interval 3%-32%.
```

Nothing disproved in twenty draws is consistent with one claim in six being
wrong. "The docs are accurate" is not a sentence a sample can support, and
this audit will not write it.

## A worked run

The repository ships planted fixtures, so you can see real output before
pointing either audit at your own docs. From the root of your clone:

```bash
export SCAN=$PWD/skills/metadiscourse-audit/scripts/scan.py
export SLOP=$PWD/skills/ai-slop-audit/scripts/scan.py
export LIE=$PWD/skills/lie-detector/scripts/scan.py
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

`repo-d` is planted for the lie detector, and its plant is a disagreement
rather than a mess: the docs state a 30-second timeout, five retries and a
report written on every failure, while `src/relay.py` holds `10`, `3` and a
nightly job. A draw with a fixed seed reproduces anywhere:

```bash
cd ../repo-d
python3 "$LIE" docs -n 4 --seed drand:4210000
```

Every line the draw prints is enough to recompute it — the seed, the corpus
digest, the population size and each claim's id — and `--json` writes that
as a manifest for `--verify`.

`repo-c` is the same arrangement for the slop scanner — chat residue, a
completion report, two phantom links, an empty section and a cross-file echo,
with a clean `CLAUDE.md` beside them:

```bash
cd ../repo-c
python3 "$SLOP" docs CLAUDE.md
```

## Installation

### Claude Code

The two `/plugin` commands in the [Quickstart](#quickstart) are the whole install. They give you `/docs-repair:metadiscourse-audit`, `/docs-repair:ai-slop-audit` and `/docs-repair:lie-detector`, and Claude will reach for them on its own when you describe the problem. Update later with `/plugin marketplace update benjaminsky-skills`.

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
When asked whether the docs are true — fact-check, spot-check, accuracy
audit — follow `.agent/docs-repair/skills/lie-detector/SKILL.md`.
```

Each `SKILL.md` is plain Markdown with YAML frontmatter and no tool-specific syntax, so nothing needs translating. The `references/` files are loaded on demand, only when a finding is ambiguous.

Cursor's own `.cursor/rules/*.mdc` format expects MDC files rather than a skill directory, so use the `AGENTS.md` route there too — Cursor reads it natively.

### No agent at all

The scanners are plain command-line tools. Python 3 standard library, no dependencies, no install step:

```bash
git clone https://github.com/benjaminsky/docs-repair ~/src/docs-repair
export MDA=~/src/docs-repair/skills/metadiscourse-audit/scripts/scan.py
export ASA=~/src/docs-repair/skills/ai-slop-audit/scripts/scan.py
export LIE=~/src/docs-repair/skills/lie-detector/scripts/scan.py
```

Run them from the root of the project you are auditing. The corpus arguments
(`docs`, `README.md`) resolve against your working directory, not against the
clone — which is why the scripts are addressed by absolute path and the corpus
by relative one:

```bash
cd ~/src/my-project
python3 "$MDA" docs README.md
python3 "$ASA" docs README.md
python3 "$LIE" docs README.md -n 20
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

The lie detector's flags are about the draw rather than about classes,
because its output is a sample and not a finding list:

```bash
python3 "$LIE" docs -n 20 --seed drand:4210000   # a seed nobody controls
python3 "$LIE" docs --pool                       # the population, undrawn
python3 "$LIE" docs --class A                    # stratify: numbers only
python3 "$LIE" docs --json > audit.json          # the manifest, to publish
python3 "$LIE" docs --verify audit.json          # exit 1 if it does not reproduce
python3 "$LIE" --interval 2 18                   # what the result implies
```

For CI, gate on the objective classes alone:

```bash
python3 "$MDA" docs --class 0 --check
python3 "$ASA" docs --class 0 --check
```

`--fix` applies only the rewrites whose removal cannot lose a fact: stripping a "worth …" wrapper, deleting a pleasantry line, removing emoji from a heading. Expect single digits across a large corpus, often zero. It never rewrites a source file — comment extraction is heuristic, so those findings stay in human hands. Everything else needs someone to decide what the surviving fact is, and keeping `--fix` that narrow is what makes it safe to run unattended.

## What they will not do

The lie detector will not call a claim false because it could not find the
evidence — that verdict is Unsupported, and the finding is that the search
came back empty. It will not tell you a doc set is accurate, either: a
sample bounds a false-claim rate, and twenty clean draws leave room for one
claim in six being wrong.

They will not touch your records. Dated plans, specs, ADRs, RFCs and changelogs are excluded by default. On two real repositories, record documents accounted for 175 of 234 and 117 of 121 of all raw findings — left in, they bury everything that matters.

They will not strip your conventions. If your rules say that stated and inferred are never blurred, your evidence tags are load-bearing. If you version your rule sets, the version identifiers are load-bearing. If your emoji are a declared system, they stay. Each audit reads those rules before it scans anything.

They are not general prose linters, and neither is a humanizer: pasting a draft into chat to "make it sound human" is a rewrite job, not an audit. Staleness relative to your code is lie-detector's question and nobody else's here — the two cleanup audits read prose, not programs, and will not notice that a true-sounding sentence stopped being true. They do not generate changelogs, reconcile contradictory content, translate, proofread, or clean up code itself — comments are in scope, the code around them is not. And nothing here counts punctuation: em dashes are not evidence of anything.

## What is in here

`skills/metadiscourse-audit/`, `skills/ai-slop-audit/` and `skills/lie-detector/` are the skills: each `SKILL.md` is the workflow your agent follows, each `references/` file holds the full taxonomy with worked examples and the false-positive families, and each `scripts/scan.py` is the scanner, with its tests beside it. At the repo root, `.claude-plugin/` holds the plugin and marketplace manifests, and `evals/` carries task prompts with planted fixtures plus trigger-eval sets for tuning the skill descriptions — `repo-a` and `repo-b` planted for metadiscourse-audit, `repo-c` for ai-slop-audit, `repo-d` for lie-detector.

## Licence

MIT.
