---
name: metadiscourse-audit
description: Clean up, tighten or de-cruft existing prose docs — a README, a docs/ folder, a design doc — by stripping out metadiscourse, meaning text whose subject is the document, its author or its reader rather than the thing it documents. Targets what revision leaves behind — changelogs written into prose ("previously X, now Y"), a document arguing with its own earlier drafts, dated status stamps, caveats buried mid-paragraph that belong in a footnote — plus staging tics like announcing how many bullets follow, "it's worth noting", headings that argue instead of naming, and the same superlative claimed in four different files. Returns a file:line inventory with cut/fold/move/keep verdicts and a concrete rewrite for each, and can apply the safe subset. Use it whenever docs are called bloated, padded, repetitive or exhausting, whenever they read like a changelog or carry "how we got here" that belongs in git, whenever someone wants docs to stand alone in the present tense, whenever they want the findings list before any edits, and whenever they ask for a documentation style guide — the audit is what the guidance should be built from. Not for scrubbing AI writing voice out of freshly generated text, finding docs stale relative to code, generating changelogs or release notes, reconciling contradictory content, translating, proofreading, or cleaning up code.
---

# Metadiscourse audit

Metadiscourse is text whose subject is the text, its author, or its reader,
rather than the thing the document is actually about. Some of it is load-
bearing. Most of the volume is not, and nearly all of the volume arrives
through revision rather than drafting.

The point of this audit is a **specific, citable inventory** — not a verdict
that the prose "could be tighter". Every finding gets `file:line`, the
verbatim text, a class, a verdict, and the rewrite. Someone should be able to
act on any single line without re-reading the document.

## What makes this worth doing carefully

A first draft rarely has this problem. It appears when a fact changes and the
new fact gets **appended next to the old one** instead of replacing it:

- A fact changes → the doc gains "previously… now…" instead of just the new
  fact. That is class 0.
- A claim gets challenged → the doc gains "but note that…" mid-paragraph
  instead of a footnote. That is class 0.5.

Appending is the safe edit. It never loses anything, it doesn't require
re-reading the surrounding argument, and each instance is individually
defensible. The cost is invisible per-edit and compounds — which is why the
densest files in any corpus are the ones that were revised most.

So classes 0 and 0.5 come first. They are also the two with **objective
tests**, which means they can be decided without taste:

- **Class 0 test** — a standing document should read coherently to someone who
  has never seen its history. If a sentence only makes sense to a reader who
  knows what the last commit changed, it is an artifact.
- **Class 0.5 test** — does the reader need this to act on the next sentence?

Everything else needs judgement. Do the decidable work first; it usually
accounts for half the findings and all of the uncontroversial ones.

## Step 1 — read the project's conventions first

**Do this before scanning.** Read whatever the project uses to state its own
rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`,
`.github/copilot-instructions.md`, `docs/style.md`, a `STYLEGUIDE`, or a
writing section in the README. Any one of them can define a convention this
audit would otherwise strip.

Projects encode conventions that *require* metadiscourse, and a scan that
doesn't know about them will confidently strip the thing the project depends
on. Real examples: a repo whose rules say "stated vs inferred is never
blurred" needs its `[V]`/`[H]` evidence tags and its "Unverified against a
real filing" markers. A repo that versions its rules needs the version
identifiers, even while the prose *narrating what changed between versions* is
pure class 0. When that narration is folded away, the identifier survives as
one present-tense statement — "Current rule set: `X`" — not as a trail of
stamps.

Write down what you find as **protected**, and say so in the report. If a
finding collides with a protected convention, it is Keep, and the report
should name the convention that protects it. Getting this wrong is the main
way this audit does damage.

Genre is a convention too, and it doesn't need a rules file to exist. A
tutorial or quickstart walks the reader by contract — "let's", "now that
we've" are its voice, not cruft — so reader-address findings in
tutorial-shaped files are Keep. The scanner already skips paths that look
like one; apply the same judgement to files it can't recognise by name.

## Step 2 — events or projection, never both

**A document is either the events or a projection of them. A document that is
both is the thing this audit fixes.**

- A **record** is an event. A dated plan, spec, ADR, RFC, changelog or release
  note is written once, at a point in time, and read as of that date. Its
  "previously / now" language *is* its content. Records are append-only:
  rewriting one in the present tense destroys what it exists to preserve, so
  records are **out of scope**.
- A **standing document** is a projection of those events onto now. A README,
  an architecture doc, a runbook, a reference page. It answers "what is true
  today" and should be **rebuilt** when the events change, not appended to.

Class 0 is event data that leaked into a projection — the document replaying
how it reached its current state instead of just presenting that state. This is
why the fix is always *state the current fact, delete the journey*: a
projection has no journey. It is also why appending feels safe and isn't. Each
append is a correct event; the mistake is writing it into the projection rather
than rebuilding the projection from it.

This is the single biggest scoping decision, not a detail. On two real
repositories, record documents were **175 of 234** and **117 of 121** of all
findings — left in, they bury every finding in the standing docs under noise
from files nobody should be editing. The scanner excludes them by default
(dated filenames, `plans/`, `specs/`, `adr/`, `rfc/`, `decisions/`,
`superpowers/`, changelogs) and reports the count it skipped.

Judge the same way file by file. When a document turns out to *be* a record
rather than to contain artifacts — a two-pass experiment write-up, a survey
conducted in rounds — don't clean it. It is an event log, and the honest
options are to rebuild the projection beside it or move it somewhere
explicitly historical. That is the author's call.

## Step 3 — scan

The script is `scripts/scan.py` inside this skill's directory. The two paths
resolve against different roots and mixing them up is the usual first failure:
the **script** must be addressed absolutely, because the skill is installed
somewhere else entirely, while the **corpus** arguments (`docs`, `README.md`)
resolve against your working directory. So stay in the target project's root
and resolve the script path once:

```bash
SCAN=/absolute/path/to/skills/metadiscourse-audit/scripts/scan.py
```

Take that path from wherever this `SKILL.md` was loaded from — under Claude
Code as a plugin it is `"$CLAUDE_PLUGIN_ROOT/skills/metadiscourse-audit/scripts/scan.py"`;
installed as a plain skill, `~/.claude/skills/metadiscourse-audit/scripts/scan.py`
or the project's `.claude/skills/` copy. Then:

```bash
python3 "$SCAN" docs README.md --exclude drafts/
python3 "$SCAN" docs --class 0            # iteration artifacts only (0a-0d)
python3 "$SCAN" docs --json               # machine-readable
python3 "$SCAN" docs --include-records    # override the exclusion
python3 "$SCAN" docs --class 0 --check    # CI gate: exit 1 on findings
```

The scanner over-reports on purpose: a false positive costs one glance, a miss
leaves an artifact in place for another year. Treat output as **candidates,
not findings**. Expect to discard roughly a third — `references/classes.md`
lists the six families that account for most of them, and reading that section
before triaging saves re-deriving them.

It groups by class, and one line can honestly carry two — a dated stamp
wrapped around a tracker claim is 0c *and* 0d. Triage such a pair as one
finding. It separately reports **collisions** — superlatives and
aphorisms repeated across files. That pass only works corpus-wide, and it is
often the most useful single output: four documents each claiming to hold
"the single most important thing" cancel each other out, and no individual
file shows the problem.

It ends with a **density table** — candidates per 100 lines, per file — and a
`clean:` line naming the files with no candidates at all. Those are the
report's "density per file" and "What is already clean" sections, precomputed:
density says where revision has concentrated and the edit pass should start;
the clean list is what a later rewrite must not regress.

Read the surrounding paragraph for every candidate you keep. The scanner sees
one line; whether a caveat interrupts the main line is a property of the
paragraph.

## Step 4 — classify and decide

Four verdicts:

| Verdict | Meaning |
| --- | --- |
| **Cut** | Deleting it loses nothing. |
| **Fold** | It carries a real claim wrapped in staging. State the claim; drop the wrapper. |
| **Move** | The content is worth keeping and is in the wrong place. Footnote or appendix. |
| **Keep** | It belongs where it is — usually a protected convention or a procedure step. |

Two rules that decide most of the hard cases:

**Caveats are never Cut, only Moved.** A risk, hedge or unverified claim is
content. The failure is placement, not existence. If a document already has a
"Limits" or "Caveats" section at the end, that is the destination and the
pattern to copy; if it doesn't, propose one.

**Keep cross-references; cut the status claims around them.** `(issue #22)`
costs a handful of tokens, never rots, and appends cheaply as more issues touch
the same spot. "…and has not been made" is the part that goes stale, because
only the tracker knows. When in doubt, keep the reference — a stale pointer
costs a click, a missing one costs the connection.

**A superlative is information exactly once.** Rule of one live superlative
per document, and one canonical home per corpus-wide claim. When the collision
pass finds the same claim in four files, three of them are Fold and the
fourth — the one in the most relevant document — is Keep.

For the full taxonomy with worked examples of each class, read
`references/classes.md`. Read it when you need to place an ambiguous finding
or want the rewrite patterns; the summary above is enough for clear cases.

### Where git helps

For class 0, `git log -p --follow <file>` confirms whether "an earlier version
said X" has a commit behind it — and if it does, that is the argument for
deleting the prose: the history already exists, in a form that can't drift out
of sync with the text the way a hand-written "now settled" can.

For class 0c, check dated status stamps against the commit that last touched
the paragraph. A date claiming a paragraph was true in March, in a paragraph
untouched since January, is the failure mode made visible.

## Step 5 — fix

`--fix` applies **only rewrites whose removal cannot lose a fact**:

```bash
python3 "$SCAN" docs --fix --dry-run   # always look first
python3 "$SCAN" docs --fix
```

That is a deliberately narrow set — stripping a "worth …" wrapper from a list
preamble, removing "it is worth noting that" and its relatives ("please note
that", "as you can see" — though never "but note that", whose clause anchors
a caveat to Move, not delete), dropping "Then" from "Then confirmed". Expect
single digits on a large corpus, often zero.

It is narrow because everything valuable here requires deciding **what the
surviving fact is**, and that is not a regex's job. Counts are the instructive
near-miss: `Two hard rules:` → `Hard rules:` looks mechanical, but "Two
independent defences" carries an argument that depends on there being two, and
"Three passes" tells a reader how long the list is before they start it. So
counts are reported as class 4 for a human to judge and never auto-stripped.
Keeping `--fix` this small is what makes it safe to run unattended.

Everything else you apply by hand, with Edit, one finding at a time. When you
do:

- **Rewrite, don't just delete.** A class 0b changelog usually contains one
  live fact — "the parser merges wrapped headers" — buried in the story of how
  it got there. Move the fact to where the thing is described; delete the story.
- **Re-read the paragraph as if the new fact had always been true.** This is
  the habit that prevents the problem recurring, and it is the single most
  useful thing to hand back to the author.
- **Show the diff before applying** anything structural (moving a caveat to an
  appendix, collapsing a two-pass section). Those change what the document
  *is*, not just how it reads. Running unattended on a task that asked for the
  cleanup, apply it — and lead the report with those diffs, because they are
  the ones a reviewer must see.
- **Never invent a protected marker.** An evidence tag added during a rewrite
  is a verification claim nobody made. Carry provenance in prose ("measured
  with two independent extractors"). Where the project's rules require a tag
  on every claim, an untagged rewrite breaks the convention too — give the
  sentence the tag its evidence honestly supports, or hand the choice to the
  author. The one forbidden move is stamping "verified" on something nobody
  verified.

If a whole file turns out to be an iteration artifact rather than a document
containing them — an experiment log, a two-pass write-up — say so and stop.
That is a decision about what the file is for, and it belongs to the author.
Offer the two options: rewrite it in the present tense, or move it somewhere
that is explicitly a historical record.

## Report format

```markdown
# Metadiscourse audit of <corpus>

**Scope.** <files, line count, what was excluded and why>
**Protected conventions.** <from step 1 — what must not be stripped, and why>

## Class 0 — iteration artifacts (N)
| Where | Text | Verdict |
| --- | --- | --- |
| `file.md:12` | verbatim quote | **Cut**. <the rewrite> |

## Class 0.5 — caveats in the main line (N)
...

## Part II — staging classes (N)
<classes 1-10, same table shape>

## Collisions
<phrases repeated across files, with every site>

## Totals
<by class, by verdict, and density per file>

## What is already clean
<name it, so a later edit doesn't regress it>
```

Two things that make the report usable rather than decorative:

**Density per file** points at where revision has concentrated, which is where
the next round of edits should go. The scanner's density table is this,
ready to carry over.

**"What is already clean"** matters more than it looks. Tables, checklists and
reference sections tend to be clean because there is nowhere to put a "worth
noting" — naming them stops a later rewrite from prosifying them. Start from
the scanner's `clean:` line, then add the sections that held up inside
dirtier files.

## Scoping

Audit a **doc set**, not a single file. The collision pass needs the corpus,
and density comparisons are what identify the files worth editing. A
single-file request is still worth widening: scan the set, report the file
they asked about first. When the set turns out to *be* one file, say so and
carry on — widening means the rest of that project's docs, never unrelated
corpora that happen to sit nearby.

If the corpus is large, do classes 0 and 0.5 across everything first and
report those before starting the judgement pass. They are the findings most
likely to be acted on, and they arrive fastest.
