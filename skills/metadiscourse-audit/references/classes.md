# The twelve classes, with worked examples

Read this when placing an ambiguous finding or when you want the rewrite
pattern for a class. Nearly every example is real, drawn from four unrelated
repositories — a data pipeline, a simulation engine, an image tool and a
scheduling app — so the patterns here are the ones that recur across domains
rather than one project's habits. Where a class had to reach beyond that
corpus, its section says so.

- [What not to scan](#what-not-to-scan) — events vs projections
- [Part I — from revising](#part-i--from-revising) — classes 0, 0.5
- [Part II — from drafting](#part-ii--from-drafting) — classes 1–10
- [False positives](#false-positives) — what looks like an artifact and isn't
- [The three lines](#the-three-lines) — how the parts interact

---

## What not to scan

**A document is either the events or a projection of them, never both.** A
dated plan, spec, ADR, RFC or changelog is an *event* — written once, read as
of its date, append-only, and its "previously / now" language is its content.
Rewriting one in the present tense destroys what it exists to preserve, so
records are out of scope. A README, architecture doc or runbook is a
*projection* of those events onto now, and should be rebuilt when they change
rather than appended to.

This is not a minor exclusion. On two of the four repositories surveyed, record
documents were **175 of 234** and **117 of 121** of all findings — scanning them
buries every finding in the standing docs under noise from files nobody should
edit. The scanner skips them by default (`RECORD_DIRS`, dated filenames) and
says how many it skipped; `--include-records` overrides.

The same judgement applies to a single file. When a document turns out to *be* a
record rather than to contain artifacts — a two-pass experiment write-up, a
survey with rounds — the finding is not "clean this up". It is: either rewrite
it as present-tense findings, or move it somewhere explicitly historical. That
is the author's call, not the audit's.

---

## Part I — from revising

### Class 0 — iteration artifacts

Event data that leaked into a projection — text that exists because the
document, or the code it describes, used to say something else. **Test: does
this sentence only make sense to someone who read the previous version?**

The rewrite is always the same shape: **state the current fact, delete the
journey.** Where the old state genuinely still matters — because a reader
would otherwise repeat the mistake — it survives as a caution in the present
tense, not as a story about us.

#### 0a — the document revising itself

The purest form: a document arguing with its own past. This shape recurs
verbatim across every repo surveyed.

> ⚠️ **Do not then subtract knob 3 from it.** **An earlier draft of this doc did
> exactly that** (1.0% − 0.97% ≈ 0%) by relabeling the residual, which
> double-removes upkeep and manufactures a false agreement.

**Fold — and this is the hard case worth studying.** The warning is real: a
reader *would* make this mistake, so it stays. What goes is "an earlier draft of
this doc did exactly that". Rewrite as a present-tense rule — "Do not subtract
knob 3 from it: that double-removes upkeep and manufactures false agreement."
The caution survives, the confession doesn't.

> …asserting "knob 1 + knob 3 = the target" afterwards would be a tautology,
> which is **a mistake an earlier draft of this doc made**.

**Cut the clause.** Whether a draft once made the mistake adds nothing to
whether it is a mistake.

> (**An earlier draft said** ~1%/yr; that was the **pre-#168 number**.)

**Cut.** Two artifacts in one parenthesis: a superseded figure and a
version-relative label ("pre-#168") that only means something to someone who
remembers #168.

> `Experiment` unifies **what used to be** two facilities — matrix runs and
> Monte Carlo — under a single runner.

**Fold** → "`Experiment` runs both matrix runs and Monte Carlo under a single
runner." A reader meeting `Experiment` today never knew the two facilities.

> migrations live in `migrations/` and are the source of truth for the schema
> (**it is no longer auto-created on first request**).

**Fold** → drop the parenthesis. This one is instructive because the deleted
behaviour feels important — it *was*, to whoever upgraded. To a new reader,
"the schema is not auto-created" is only confusing: nothing suggested it would
be.

> `## ⚠️ Superseded in part — read § "…" first`

**Cut.** Present the findings that hold; git holds the pass that didn't.

> The original table is kept because being wrong in a recorded way is the
> point of writing these down.

**Cut.** The sentiment is admirable and the text is still cruft. If preserving
the wrong version matters, that is what the commit is.

> …the milestone — which **item 2 above had wrongly concluded** did not exist.

**Cut the clause.** Item 2 should not say it in the first place.

> **Then confirmed** against a real file.

**Fold** → "Confirmed against a real file." Verification status is a fact; the
order in which verifications happened is not.

#### 0b — code changelogs written into prose

The commonest and most mechanical shape. Version identifiers that get stamped
on output are load-bearing; the **prose narrating what changed between two
versions** duplicates the commit.

> _**Changed in** `rules/2026-08-b`: state X was previously inferred from a
> passed date; it now requires a recorded event._

**Cut.** The rule table above it already states the current behaviour, so the
paragraph's only content is that the behaviour used to differ.

> _**Corrected in** `rules/2026-08-c`: `2026-08-b` dropped the security signal
> on the claim that no such column exists. It does — … It is back, and the
> parser now merges wrapped headers._

**Fold, carefully — this is the case that makes blanket deletion unsafe.** The
paragraph is ~90% dead history wrapped around one live fact: *the parser merges
wrapped headers*. Move the fact to where the column is described, delete the
story of the bug and its revert. A regex that deleted the paragraph would have
deleted the fact, which is exactly why `--fix` refuses this shape.

> `src/parsers/summary.ts` **now** parses it.

**Fold** — drop "now". Watch for clusters: three "now"s in one file usually all
mark the same week's work, and none of them means anything to a reader who
arrived afterwards.

#### 0c — dated status stamps

A date written into a paragraph is a promise to come back and edit it. Nobody
does, and the paragraph silently becomes false.

> _**Status 2026-08-05** (both passes): the first pass concluded 0 of 5…
> Reading the sources themselves overturned most of that — 3 of 5 now carry…_

**Fold** to the standing state: the numbers as they are, then the judgement.

> **Still open:**

**Fold.** A heading that claims a state nobody re-checks. Name what is open, or
point at the tracker item that knows.

**The distinction that decides this class:** a date recording *when a
measurement was taken* is data and stays —

> _Run 2026-08-04 against the top five of the July shortlist._ → **Keep**

— while a date recording *when this paragraph was last true* is an artifact.
Check these against `git log` for the file: a paragraph claiming to be current
as of March, untouched since January, is the failure made visible.

#### 0d — backlog leakage

Not history, but the same failure pointing forwards: tracker *state* copied
into a doc, where it goes stale silently.

**The reference is not the problem — the status claim wrapped around it is.**
`(issue #22)` costs about five tokens, survives indefinitely, and appends
cheaply when more issues touch the same spot: `see issues #11, #56, #175`. Keep
those. What rots is the sentence claiming what the issue's state *is*.

> Folding it into the window rules is the obvious next change and **has not
> been made** (issue #22).

**Fold** → "…is the obvious next change (issue #22)." The pointer stays; the
claim about whether anyone has done it goes, because only the tracker knows.

> Issue #4's "median under 15 minutes" criterion **should be rewritten** as
> findability plus source type.

**Fold** → "These numbers describe findability and source type, not the
'median under 15 minutes' criterion in issue #4." A document should not tell a
tracker to edit itself, but it should still say which issue it relates to.

> Real site geocoding is a paid-MVP problem — see issue #11.

**Keep.** A bare cross-reference, no status claim, nothing to go stale.

When in doubt here, keep the reference. A stale pointer costs a click; a
missing one costs the reader the connection entirely.

---

### Class 0.5 — caveats in the main line

Content that is worth keeping and is in the wrong place. **Test: does the
reader need this to act on the next sentence?**

Nothing here is ever Cut. A qualification set inside the sentence it qualifies
doubles the reader's work on the sentence they came for; the same
qualification as a footnote costs nothing until someone wants it.

**Move:**

> **Anchor choice.** The window measures back from the projected end date, not
> from the start date. The start date would be the tighter anchor — the goods
> ship at construction start, not eighteen months later — **but that column is
> sparsely populated, and an anchor that is usually absent produces a report
> that is mostly blank. Revisit if a future month fills it in.**

The paragraph's job is to say what the anchor *is*. The counterfactual and the
revisit note are a message to a future maintainer; footnote them.

> **Assessment:** *Conflict risk:* low-to-moderate… *Pronunciation:* …
> *Positioning risk:* … **Verdict:** keep it.

Three screens of risk before a two-word verdict — the commonest shape of this
class. Verdict in the body, assessment in an appendix. When a section's
conclusion is one line and its justification is fifty, the reader wanting the
conclusion pays for all fifty.

**Keep:**

> **The one limit:** Vercel caps a request body at about 4.5 MB. A workbook
> can exceed that, and if it does the console says so.

The reader hits this in the next sixty seconds. Inline is correct.

> …there are no roles — so **anyone who can sign in can load data and delete
> stored runs.**

A live security property. Burying it would be the wrong call.

> Inline `[V]`/`[H]` tags on forty bullets

The cheap form done right: a token, not a clause. Where a project has an
evidence-tag scheme, use it inline and put the reasoning below.

**The pattern to copy.** A trailing "Limits of this run" section — four
bullets, at the end, out of the way of the findings — is what good looks like.
When a document already has one, that is where Moved caveats go. When it
doesn't, propose one rather than inventing a new structure per caveat.

---

## Part II — from drafting

These can appear in a first draft. All need judgement; none has an objective
test. Ordered by how much volume they typically carry.

### Class 1 — document self-reference and status framing

The document describing itself or how it should be read.

> **How to read this.** Every claim is tagged: → **Cut the label**, keep the legend.
> **How to read this.** Every endpoint lists its method and path. → **Cut the line.** When the "legend" restates what the page shows anyway, there is nothing to keep.
> **A note on schema verification.** Direct egress is blocked… → **Cut the label**; the paragraph stands alone.
> Work is tracked as GitHub issues; this is the shape, not a substitute for them. → **Cut.**
> **Status: design only. Nothing here is built.** → **Keep.** A real scope claim.

### Class 2 — cross-reference and navigation

Pointing at the document's own geometry. Most `above`/`below` hits in
technical docs are *content* (a header row above the data, a value below a
threshold) — check before flagging.

> **Low, but see the caveat below** → **Move**; put the caveat in a footnote and the cell reads "Low".
> …shows you the table below without your having to ask for it → **Cut the clause.**

### Class 3 — walking the reader

The writer narrating the reading experience: announcing the tour, staging the
next stop, voicing the reader's questions for them. Class 2 points at the
document's geometry; this class performs the journey through it.

These examples are the canonical shapes rather than survey finds — the four
repos had almost none of this, because design docs written for peers rarely
walk the reader. The class earns its place anyway: the docs that *do* have it
(onboarding pages, READMEs that grew out of talks, prose that began life as a
transcript) have it in every paragraph.

**Genre decides this class.** A tutorial walks the reader by contract —
someone doing a quickstart asked to be led, and "let's create your first
project" is the voice they signed up for. The scanner skips paths that look
like one (`tutorial`, `getting-started`, `walkthrough`, `onboarding`,
`quickstart`). Everywhere else the reader is mid-task, and the tour-guide
gestures stand between them and the fact they came for.

> Let's take a look at the configuration format. → **Cut.** The heading already did this job.
> Now that we've covered ingestion, we can turn to retries. → **Cut** — or, where the dependency is real, **Fold** it into content: "Retries assume the ingest contract above."
> You might be wondering why the cursor is opaque. → **Fold** → "The cursor is opaque because …". Answer the question instead of performing it.
> As you can see, the schema mirrors the API. → **Cut the opener.** If they can see it, saying so adds nothing; if they can't, saying so doesn't help.
> Let's say the file has 100 rows. → **Keep.** "Let's say / assume / define" frames a worked example — a standard device, not a gesture, and the scanner leaves it alone.

### Class 4 — enumerative pre-announcement

Telling the reader how many items are coming. Cheap to write, and it
forecloses editing: the count is maintained in two places and drifts.

The tiebreaker for the hard cases: a count in the preamble of a visible list
restates what the reader is about to see; a count inside a claim ("two
*independent* defences") is the claim. Either verdict on a preamble count is
defensible — what is not defensible is dropping a count that argues.

> Two further caveats worth carrying into any interpretation: → **Cut** → "Caveats:"
> Two things follow from this table and are already enforced in the code: → **Fold**; keep "enforced in the code".
> Five gaps, ordered by how defensible they look. → **Fold**; keep the ordering key, drop the count.
> ## Two ways to run it → **Keep.** Here the count is the point.

`--fix` strips a "worth …" wrapper (`Two priors worth defending explicitly:` →
`Two priors:`) but never the count itself — "Two independent defences" and
"Three passes" both carry the number as content.

### Class 5 — "worth X" attitude markers

The writer rating the salience of their own point instead of asserting it.

The line runs between naming a price and rating attention:

> **Worth ten minutes** of a real look before the next round of positioning → **Keep.** A costed action.
> **Worth a glance** while the file is open: are the milestone columns dates? → **Fold** → "Check the milestone columns are dates."
> Schema constraints **worth knowing**: → **Cut** → "Schema constraints:"

### Class 6 — salience superlatives

The writer ranking parts of their own argument. The reader is told a thing
matters instead of shown why.

The real problem is rarely the individual superlative — it is **collision**.
When four documents each claim "the single most important thing", they cancel.
One live superlative per document; one canonical home per corpus-wide claim.

> That second line is the finding. → **Cut.** The line is already bolded.
> …the most valuable field in the schema → **Cut** where it is the third assertion of the same claim in three files.
> **These numbers are the least defensible thing in the repository.** → **Keep.** It sets up the interview question that fixes them.

### Class 7 — intent disclosure

"deliberately", "on purpose", "explicitly", "by design". Load-bearing when it
pre-empts a "you forgot this" reading; filler when the sentence already
implies intent.

**The test:** would a reader who sees only the fact conclude you made a
mistake? If yes, keep the marker.

> ## What is deliberately absent → **Keep.** "Absent" alone reads as an oversight.
> **Retrieval is manual on purpose.** → **Keep.**
> Naming work is **explicitly** secondary → **Cut.** Nothing suggests otherwise.
> Two independent defences, **deliberately**: → **Fold.** The reason clause that follows carries it.

### Class 8 — contrastive framing

"not X, it is Y". Effective once per document; at high density it becomes the
house cadence rather than emphasis. Count them before judging any one.

> **This is a validation experiment, not a product.** → **Keep.** The load-bearing instance.
> ## Format stability — measured, not assumed → **Fold.**
> That is what makes dedupe auditable rather than magic. → **Fold.**

### Class 9 — meta-commentary on the record-keeping

The docs discussing the value of writing docs.

> Flagging it as a decision rather than assuming it. → **Cut.** The section is the flag.
> The diff is the record. → **Keep once**, Cut the second and third repetition.

### Class 10 — headings that assert rather than name

A heading is a label; when it argues, the argument is unciteable and the
reader can't skim. Usually the highest-leverage class, because the fix needs
no judgement about content — just name the subject.

> ## The distinction that decides the whole design → **Fold** → "Model maps columns; code reads cells"
> ## The failure is as instructive as the successes → **Fold** → "Trailblazer: a confident wrong answer"
> ## Notes on the non-obvious choices → **Fold** → "Schema choices and their reasons"
> ## What this does not do → **Keep.** A scope boundary.

", and why" as a heading suffix is never wrong and never necessary.

---

## False positives

Every one of these was flagged by the scanner on a real repo and was **wrong**.
They cluster into six families, and knowing them is most of the difference
between a useful pass and a reader discarding output.

### "no longer" describing a condition, not a history

> …a gap missing from the schema, or an entry that **no longer matches** it

> the rendered `![alt](url)` **no longer matches** the token regex — so the
> `edited` event fires

**Keep both.** These are runtime predicates: *when* an entry stops matching,
*this* happens. Compare with the genuine artifact — "the schema is no longer
auto-created on first request" — which describes a change to the system rather
than a condition inside it. The test: does removing the time-dimension break the
sentence? "An entry that does not match" still works; "the schema is not
auto-created" still works too, which is why the second one goes.

### Third-party renames and biography

> **Acme** (formerly Initech) — the approachable planner

> The founding CEO (**previously built** home-services brands inside another
> portfolio)

**Keep.** "Formerly" and "previously" here are facts about the world, not about
the document. A competitor's old name is often the name a reader remembers, so
it is load-bearing. The scanner suppresses the clearest cases; expect to wave
off the rest by hand.

### Research rounds, not revision rounds

> Grounded in two survey **rounds** over fifteen neighbouring systems —
> **round 1**: … ; **round 2**: …

**Keep.** A survey conducted in waves is methodology. Contrast a document
revised in passes ("the search-only pass concluded…"), which is an artifact.
Same word, opposite verdicts: the question is whether the rounds happened to
the *subject* or to the *document*.

### Design contrast, not changelog

> Each topic has one canonical home; other docs link to it **rather than**
> restating it.

> a fixed price captures that as margin **instead of** passing volatility to
> users.

**Keep.** "X rather than Y" is how a design doc states a *choice* against a
plausible alternative. A changelog says what the code used to do. This family
was common enough — ~25 hits across four repos, none of them real — that the
pattern matching it was removed from the scanner entirely.

### Perfect tense inside a condition

> Once the index **has been built**, queries hit it instead of the table.

> The lock is released only after the batch **has been written**.

**Keep both.** These name the moment a condition becomes true — runtime
sequencing, the same shape as the "no longer" family above in a different
tense. A changelog ("the quote-escape branch **has been added** back") has no
conditional marker: nothing in the sentence waits on the event, it just
happened once, off-stage, to the code. The test: swap "has been" for "is".
"Once the index is built, queries hit it" still works; "the quote-escape
branch is added back" loses its only content, which was that something
changed. The scanner suppresses the conditional form and flags the bare one.

### "explicitly" as a mode of action, not a disclosure of intent

> Supplying authorization/token/userinfo **explicitly** makes @auth/core skip
> discovery entirely.

> Default to today's dollars; only nominal when **explicitly** stored as `'0'`.

> the yearly-series presets stay read-only until you **explicitly** override
> them with a single flat value.

**Keep.** Class 7 is the *author* disclosing that a choice was intentional.
These are describing how a caller, a user or the code performs an action —
"explicitly" modifies the verb, not the design. The test: whose intent is being
disclosed? If the sentence would still be true with "explicitly" replaced by
"by hand" or "in so many words", it is a mode of action and there is nothing
to cut. This is the largest single discard family when auditing code comments:
on a 25k-line TypeScript corpus it was 11 of 28 class-7 candidates.

### "used to" meaning "employed in order to"

> Static module metadata **used to** build params and instantiate its cadence.

> Read-only balances **used to** size payoff and liquidation transactions.

**Keep.** A reduced relative clause — "balances *that are* used to size" — and
the commonest shape of comment in a typed codebase. The past-habitual sense
("the catalog used to seed defaults") says a thing no longer happens; this one
says what a thing is for. The scanner suppresses the appositive and
`for`/`of`-headed forms and lets the bare noun-phrase definitions through, so
expect a few of these per corpus.

### Domain vocabulary that collides with revision vocabulary

> A trade accumulating member **corrections** gets its blurb **revised**

> member-**override** rate on applied tags < 10%

**Keep.** "Correction", "revision" and "override" are the subject matter here,
not the document's history. Any repo whose domain involves editing, versioning
or review will trip these. Read the noun, not the verb: corrections *to trades*
are content; corrections *to this section* are artifacts.

---

## The three lines

Three cuts run through this material, in priority order. They can disagree,
and when they do the earlier one wins.

1. **Current state, or how we got here?** → class 0
2. **Main line, or caveat?** → class 0.5
3. **Evidence, or staging?** → classes 1–10

Line 3 is the finest and the most constrained by a project's own conventions:
evidence tags, verification status and provenance stamps are all metadiscourse
and are all mandatory in projects whose rules require them.

Lines 1 and 2 override line 3 where they collide. A "superseded in part"
banner is honest evidence *and* an iteration artifact — it still goes, because
git carries it better.
