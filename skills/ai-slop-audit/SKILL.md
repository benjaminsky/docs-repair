---
name: ai-slop-audit
description: Clean up docs that were generated or heavily edited by an AI assistant — a README, a docs/ folder, a wiki that ballooned after coding-agent sessions, the comments in source files — by stripping generation residue and the machine register. Targets chat turns committed as documentation ("I've updated the script", "Hope this helps!", "Let me know if you have any questions"), completion reports pasted where a description belongs ("The following changes were made", "All 47 tests pass"), unfilled template scaffolding and empty sections, links to files that don't exist, prose that restates what the code already does instead of why it does it, plans left behind after their work merged, emoji-decorated headings, importance inflation ("comprehensive", "robust", "seamless", "production-ready"), the lexical tells ("delve", "leverage", "utilize", "streamline"), essay scaffolding ("In this guide, we'll", "In conclusion"), walls of bold-term bullets, and the same paragraph regenerated into three files. Returns a file:line inventory with cut/fold/verify/keep verdicts and a concrete rewrite for each, and can apply the safe subset. Use it whenever docs are called AI-generated, slop, machine-written or "written by the agent", whenever someone says the docs sound like ChatGPT or read like marketing, whenever a doc folder doubled after agent sessions and someone wants to know what's real, and whenever they want the findings list before any edits. Not for rewriting a freestanding draft pasted into chat, not for revision debris in human-written docs — "previously X, now Y", dated status stamps, buried caveats are metadiscourse-audit's territory — and not for AI-generated code, changelog generation, staleness detection, translation or proofreading.
---

# AI slop audit

Slop, here, is not "text an AI touched". It is the residue of *generation*:
what a session leaves behind when it writes a document without reading the
corpus it joins, in a register tuned to look complete rather than to be
correct. Some of it is process debris with an objective test — a chat turn
committed verbatim, a link to a file that was never created. Most of the
volume is register: inflation, scaffolding and decoration that a reader has
to wade through to reach the facts.

The point of this audit is a **specific, citable inventory** — not a verdict
that the docs "sound like AI". Every finding gets `file:line`, the verbatim
text, a class, a verdict, and the rewrite. Someone should be able to act on
any single line without re-reading the document.

## What makes this worth doing carefully

Each generated document is locally plausible. The damage is corpus-level and
arrives three ways:

- **The process leaks into the artifact.** A session's closing pleasantry,
  its summary of what it changed, its "All 47 tests pass" — true of a chat
  on a Tuesday, committed as if it described the system. That is class 0.
- **Confidence outruns verification.** Generated docs link to files that
  don't exist, document flags that were never built, and re-explain what the
  code already says — with total fluency. Nothing in the prose marks which
  claims were checked.
- **Sessions don't read sibling docs.** So the same explanation gets
  regenerated wherever it seems locally useful, and every file
  independently claims to be comprehensive. No single file shows the
  problem; the corpus does.

Class 0 comes first: it has objective tests, so it can be decided without
taste. A standing document has no author performing edits in it, and a
relative link either resolves or it does not. Everything after that needs
judgement — and the judgement that matters most is not "does this sound
generated" but "is this claim true of the code".

One thing this audit never does: count punctuation. Em dashes, semicolons
and Oxford commas are not evidence of anything — people who write well use
all three heavily, and a "detector" built on them flags the best human prose
in the corpus. Every class here names a specific removable behaviour, not a
style.

## Step 1 — read the project's conventions first

**Do this before scanning.** Read whatever the project uses to state its own
rules — `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, a style guide, a
writing section in the README. Projects encode conventions that *look like*
findings, and stripping them is the main way this audit does damage:

- A repo using gitmoji, or emoji as section markers by declared convention,
  keeps its emoji. Class 5 is about unchosen decoration, not chosen systems.
- A support matrix's ✅/❌ carries the answer. The scanner already skips
  table rows; apply the same judgement to legends and keys.
- Marketing-facing pages may be *intended* to say "seamless". If the
  register was chosen, it is a convention — say so in the report and leave
  the page out, rather than editing the marketing to sound like a runbook.

Write down what you find as **protected**, and say so in the report. If a
finding collides with a protected convention, it is Keep, and the report
should name the convention that protects it.

## Step 2 — events or projection, never both

Same rule as every audit in this family: a dated plan, spec, ADR, RFC or
changelog is a **record**, written once and read as of its date. A session
hand-off note saved under `plans/` with a date in its name is a record too —
its "I've implemented the first two phases" is its content, however it was
authored. Records are out of scope, and the scanner excludes them by
default — which is a rule about scanning, not about keeping: step 5 covers
the plan that the merge made redundant.

A README, an architecture doc, a runbook is a **standing document**: a
projection of the system onto now. Class 0 is process residue that leaked
into a projection — a chat turn is an event, and committing it into a
standing doc is the same mistake as writing a changelog into one.

When a whole file turns out to be a saved transcript or a completion report
rather than a document containing residue, don't clean it — say so. The
honest options are to extract the facts into the standing docs and delete
it, or move it somewhere explicitly historical. That is the author's call.

## Step 3 — scan

The script is `scripts/scan.py` inside this skill's directory. The **script**
is addressed absolutely — take the path from wherever this `SKILL.md` was
loaded (under Claude Code as a plugin,
`"$CLAUDE_PLUGIN_ROOT/skills/ai-slop-audit/scripts/scan.py"`) — while the
**corpus** arguments resolve against your working directory. So stay in the
target project's root:

```bash
SCAN=/absolute/path/to/skills/ai-slop-audit/scripts/scan.py
python3 "$SCAN" docs README.md --exclude drafts/
python3 "$SCAN" docs --class 0            # generation residue only (0a-0d)
python3 "$SCAN" docs --json               # machine-readable
python3 "$SCAN" docs src --code           # also scan code comments
python3 "$SCAN" docs --class 0 --check    # CI gate: exit 1 on findings
```

The scanner over-reports on purpose: a false positive costs one glance, a
miss leaves a chat turn in the docs for another year. Treat output as
**candidates, not findings** — `references/patterns.md` lists the false-
positive families that account for most discards, and reading that section
before triaging saves re-deriving them. "Robust" in a statistics doc,
"harness" in a test doc and "leverage" in a finance doc are the domain
talking, not the register.

Class 0d — **phantom relative links** — is checked against the filesystem,
so those findings are facts, not candidates. The scanner also reports
**echoes** at two granularities: sentences repeated verbatim across files
(matched after paragraphs are joined, so soft wraps don't hide them), and
paragraphs that are near-verbatim by shingle overlap — the regenerated-
boilerplate tell that only shows corpus-wide. Both are deterministic;
"same idea in different words" is yours to catch in triage, where you have
the files open anyway. It ends with a **density table** and a `clean:`
line — where to start editing, and what a later rewrite must not regress.

The scanner sees prose. Fenced code blocks are skipped, so placeholder
values and hallucinated flags inside examples are yours to catch in step 4.

### Code comments

The same residue accumulates next to code — `# I've bumped this to handle
the new load` beside a constant, `// leverages a robust worker pool` above
a function — and the register classes apply unchanged. `--code` extends a
directory walk to source files; a source file named on the command line is
scanned without the flag, because naming it is the request.

Three differences from prose: TODO, FIXME and their relatives are skipped
(a TODO is a tracker item living in code, and its "not yet" is its
content); docstrings are out of scope (a triple-quoted string is data as
often as documentation); and `--fix` never rewrites a source file — comment
extraction is heuristic, so every comment finding is applied by hand, with
Edit. A source file's density divides by its comment lines, not its total
lines, so the density table still compares prose against prose.

## Step 4 — verify the claims no scan can

This is the step that distinguishes auditing generated docs from linting
them, and it needs the code open. The scanner's phantom-link class is the
deterministic tip of a bigger iceberg: **generated prose asserts with equal
confidence what it verified and what it assumed.**

For each scanned document, take the load-bearing claims — defaults, flag
names, file paths, behaviour on error, anything a reader would act on — and
check them against the code. Three outcomes:

- **True** → the claim stays (and the inflation around it still goes).
- **False or unbuilt** → that is the finding that matters most in the whole
  report. A documented feature that doesn't exist outranks fifty
  "seamlessly"s. Lead with these.
- **True but a restatement** — prose that paraphrases the signature or the
  code beside it, adding nothing the code doesn't say. Verdict Cut, with the
  code cited as the reason nothing is lost. Step 5 is that judgement in
  full, including where it stops.

Where git helps: `git log --diff-filter=A --format='%an %s' -- <file>` shows
who or what introduced a document, and a doc whose every line landed in one
commit alongside generated code is a doc whose claims all date from one
session — check them as a batch.

## Step 5 — cut what the code already says

Step 4 asks whether a claim is true. This step asks whether it was worth
making. Prose that restates the implementation is true on the day it is
written and unowned afterwards: nothing updates it when the function
changes, and nothing warns the reader when it has drifted. The code answers
*what*; a document earns its place by answering *why*.

The test is a hypothetical edit: **if someone changed the code without
touching this line, would the line become wrong?** If yes, it is tracking an
implementation it cannot see, and the implementation says it better —
verdict Cut, citing the file and symbol that carries the fact. If the line
would survive that edit — because it explains a constraint, a rejected
alternative, an invariant spanning files, a reason that lives outside the
repository — it is doing work no signature can do. Keep it.

What passes the test, in practice:

- The constraint the code obeys but cannot state: "the vendor rejects
  batches over 500, so the chunk size is not tunable."
- The alternative that was tried and abandoned, with the symptom that
  killed it.
- An invariant holding across two files — the reason both must change
  together.
- The interface contract for a reader who will never open the source.
  Reference documentation written for consumers of a published API is the
  artifact, not a shadow of one. This step is about prose restating code
  that its own readers can read.

A restatement is Cut rather than Fold when the code is in the same
repository, and Fold when a *why* is buried in it: "the `--retries` flag
sets the retry count, which is 3 by default because the upstream load
balancer drops idle connections at 4" loses its first clause and keeps its
second. Where a whole document is a narration of one module, say so in the
report rather than editing it line by line — the honest fix is deleting the
file and linking to the source.

### Comments hold to the same standard

`// increment the retry counter` above `retries += 1` is this finding in a
different file type, and the density of it is higher in code than in prose
because a session writing code narrates as it goes. A comment stays when it
names the why: the bug it works around, the boundary case the obvious
version gets wrong, the reason a slower path was chosen. It goes when a
reader could recover it by reading the next line.

Two carve-outs, both already the audit's rules: TODO and FIXME are tracker
items, not narration, and are out of scope; and `--fix` never rewrites a
source file, so every comment finding is applied by hand with Edit.

### Plans die at the merge; specs do not

Records are excluded from the scan (step 2), and that does not change —
nothing here is a scanner verdict. But "not scanned" is not "kept forever",
and the two record types age in opposite directions once the code lands.

A **plan** is a route: phases, ordering, checklists, "then wire the handler
into the router". When the work is merged the route is redundant with the
thing it describes, and worse than redundant — a plan reads as intent, so
the next reader, often the next session, takes a finished plan for
outstanding work or for a design the code has since moved past. Delete
merged plans. Git keeps them, and the reason the design is what it is
belongs in the standing docs anyway, not in the file that predates the
decision.

A **spec** is a destination: what the system must do, the constraints on
it, what is deliberately out of scope. Implementation does not consume
that — it is what the code gets checked against next year. Keep specs,
including the ones a superpowers-style workflow generates under `specs/`;
it is the `plans/` beside them that should be cleared out.

Check before deleting: a plan whose phases are half-built is live, and a
plan carrying the only written record of *why* an approach was chosen needs
that paragraph moved into the standing docs first. List the plans in the
report with the commit or code that implements each, and let the author
confirm the ones that are spent.

## Step 6 — classify and decide

Four verdicts:

| Verdict | Meaning |
| --- | --- |
| **Cut** | Deleting it loses nothing. Residue, inflation, decoration. |
| **Fold** | A real claim wrapped in register. State the claim; drop the wrapper. |
| **Verify** | The line asserts something only the code can confirm. Check it, then Cut, Keep or correct it. |
| **Keep** | It belongs — usually a protected convention or the domain's own vocabulary. |

Rules that decide most of the hard cases:

**Deflate to the measurable fact, or to nothing.** "Blazing-fast responses"
either becomes the number ("p99 under 3 ms") or disappears — there is no
third rewrite where the adjective survives. If nobody has the number, the
honest sentence is the one without the claim.

**An empty section is a question, not a deletion.** Scaffolding that was
never filled ("## Troubleshooting" over nothing) means someone thought the
section should exist. Cut it by default, but list it in the report as a
possible gap — the author may want the content, not the removal.

**The code answers what; the doc answers why.** A line that would go wrong
on its own the next time someone edits the implementation is Cut, per step 5
— including in comments.

**Echoes get one home.** When the same explanation lives in three files,
pick the file that owns the topic, keep it there, and replace the others
with a link. Same rule as any duplicated fact; generation just produces
more of it.

**Bullet walls become tables or paragraphs.** A run of `**Term**:
description` bullets is a table wearing prose's clothes — parallel rows
belong in a table; an argument belongs in a paragraph. Which one is a
judgement call the report should make explicitly.

For the full taxonomy with worked examples and the false-positive families,
read `references/patterns.md`. Read it when a finding is ambiguous; the
summary above is enough for clear cases.

## Step 7 — fix

`--fix` applies **only rewrites whose removal cannot lose a fact**:

```bash
python3 "$SCAN" docs --fix --dry-run   # always look first
python3 "$SCAN" docs --fix
```

That set is: deleting a line that is entirely pleasantry ("Hope this helps!
Let me know if you have any questions."), stripping emoji from headings, and
removing "In conclusion,"-family sentence openers. Expect single digits.
Everything else needs someone to decide what the surviving fact is —
especially class 1, where the right rewrite depends on whether the number
behind the adjective exists.

Everything else you apply by hand, with Edit, one finding at a time. When
you do:

- **Rewrite, don't just delete.** A handoff summary usually contains one
  live fact — "the scheduler uses a worker pool" — inside the report of how
  it got there. Move the fact to where the thing is described; delete the
  report.
- **Re-read the paragraph as if a person who had read the code wrote it.**
  That is the standard the rewrite has to meet, and the habit that prevents
  the problem recurring.
- **Show the diff before applying** anything structural — collapsing an
  echo to a link, converting a bullet wall to a table, deleting an empty
  section. Those change what the document is, not just how it reads.
- **Never fix a false claim silently.** A doc that says the default is 30
  when the code says 10 gets corrected in the text *and* named in the
  report — whoever trusted the doc needs to know it was wrong, not just
  that it is now right.

## Report format

```markdown
# AI slop audit of <corpus>

**Scope.** <files, line count, what was excluded and why>
**Protected conventions.** <from step 1 — what must not be stripped, and why>

## Verified claims
<from step 4: false or unbuilt claims first — these outrank everything below>

## Redundant with code
<from step 5: prose and comments restating the implementation, each with the
file:symbol that already says it; then merged plans, each with the commit or
code that implements it>

## Class 0 — generation residue (N)
| Where | Text | Verdict |
| --- | --- | --- |
| `file.md:12` | verbatim quote | **Cut**. <the rewrite> |

## Classes 1-6 — register (N)
<same table shape>

## Echoes
<sentences repeated across files, with every site and the proposed home>

## Totals
<by class, by verdict, and density per file>

## What is already clean
<name it, so a later edit doesn't regress it>
```

Findings that failed verification lead the report. Density says where to
edit next. "What is already clean" stops a later rewrite — possibly a later
*session* — from regressing the files that are fine.

## Scoping

Audit a **doc set**, not a single file. Echoes only exist corpus-wide, and
density comparisons are what identify the files worth editing. A single-file
request is still worth widening: scan the set, report the file they asked
about first.

This audit composes with its sibling, `metadiscourse-audit`. Generated text
contains metadiscourse too — a model writes "it's worth noting" as readily
as a person revising — and revision debris accumulates in generated docs
once humans start editing them. The split is by *origin*: residue and
register of generation belong here; the debris of revision ("previously X,
now Y", dated stamps, caveats mid-paragraph) belongs there. On a corpus with
both histories, run both scanners and triage the union — a line flagged by
both is one finding, not two.
