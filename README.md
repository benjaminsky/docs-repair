# Docs Repair

Docs Repair is three audits over standing documentation — the README, the docs/ folder, the runbook. Two of them remove the text that accumulates in it without anyone choosing it; the third asks whether what is left is true:

- **metadiscourse-audit** removes what *human revision* leaves behind: text whose subject is the document, its author or its reader rather than the thing it documents.
- **ai-slop-audit** removes what *AI sessions* leave behind: generation residue and the machine register.
- **lie-detector** verifies the factual claims against the code and keeps a ledger of what settled each one, so a doc set gets a coverage number and a CI gate.

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

The two cleanup audits share one architecture. A dependency-free scanner produces a `file:line` inventory of candidates; the skill triages each against the surrounding paragraph into a verdict — cut, fold, move, verify, or keep — with a concrete rewrite; and a deliberately narrow `--fix` applies only the rewrites whose removal cannot lose a fact.[^c16ef9f88] Everything else waits for a human to decide what the surviving fact is.

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

> Our docs keep drifting from the code. Enrol every claim in `docs/` in a
> ledger, wire the gate into CI, and start working the backlog.[^ce6220349]

Every finding comes back as `file:line`, the verbatim text, a class, a verdict,
and the rewrite.[^ce63331b2] Then approve a slice:

> Apply the class 0 findings. Show me the diff for anything you move rather
> than cut.

(lie-detector works differently — it draws a sample rather than listing findings; [what it does](#what-lie-detector-finds) is below.)

Class 0 is each cleanup audit's objective tier — iteration artifacts and misplaced
caveats on one side, chat residue and phantom links on the other — so the
first slice is the one you will almost always accept; everything below it is
taste and deserves a look before it lands.[^c186f5991] And point either audit at a **doc
set**, not one file: the corpus-wide passes and the density ranking only mean
anything across a corpus, and they are the outputs that tell you where to
edit next.[^cf9a26693]

No agent, no install — each scanner is a single dependency-free Python file.
From your project's root:

```bash
git clone https://github.com/benjaminsky/docs-repair /tmp/dr
python3 /tmp/dr/skills/metadiscourse-audit/scripts/scan.py docs README.md
python3 /tmp/dr/skills/ai-slop-audit/scripts/scan.py docs README.md
python3 /tmp/dr/skills/lie-detector/scripts/ledger.py init docs README.md
```

The two cleanup scanners print candidates by `file:line`, ending with how
many `--fix` can rewrite mechanically; `ledger.py init` enrols the claims it
finds and prints the backlog, with no `--fix` to offer.[^ca527b649] Other routes — [any agent that reads
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
never created, "comprehensive" on every page — is ai-slop-audit's.[^cf12d8ddc]

Run lie-detector last, after the register is gone: a cleanup audit will
happily strip the wrapper off a false claim — "leverages a robust 30-second
timeout" becomes "the timeout is 30 seconds", tidier and still wrong — and a
fact-check over cleaned text produces findings about facts rather than
adjectives.[^c30dba78c]

On a corpus with both histories, run both cleanup audits. They compose: a model writes
"it's worth noting" as readily as a person revising, and revision debris
accumulates in generated docs once humans start editing them. A line flagged
by both is one finding, not two.

## How the cleanup audits work

Each of the two starts by reading your project's own rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, a style guide, whatever you use.[^cee7360e0] Projects encode conventions that *require* text an audit would otherwise strip — evidence tags, versioned rule sets, emoji used as a declared system, a marketing page whose register was chosen.[^c7c88fab6] Whatever it finds there is protected for the rest of the run.

Then it separates your records from your standing documents. A document is either the events or a projection of them, never both.[^cf34631cf] A dated plan, spec, ADR or changelog is an event: written once, read as of its date, and its "previously / now" language is its content. A session hand-off note saved under `plans/` with a date in its name is an event too, however it was authored. Those are left alone. A README or a runbook is a projection of those events onto now, and that is what gets audited.

Only then does it scan.[^ccc17fc75] Both scanners over-report on purpose — a false positive costs one glance, a miss leaves the artifact in place for another year — so output is candidates, not verdicts, and each skill ships a reference of the false-positive families that account for most discards. Both end with a **density table** (candidates per 100 lines, per file — where to edit first) and a `clean:` line (what a later rewrite must not regress), and each has a corpus-wide pass no single file can show: repeated superlatives for one, repeated sentences for the other.[^c3d6e92a3]

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

And the one that only shows up across a whole doc set: four different files each claiming to hold the single most important thing.[^c5843d575] They cancel. Three become ordinary claims and one keeps the crown.

Three rules shape the verdicts. Caveats are never cut, only moved: a risk or a hedge is content, and the failure is that it interrupts the sentence you came for instead of sitting in a footnote.[^c2b89925f] Cross-references stay while the status claims around them go — `(issue #14)` never rots, and "has not been made" is the part only the tracker knows.[^cc3ed1490] And a superlative is information exactly once.

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
fully objective test, so the scanner checks it against the filesystem:[^c2b4d34e1]

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
that doesn't exist leads the report — it outranks fifty "seamlessly"s.[^c49ec7768]

## What lie-detector finds

Claims the tree contradicts:

```
docs/relay.md:16  refuted
    "Relay retries a failed flush 5 times before parking the batch."
    → src/relay.py:5 — MAX_RETRIES = 3
```

It works from a **ledger** checked into your repository — a sidecar beside
each document (`README.claims.toml` next to `README.md`), one entry per
factual claim, carrying the verdict and the `file:line` evidence that
settled it:

```bash
LD=skills/lie-detector/scripts/ledger.py
python3 "$LD" init docs README.md   # enrol every claim, unverified
python3 "$LD" check --backlog       # the next batch, grouped by evidence
python3 "$LD" record verdicts.json  # write verdicts back, with citations
python3 "$LD" check                 # the gate: 0 clean, 1 blocking
```

**Claims can carry their own name.** `init --anchor` writes each claim's id
into the sentence as a markdown footnote, and the block at the end of the
document records what settled it:[^c335ba416]

```markdown
The `--batch-size` flag defaults to 500 events per flush.[^c4e233156]

[^c4e233156]: supported · 2026-09-01 · [src/relay.py:3](src/relay.py#L3)
```

Anchored claims survive rewriting: reword the sentence however you like and
the verdict follows the marker, where a derived id would have lost it. That
matters more than it sounds — in a real corpus about a third of claims name
no identifier at all, and those are the ones a rewrite orphans. The footnotes
are provenance rather than staging, so both cleanup audits protect them
rather than stripping them.

**Day one is green.** `init` grandfathers the existing backlog as exempt and
marks nothing supported, so adoption costs one command and one commit — the
same move as `cargo vet init`'s exemptions and ESLint's bulk suppressions.[^c2a3feb3c]
From that moment the gate enforces on anything *new*: a claim you add, or one
you edit, needs a verdict before the build passes.[^ccf128b0d]

**Nothing is maintained by hand.** Every run re-derives the claim set from
the documents and diffs it against the ledger, so a doc edit cannot escape
unnoticed — it is new, stale, or an orphan.[^c4f26fc9b] Forgetting is not a failure mode.

**Only what moved is re-verified**, which is what makes checking every claim
affordable.[^c6a44d483] Each verdict is anchored to the claim's *skeleton* — its numbers,
units, identifiers and quantifiers — and to a hash of the evidence it cites.
Reword a sentence and the verdict holds; change 500 to 100, or "never" to
"rarely", or the constant the claim cites, and that one entry goes stale:[^c11aa7726]

```
$ python3 "$LD" check
FAIL  docs/relay.md:13  stale — evidence moved: src/relay.py:3
ok    44 supported

1 blocking, 0 advisory. Coverage 95% (45/47 verified).
```

**`record` enforces what each verdict owes.** There are four — supported,
refuted, unsupported, unverifiable — and the rules are refusals: a
supported verdict must quote evidence that is really at the line it cites, a
refuted one must carry the correction, an unsupported one must record what
was searched.[^c987a2e46] Absence of evidence is `unsupported`, never `refuted`.[^cc76a8cdb] A ledger
of rubber-stamped verdicts is worse than none, because it launders assumption
as evidence.[^cb29d02a7]

**It offers to wire itself in.** If nothing in `AGENTS.md` or `CLAUDE.md`
mentions the ledger, `init` prints the block that tells future sessions to
verify their own claims — and prints it rather than writing it, because the
file that governs how every agent behaves in your repo is not a side effect.[^c4aec42eb]

For a repository you do not own, there is a second, stateless mode: a
reproducible random sample, drawn by a lottery anyone can recompute from a
published seed, reported as a rate with a confidence interval.

## A worked run

The repository ships planted fixtures, so you can see real output before
pointing either audit at your own docs. From the root of your clone:

```bash
export SCAN=$PWD/skills/metadiscourse-audit/scripts/scan.py
export SLOP=$PWD/skills/ai-slop-audit/scripts/scan.py
export LIE=$PWD/skills/lie-detector/scripts/scan.py
export LEDGER=$PWD/skills/lie-detector/scripts/ledger.py
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
the clean list:[^cac37f727]

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
--dry-run` shows the mechanical subset before anything is applied.[^c9553343e]

`repo-d` is planted for the lie detector, and its plant is a disagreement
rather than a mess: the docs state a 30-second timeout, five retries and a
report written on every failure, while `src/relay.py` holds `10`, `3` and a
nightly job.[^ca8fe8ee5]

```bash
cd ../repo-d
python3 "$LEDGER" init docs
python3 "$LEDGER" check --backlog --limit 4
```

`init` enrols twelve claims and finds candidate evidence for the ones naming
a flag or a path; `--backlog` hands back the four that `src/relay.py`
settles, so one file answers all of them.

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

That installs every skill to `~/.claude/skills/<name>` (pass `--skill metadiscourse-audit` for just one).[^cd8bfb1d7] Pass `--project` to install into the current repo instead, `--link` to symlink so `git pull` updates them in place, or `--uninstall` to remove them.[^cbd28355f] It will not overwrite a directory it did not create.

### Claude Code on the web

`/plugin` is a terminal command, so cloud sessions cannot install anything interactively, and `~/.claude` does not carry over from your machine.[^cf1a9344c] Install from the environment's setup script instead. One environment covers every cloud session you start from it — the web, `claude --cloud`, the mobile and desktop apps, and routines — across all your repositories.[^c0b55772c]

Open the environment settings at [claude.ai/code](https://claude.ai/code) and put this in **Setup script**:[^c29961a02]

```bash
#!/bin/bash
command -v claude >/dev/null || export PATH="/opt/claude-code/bin:$PATH"
claude plugin marketplace add benjaminsky/docs-repair || true
claude plugin install docs-repair@benjaminsky-skills || true
```

The `PATH` fallback is there because setup scripts run as root under a non-login shell, where `claude` is not otherwise found.[^cde054205] It resolves through `command -v` first, so it does nothing on an image that already puts `claude` on the path, and the directory it falls back to carries no version in its name.[^cfaec2646] The `|| true` matters more: a setup script that exits non-zero stops the session from starting at all.[^c335cb9e0]

A setup script is skipped whenever a cached environment exists, so a new version arrives when the cache rebuilds rather than on your next session.

To scope the skills to one repository rather than every cloud session, commit the same two keys to that repository's `.claude/settings.json`:[^cde95968c]

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

`AGENTS.md` is the portable route — Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf and Zed all read it.[^c9e80e15a] Clone the repository somewhere your agent can see, then point at the skills from your `AGENTS.md`:[^cb455d13b]

```bash
git clone https://github.com/benjaminsky/docs-repair .agent/docs-repair
```

```markdown
## Documentation

When asked to clean up, tighten or de-cruft docs, follow
`.agent/docs-repair/skills/metadiscourse-audit/SKILL.md`.
When asked to strip AI slop or AI voice from docs, follow
`.agent/docs-repair/skills/ai-slop-audit/SKILL.md`.
When asked whether the docs are true, or to keep them true — fact-check,
accuracy audit, doc drift in CI — follow
`.agent/docs-repair/skills/lie-detector/SKILL.md`.
```

Each `SKILL.md` is plain Markdown with YAML frontmatter and no tool-specific syntax, so nothing needs translating.[^c6d8b08a7] The `references/` files are loaded on demand, only when a finding is ambiguous.[^cbcd0eddc]

Cursor's own `.cursor/rules/*.mdc` format expects MDC files rather than a skill directory, so use the `AGENTS.md` route there too — Cursor reads it natively.[^cbc7e2aff]

### No agent at all

The scanners are plain command-line tools. Python 3 standard library, no dependencies, no install step:[^c31255dad]

```bash
git clone https://github.com/benjaminsky/docs-repair ~/src/docs-repair
export MDA=~/src/docs-repair/skills/metadiscourse-audit/scripts/scan.py
export ASA=~/src/docs-repair/skills/ai-slop-audit/scripts/scan.py
export LIE=~/src/docs-repair/skills/lie-detector/scripts/scan.py
```

Run them from the root of the project you are auditing. The corpus arguments
(`docs`, `README.md`) resolve against your working directory, not against the
clone — which is why the scripts are addressed by absolute path and the corpus
by relative one:[^cffe46a3e]

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
command line needs no flag.[^c7976eb21] TODO and FIXME lines are left alone — a TODO is
a tracker item living in code, and its "not yet" is its content.

The lie detector has two commands rather than flags, because its output is
state rather than a finding list:

```bash
python3 "$LEDGER" init docs README.md    # enrol; day one is green
python3 "$LEDGER" check                  # the gate; --strict, --prune
python3 "$LEDGER" check --backlog        # the next batch, by evidence file
python3 "$LEDGER" record verdicts.json   # citations required
python3 "$LEDGER" show docs/relay.md:16  # provenance for one sentence
python3 "$LEDGER" init --print-hook      # run check after every doc edit

python3 "$LIE" docs -n 20 --seed drand:4210000   # sampling: a repo you do not own
python3 "$LIE" --interval 2 18                   # what that sample implies
```

For CI, gate on the objective classes alone:

```bash
python3 "$MDA" docs --class 0 --check
python3 "$ASA" docs --class 0 --check
python3 "$LEDGER" check
```

`--fix` applies only the rewrites whose removal cannot lose a fact: stripping a "worth …" wrapper, deleting a pleasantry line, removing emoji from a heading.[^cdeece67d] Expect single digits across a large corpus, often zero. It never rewrites a source file — comment extraction is heuristic, so those findings stay in human hands.[^cf993e82a] Everything else needs someone to decide what the surviving fact is, and keeping `--fix` that narrow is what makes it safe to run unattended.[^c14f6b361]

## What they will not do

The lie detector will not call a claim false because it could not find the
evidence — that verdict is Unsupported, and the finding is that the search
came back empty. It will not tell you a doc set is accurate either: full
coverage says every claim was examined, not that the examining was
infallible.[^c64e9c1cc]

They will not touch your records. Dated plans, specs, ADRs, RFCs and changelogs are excluded by default — an exclusion from scanning, not a verdict that they should be kept; the one record the slop audit will propose deleting is a plan whose work has already merged.[^c0dad975b] On two real repositories, record documents accounted for 175 of 234 and 117 of 121 of all raw findings — left in, they bury everything that matters.

They will not strip your conventions. If your rules say that stated and inferred are never blurred, your evidence tags are load-bearing.[^c21d9dec7] If you version your rule sets, the version identifiers are load-bearing. If your emoji are a declared system, they stay. Each audit reads those rules before it scans anything.

They are not general prose linters, and neither is a humanizer: pasting a draft into chat to "make it sound human" is a rewrite job, not an audit. Staleness relative to your code is lie-detector's question and nobody else's here — the two cleanup audits read prose, not programs, and will not notice that a true-sounding sentence stopped being true. They do not generate changelogs, reconcile contradictory content, translate, proofread, or clean up code itself — comments are in scope, the code around them is not. And nothing here counts punctuation: em dashes are not evidence of anything.

## What is in here

`skills/metadiscourse-audit/`, `skills/ai-slop-audit/` and `skills/lie-detector/` are the skills: each `SKILL.md` is the workflow your agent follows, each `references/` file holds the full taxonomy with worked examples and the false-positive families, and each `scripts/scan.py` is the scanner, with its tests beside it. lie-detector carries a second script, `scripts/ledger.py`, which manages the claim ledger — extraction, hashing, staleness, the backlog and the gate are mechanical and live there; reaching a verdict is the skill's job and does not.[^c33caa1b1] At the repo root, `.claude-plugin/` holds the plugin and marketplace manifests, and `evals/` carries task prompts with planted fixtures plus trigger-eval sets for tuning the skill descriptions — `repo-a` and `repo-b` planted for metadiscourse-audit, `repo-c` for ai-slop-audit, `repo-d` for lie-detector.

## Licence

MIT.

<!-- claim anchors: written by lie-detector -->

[^c16ef9f88]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:903](skills/metadiscourse-audit/scripts/scan.py#L903)
[^ce6220349]: unverifiable · 2026-09-02
[^ce63331b2]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:903](skills/metadiscourse-audit/scripts/scan.py#L903)
[^c186f5991]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:38](skills/ai-slop-audit/SKILL.md#L38)
[^cf9a26693]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:359](skills/ai-slop-audit/SKILL.md#L359)
[^ca527b649]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:1028](skills/lie-detector/scripts/ledger.py#L1028)
[^cf12d8ddc]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:144](skills/ai-slop-audit/SKILL.md#L144)
[^c30dba78c]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:359](skills/ai-slop-audit/SKILL.md#L359)
[^c7c88fab6]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:65](skills/ai-slop-audit/SKILL.md#L65)
[^cee7360e0]: supported · 2026-09-02 · [skills/metadiscourse-audit/SKILL.md:47](skills/metadiscourse-audit/SKILL.md#L47)
[^cf34631cf]: supported · 2026-09-02 · [skills/metadiscourse-audit/SKILL.md:103](skills/metadiscourse-audit/SKILL.md#L103)
[^c3d6e92a3]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:913](skills/metadiscourse-audit/scripts/scan.py#L913)
[^ccc17fc75]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:65](skills/ai-slop-audit/SKILL.md#L65)
[^c5843d575]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:666](skills/metadiscourse-audit/scripts/scan.py#L666)
[^c2b89925f]: supported · 2026-09-02 · [skills/metadiscourse-audit/SKILL.md:268](skills/metadiscourse-audit/SKILL.md#L268)
[^cc3ed1490]: supported · 2026-09-02 · [skills/metadiscourse-audit/SKILL.md:230](skills/metadiscourse-audit/SKILL.md#L230)
[^c2b4d34e1]: supported · 2026-09-02 · [skills/ai-slop-audit/scripts/scan.py:474](skills/ai-slop-audit/scripts/scan.py#L474)
[^c49ec7768]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:144](skills/ai-slop-audit/SKILL.md#L144)
[^c335ba416]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:413](skills/lie-detector/scripts/ledger.py#L413)
[^c2a3feb3c]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:1002](skills/lie-detector/scripts/ledger.py#L1002)
[^ccf128b0d]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:1198](skills/lie-detector/scripts/ledger.py#L1198)
[^c4f26fc9b]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:515](skills/lie-detector/scripts/ledger.py#L515)
[^c6a44d483]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:530](skills/lie-detector/scripts/ledger.py#L530)
[^c11aa7726]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:303](skills/lie-detector/scripts/ledger.py#L303)
[^c987a2e46]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:44](skills/lie-detector/scripts/ledger.py#L44), [skills/lie-detector/scripts/ledger.py:1437](skills/lie-detector/scripts/ledger.py#L1437)
[^cb29d02a7]: unverifiable · 2026-09-02
[^cc76a8cdb]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:1437](skills/lie-detector/scripts/ledger.py#L1437)
[^c4aec42eb]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:726](skills/lie-detector/scripts/ledger.py#L726)
[^cac37f727]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:882](skills/metadiscourse-audit/scripts/scan.py#L882)
[^c9553343e]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:353](skills/metadiscourse-audit/scripts/scan.py#L353)
[^ca8fe8ee5]: supported · 2026-09-02 · [evals/fixtures/repo-d/docs/relay.md:10](evals/fixtures/repo-d/docs/relay.md#L10), [evals/fixtures/repo-d/src/relay.py:4](evals/fixtures/repo-d/src/relay.py#L4)
[^cbd28355f]: supported · 2026-09-02 · [install.sh:36](install.sh#L36), [install.sh:38-39](install.sh#L38-L39)
[^cd8bfb1d7]: supported · 2026-09-02 · [install.sh:47](install.sh#L47), [install.sh:38](install.sh#L38)
[^c0b55772c]: unsupported · 2026-09-02
[^cf1a9344c]: unsupported · 2026-09-02
[^c29961a02]: unsupported · 2026-09-02
[^c335cb9e0]: unsupported · 2026-09-02
[^cde054205]: unsupported · 2026-09-02
[^cfaec2646]: unsupported · 2026-09-02
[^cde95968c]: unsupported · 2026-09-02
[^c9e80e15a]: unsupported · 2026-09-02
[^cb455d13b]: unverifiable · 2026-09-02
[^c6d8b08a7]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:1-2](skills/ai-slop-audit/SKILL.md#L1-L2)
[^cbcd0eddc]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:284](skills/ai-slop-audit/SKILL.md#L284)
[^cbc7e2aff]: unsupported · 2026-09-02
[^c31255dad]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:19-27](skills/lie-detector/scripts/ledger.py#L19-L27)
[^cffe46a3e]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:95](skills/ai-slop-audit/SKILL.md#L95)
[^c7976eb21]: supported · 2026-09-02 · [skills/ai-slop-audit/scripts/scan.py:882](skills/ai-slop-audit/scripts/scan.py#L882)
[^c14f6b361]: supported · 2026-09-02 · [skills/metadiscourse-audit/scripts/scan.py:923](skills/metadiscourse-audit/scripts/scan.py#L923)
[^cdeece67d]: supported · 2026-09-02 · [skills/ai-slop-audit/scripts/scan.py:940-942](skills/ai-slop-audit/scripts/scan.py#L940-L942)
[^cf993e82a]: supported · 2026-09-02 · [skills/ai-slop-audit/scripts/scan.py:942](skills/ai-slop-audit/scripts/scan.py#L942)
[^c64e9c1cc]: supported · 2026-09-02 · [skills/lie-detector/scripts/ledger.py:1255](skills/lie-detector/scripts/ledger.py#L1255)
[^c0dad975b]: supported · 2026-09-02 · [skills/lie-detector/scripts/scan.py:463](skills/lie-detector/scripts/scan.py#L463), [skills/ai-slop-audit/SKILL.md:219](skills/ai-slop-audit/SKILL.md#L219)
[^c21d9dec7]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:65](skills/ai-slop-audit/SKILL.md#L65)
[^c33caa1b1]: supported · 2026-09-02 · [skills/ai-slop-audit/SKILL.md:2](skills/ai-slop-audit/SKILL.md#L2)
