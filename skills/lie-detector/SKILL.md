---
name: lie-detector
description: Fact-check documentation by sampling — draw a random, reproducible sample of the factual claims in a README, a docs/ folder, a runbook or the comments in source files, then try to disprove each one against the code, the config and the tests. For when someone asks whether the docs can be trusted, wants the docs fact-checked, spot-checked, audited for accuracy or lies, wants to know how much of a doc set is still true, or wants a documented feature checked against whether it exists. Extracts checkable claims — defaults and limits, flags and paths, guarantees like "never" and "every", version and platform requirements, behaviour on error — and draws n of them by a lottery anyone can recompute from a published seed, so the sample is verifiably not cherry-picked. Each drawn claim gets a falsification test written before the evidence is opened, then a verdict of False, Unsupported, True or Unfalsifiable, and the result is extrapolated to the corpus with a confidence interval rather than reported as "the docs are accurate". Use it for accuracy, drift and trust questions about standing documentation. Not for finding revision debris (metadiscourse-audit) or generation residue and the machine register (ai-slop-audit), not for verifying claims about the outside world that the repository cannot settle, and not for proofreading, changelog generation or rewriting prose.
---

# Lie detector

A lie, here, is a claim the tree contradicts. Not a doubtful claim, not an
aged one, not one you would have phrased differently: a sentence asserting
something a reader would act on, where the code, the config, the tests or
the filesystem say otherwise. The other two audits in this family ask what
documentation *sounds* like. This one asks whether it is **true**, and it
answers by trying to break claims rather than by trying to confirm them.

Two constraints shape the whole method. Checking every claim in a corpus is
not affordable, and checking the claims that catch your eye is worthless —
the ones that catch your eye are the ones you already doubt, and a doc set's
credibility does not rest on the sentences its auditor happened to
distrust. So the sample is drawn by a lottery, published with its seed, and
the result is reported as an estimate of the corpus with its uncertainty
attached.

## Step 1 — fix the corpus, then fix the seed, in that order

The draw is worth something only if it could not have been shopped for.
That is two separate properties, and they are worth separating in the
report because most audits only ever get the first:

- **Verifiable** — anyone can recompute the draw and get your sample back.
  Publishing the seed, the corpus digest and the population size does this,
  and the scanner prints all three.
- **Unbiasable** — you could not have tried seeds until the sample looked
  survivable. Only a seed you did not choose gives you this.

So the order matters. Settle the corpus first — which paths, which
exclusions, at which commit — and only then take the seed. Sources of a
seed nobody controls, best first:

- A public value that did not exist when the corpus was fixed: a
  [drand](https://drand.love) round number, a NIST randomness beacon pulse,
  a stock index close, a block hash. `--seed drand:4210000`.
- A string the person who asked for the audit supplies. Their choosing it
  is the point; you have no way to prepare for it.
- The corpus's own git HEAD, which the scanner uses when nothing else is
  given. It is verifiable, and it is honest about being weak: the auditor
  can commit again to re-roll it. Say so in the report rather than implying
  a rigour the draw does not have.

State in the report which of the two properties you got. An audit that says
"verifiable, not unbiasable — seed was HEAD" is worth more than one that
says "randomly sampled" and leaves the reader to guess.

## Step 2 — draw

The script is `scripts/scan.py` inside this skill's directory. The
**script** is addressed absolutely — take the path from wherever this
`SKILL.md` was loaded (under Claude Code as a plugin,
`"$CLAUDE_PLUGIN_ROOT/skills/lie-detector/scripts/scan.py"`) — while the
**corpus** arguments resolve against your working directory, so stay in the
target project's root:

```bash
SCAN=/absolute/path/to/skills/lie-detector/scripts/scan.py
python3 "$SCAN" docs README.md -n 20 --seed drand:4210000
python3 "$SCAN" docs README.md --json > audit.json   # the manifest, to publish
python3 "$SCAN" docs src --code -n 20                # comments claim too
python3 "$SCAN" docs --pool                          # the whole population
python3 "$SCAN" docs --verify audit.json             # recompute a draw
```

What comes back is the sample, a **queue** — the next claims in draw order —
and the population by class. Twenty is a reasonable draw for a first pass:
enough to bound the error rate usefully, few enough that every claim gets
the code opened against it. Sample less than you can actually check; a
half-checked sample of forty is worse than a checked sample of fifteen,
because it reports a rate it did not measure.

The scanner over-extracts on purpose. A sentence in the population is a
*candidate claim*, and some of them will turn out not to assert anything
checkable — that is what the queue is for, and step 4 says how to replace
one without breaking the draw.

`--pool` prints the population. Read it once before drawing on an unfamiliar
corpus: if the population is mostly navigation and marketing, the corpus is
not making checkable claims, and that finding — a doc set that asserts
nothing falsifiable — is worth reporting on its own.

## Step 3 — write the disproof test before you look

For each drawn claim, before opening any file, write down **what evidence
would make this false**. "The default timeout is 30 seconds" is false if
the constant is anything but 30, or if no such default exists, or if the
flag was renamed. Write that first, then go and look.

This ordering is the difference between an audit and a reading. Opening the
code first means finding a way to read the sentence as true — the code
always offers one, and every claim survives an auditor who starts from the
answer. Pre-registering the test also produces the sentence the report
needs: the evidence that settled it, not the impression it left.

Where to look, by class — the scanner labels each drawn claim with one:

| Class | What it claims | Where it is settled |
| --- | --- | --- |
| **A** | a number or a default | the constant, the argument parser's default, the config schema |
| **B** | an interface: a flag, path, function, env var | the parser, the file's existence, the symbol, the call site |
| **C** | a guarantee: never, always, every, only, idempotent | the test that would fail if it broke — and its absence is itself the finding |
| **D** | a dependency, version or platform | the manifest, the lockfile, the CI matrix, the packaging metadata |
| **E** | behaviour on error: returns, raises, retries, falls back | the handler, the retry loop, the exit path |
| **F** | something external: a URL, a licence, a standard | the target itself; often not settleable from the tree |

`references/falsification.md` has the recipes per class, the verdict rules
for the hard cases, and the families of claim that look false and are not.
Read it when a verdict is not obvious.

## Step 4 — four verdicts, and one rule about the fourth

| Verdict | Meaning |
| --- | --- |
| **False** | The tree contradicts the claim. Quote both sides: the sentence, and the `file:line` that refutes it. |
| **Unsupported** | Nothing in the tree settles it either way. Not a lie — an unverifiable assertion, which is its own finding when the doc states it flatly. |
| **True** | The evidence confirms it. Cite the evidence; a True with no citation is an impression, and impressions do not belong in the tally. |
| **Unfalsifiable** | The sentence asserts nothing checkable ("Relay is designed for reliability"), so no evidence could have settled it. |

**Absence of evidence is Unsupported, never False.** The most damaging thing
this audit can do is call a claim a lie because the grep missed it. If you
cannot find the retry loop, the finding is that you could not find it.

**Unfalsifiable claims are replaced from the queue, never by choice.** Take
the next claim in draw order, and record the swap — "claim 7 unfalsifiable,
replaced by queue 1" — in the report. Replacing a claim you happened to
dislike, or one that looked expensive to check, quietly turns the lottery
back into a hand-picked sample, and nothing in the output would show it.
Unfalsifiable claims still get counted: a corpus that keeps producing them
is telling you something about its prose.

The tally is over the claims that could be settled. If four of twenty were
unfalsifiable, the denominator is sixteen, and the report says so.

## Step 5 — say what a sample means, and no more

A sample bounds a rate; it does not clear a corpus. Nothing false in twenty
draws is consistent with one claim in eight being wrong — which is a
different sentence from "the docs are accurate", and the difference is the
whole reason to sample rather than to spot-check.

```bash
python3 "$SCAN" --interval 2 18    # what 2 lies in 18 checkable draws implies
```

Report the observed rate, the interval, and the population it generalises
to. It generalises to the corpus that was sampled — not to the repository,
not to files you excluded, and not to the claims the extractor never
proposed. A stratified draw (`--class A`) generalises only to that class,
which is worth doing deliberately when someone asks specifically whether
the numbers in the docs are right.

Two findings outrank the rate, and lead the report:

- **A false claim about something load-bearing** — a default, a guarantee,
  a security-relevant behaviour. One of these is the reason the audit was
  worth running, whatever the sample rate turned out to be.
- **A guarantee with no test behind it.** Class C claims that no test would
  catch breaking are not lies today and are the ones that become lies
  silently. Report them as unguarded, with the test that should exist.

## Step 6 — correct, and never quietly

Fixing is by hand — there is no `--fix` here, because every correction
needs someone to decide what the true statement is. When you correct a
false claim:

- **Correct it in the text and name it in the report.** Whoever trusted
  that sentence needs to know it was wrong, not just that it now reads
  right. A silent correction destroys the only evidence the audit produced.
- **Fix the claim, not the sentence around it.** If the default is 10 and
  the doc says 30, the fix is `10` — not a rewrite that removes the number
  and leaves prose no one can check next time. Vagueness is not accuracy.
- **When the code is wrong and the doc is right, say that instead.** A
  disagreement between the two is a finding about the pair, and the doc is
  sometimes the one recording the intended behaviour. Do not "correct" a
  doc into matching a bug.
- **Publish the manifest with the report** (`--json`). It is what lets a
  reader rerun `--verify` and confirm the sample was not chosen after the
  fact — the audit's only claim to being more than an opinion.

## Report format

```markdown
# Lie detector: <corpus> @ <commit>

**Draw.** n of P claims. Seed `<seed>` (<source>) — <verifiable | verifiable
and unbiasable>. Corpus digest `<digest>`. Manifest: `<path>`.
**Scope.** <paths, exclusions, and what was skipped as a record>

## False (N)
| Claim | Where | Refuted by | Correction |
| --- | --- | --- | --- |
| verbatim sentence | `doc.md:12` | `src/relay.py:8` — MAX_RETRIES = 3 | "retries 3 times" |

## Unsupported (N)
<claim, where, and what evidence was looked for and not found>

## Unguarded guarantees (N)
<class C claims that no test would catch breaking, with the test that should exist>

## True (N)
<claim, and the file:line that confirmed it>

## Draw integrity
<unfalsifiable claims and the queue draws that replaced them, in order>

## What the sample implies
<k false of m checkable; observed rate; 95% interval; the population it
generalises to and the one it does not>
```

## Scoping

Sample a **doc set**, not a file — the rate is the output, and a rate over
one file is a rate over nothing. A single-file request is still worth
widening: draw across the set, and report the file they asked about first.

This audit composes with its siblings. `metadiscourse-audit` removes what
revision leaves behind, `ai-slop-audit` removes what generation leaves
behind, and both can strip a false claim's *wrapper* while leaving the false
claim standing — "leverages a robust 30-second timeout" becomes "the timeout
is 30 seconds", which is tidier and still wrong. Run this one last, over the
cleaned text, and its findings will be about facts rather than register.

Records — dated plans, specs, ADRs, changelogs — are excluded from the draw,
because their claims were true of a proposal on a date and disproving them
establishes only that the plan changed. Sample them deliberately
(`--include-records`) only when someone asks whether a specific record was
ever implemented, and label that draw as what it is: a check of intent
against outcome, not an audit of the documentation.
