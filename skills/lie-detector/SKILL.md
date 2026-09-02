---
name: lie-detector
description: Check whether documentation is true, and keep it true — verify the factual claims in a README, a docs/ folder, a runbook or the comments in source files against the code, config and tests that settle them. Two modes. The ledger mode enrols every claim in a sidecar beside each document (`README.claims.toml` next to `README.md`), optionally anchoring each sentence to its entry with a markdown footnote so a rewrite keeps its verdict, records each verdict with the file:line evidence that settled it, and re-verifies only what a later commit staled, so a doc set gets a coverage number, a CI gate and per-sentence provenance; `init` grandfathers the existing backlog so day one is green, and offers the AGENTS.md or CLAUDE.md line that tells future sessions to verify their own claims. The sample mode draws a reproducible random sample instead, for a repository you do not own. Use it whenever someone asks whether the docs can be trusted, wants them fact-checked, spot-checked or audited for accuracy, wants to know how much of a doc set is still true, wants a documented feature checked against whether it exists, or wants documentation drift caught in CI. Verdicts are supported, refuted, unsupported and unverifiable; absence of evidence is never a refutation. Not for finding revision debris (metadiscourse-audit) or generation residue and the machine register (ai-slop-audit), not for claims about the outside world a repository cannot settle, and not for proofreading, changelog generation or rewriting prose.
---

# Lie detector

A lie, here, is a claim the tree contradicts. Not a doubtful claim, not an
aged one, not one you would have phrased differently: a sentence asserting
something a reader would act on, where the code, the config, the tests or
the filesystem say otherwise. The sibling audits ask what documentation
*sounds* like. This one asks whether it is **true**, and it answers by
trying to break claims rather than by trying to confirm them.

Two scripts, and which one you want follows from one question — **do you
maintain these docs?**

| | `scripts/ledger.py` | `scripts/scan.py --sample` |
| --- | --- | --- |
| Answers | is every claim true, and what settled it | roughly how wrong is this doc set |
| Output | a ledger checked into the repo | a report, nothing checked in |
| Cost | a full pass once, then only what changed | one sample, every time |
| For | docs you own | a repo you do not own, or a first look |

The rest of this file is the ledger mode. Sampling is at the end.

## Why a ledger, and why it is affordable

Checking every claim on every run is not affordable, which is the argument
that usually ends in sampling. The way out is not a smaller sample; it is
**not re-verifying what has not moved**.

Every verdict is anchored to two hashes, and keeping them apart is what lets
a verdict have a history:

- **identity** — which claim this is: the file, plus the identifiers it is
  about. Editing 500 to 100 leaves identity alone, so the entry keeps its
  audit trail instead of arriving as a stranger.
- **skeleton** — what it asserts: those identifiers plus the numbers, units,
  quantifiers and modals. Rewording prose does not move it; changing a
  value, a unit, or a "never" into a "rarely" does.

Plus a hash of the cited evidence itself. A verdict stays live while the
skeleton and every evidence hash hold; when one moves, that one entry is
what gets re-verified. The first run is an audit. Every run after it is a
diff.

**Nobody maintains the ledger.** Each run re-derives the claim set from the
documents and compares: in the docs but not the ledger is a new claim, in
both with a moved hash is stale, in the ledger but not the docs is an
orphan. A doc edit cannot escape unnoticed — only be ignored, which is what
the gate is for.

## Step 1 — enrol, and wire it in

```bash
LD=/absolute/path/to/skills/lie-detector/scripts/ledger.py
python3 "$LD" init docs README.md --anchor
```

Enrolling writes a **sidecar beside each document** — `README.claims.toml`
next to `README.md` — so the metadata lives with the prose making the claims,
each file stays small enough to review, and a docs PR touches only the
sidecars for the documents it changed. A sidecar names its own document, so
nothing afterwards needs to be told the corpus.

Every claim is recorded `unverified` and `exempt`, and **nothing is marked
supported**. An unverified entry is a claim the ledger knows about, not one
anybody has an opinion on; recording a verdict nobody established is the
failure this skill exists to prevent. `init` does do the mechanical half of
verification — searching the tree for candidate evidence — so the judgement
is what is left.

Day one is therefore green, with the whole backlog visible and the gate
already enforcing on anything new. This is `cargo vet init`'s exemptions and
ESLint's bulk suppressions, for prose.

`--anchor` writes each claim's id into the document as a markdown footnote
and maintains the definitions at the end of the file:

```markdown
The `--batch-size` flag defaults to 500 events per flush.[^c4e233156]

[^c4e233156]: supported · 2026-09-01 · src/relay.py:3
```

**Anchor when you can.** A derived id is computed from the identifiers a
sentence names, and about a third of claims in a real corpus name none — a
rewrite orphans those and their verdict is lost. An anchored claim can be
reworded freely; the verdict follows the marker, and only a change to what
the sentence *asserts* stales it. An anchored sentence also stays a claim
even if a rewrite leaves it matching no class, because the marker is the
author saying it is tracked.

**Two marker forms, because a footnote reference only renders as a neat
superscript when a definition exists.** Without one, markdown prints the raw
`[^c4e233156]` and the document looks vandalised — so a document that keeps
footnotes gets the footnote form, and a document that does not gets an HTML
comment (`<!--c4e233156-->`), which renders as nothing at all and costs the
same handful of tokens. Both are read as ids; a document can change form and
`init --anchor` swaps the markers over.

**Files an agent loads every session get markers and no footnotes.**
`CLAUDE.md`, `AGENTS.md`, `.cursorrules` and their kin are read into the
context of every session started in the repository, so a definitions block
there is paid for on every session, forever — in this repository it was 23%
of `CLAUDE.md`. The markers stay — invisible, since these files have no
footnotes to render against — because they are what carries identity and
they cost a fraction of the block; the provenance lives in the sidecar, one
`show` away. Ordinary documents keep their footnotes, where a human reader
benefits from them.

Those footnotes are provenance, not staging. Both sibling audits protect
them explicitly — `metadiscourse-audit`'s step 1 says why — so they are not
something a later cleanup pass will strip.

`init` then reports whether the repository's agent instructions mention the
ledger, and prints the block to add when they do not. **Read the printed
block to the user and let them decide.** `init --wire` appends it — and works on an
already-enrolled repo, since wiring is a decision that usually comes later
(AGENTS.md when both it and CLAUDE.md exist; nothing is created unless
`--create`). The `PostToolUse` hook behind `init --print-hook` is a separate,
opt-in offer —
a line of instruction and a hook that executes on every edit are different
levels of consent.

That line matters more than it looks: the gate catches an unverified claim
at merge, which is late. The instruction catches it in the session that
wrote it, which still has the code open.

## The whole surface

Four commands, because a person does four things — enrol once, ask what
needs attention, write down what they found, look up one sentence. Every
other view is the same comparison presented differently, so it is a flag on
`check` rather than a command of its own:

```bash
ledger.py init docs README.md    # once per repo; --anchor, --wire, --print-hook
ledger.py check                  # the gate; --backlog, --relocate, --prune
ledger.py record verdicts.json   # citations required
ledger.py show docs/relay.md:16  # provenance for one sentence, or c4e233156
```

`check` takes no corpus at all: the sidecars name their own documents, and a
gate that has to be told what to check is one that eventually gets
mis-invoked in CI, silently checking less than it reports.

## Step 2 — work the backlog

```bash
python3 "$LD" check --backlog --limit 10
```

Claims come back **batched by the evidence they need**, because the cost of
verifying one is dominated by loading the code that settles it: ten claims
about one file cost about one file's reading. Within that, ordered by class,
because a wrong default outranks a wrong adjective.

Ten a sitting is a real pace. It never has to finish — every claim verified
is one a reader can trust, and the ones behind it are no worse off than they
were.

## Step 3 — verify, disproof first

For each claim, **before opening the evidence, write down what would make it
false.** "The default timeout is 30 seconds" is false if the constant is
anything else, if no such default exists, or if the flag was renamed.

This ordering is the difference between an audit and a reading. Open the
code first and you will find a way to read the sentence as true — the code
always offers one. Then look, in the order the class suggests:

| Class | What it claims | Where it is settled |
| --- | --- | --- |
| **A** | a number or a default | the constant, the parser's default, the config schema |
| **B** | an interface: a flag, path, function, env var | the parser, the file's existence, the symbol, the call site |
| **C** | a guarantee: never, always, every, only, idempotent | the path that would violate it — and the test that would catch it |
| **D** | a dependency, version or platform | the packaging metadata, then the CI matrix |
| **E** | behaviour on error: returns, raises, retries, falls back | the handler and the retry loop |
| **F** | something external: a URL, a licence, a standard | the target itself; often unsettleable from the tree |

`references/falsification.md` has the recipes per class and the families of
claim that look false and are not. Read it when a verdict is not obvious;
**"your grep was wrong" is the commonest cause of a false Refuted.**

## Step 4 — record, with the evidence

```bash
python3 "$LD" record verdicts.json --by "$(whoami)"
```

```json
[
  {"id": "d44c8aea3bbe", "verdict": "refuted",
   "correction": "Relay retries a failed flush 3 times before parking the batch.",
   "severity": "high",
   "evidence": [{"file": "src/relay.py", "lines": "5", "symbol": "MAX_RETRIES",
                 "quote": "MAX_RETRIES = 3",
                 "note": "flush() loops range(MAX_RETRIES); no other retry path"}]},
  {"id": "62992a2b4053", "verdict": "unsupported",
   "searched": ["journal", "wal", "fsync", "src/**", "tests/**"],
   "note": "no journal in the tree; the claim may describe a component elsewhere"}
]
```

Four verdicts, and the script enforces what each one owes:

| Verdict | Means | `record` requires |
| --- | --- | --- |
| **supported** | the evidence entails the claim | evidence whose quote is really at those lines |
| **refuted** | the evidence contradicts it | evidence, **and the correction** |
| **unsupported** | nothing in the tree settles it | the list of what was searched |
| **unverifiable** | no evidence could settle it | nothing — it is a finding about the prose |

These are refusals, not suggestions: a `supported` with no evidence is
rejected, and so is a quote that is not actually at the line it cites. A
ledger of rubber-stamped verdicts is worse than no ledger, because it
launders assumption as evidence.

**Absence of evidence is `unsupported`, never `refuted`.** If you cannot
find the retry loop, the finding is that you could not find it — record the
search so a reader can falsify it.

**A supported guarantee with no test behind it is still a finding.** Put the
tests that guard it in `guarded_by`; an empty list means the claim is true
by accident today and will become false with nobody noticing.

## Step 5 — the gate

```bash
python3 "$LD" check             # 0 clean · 1 blocking · 2 nothing to check
python3 "$LD" check --strict    # unsupported blocks too
python3 "$LD" check --relocate  # re-address citations whose quote is intact
python3 "$LD" check --prune     # drop entries whose sentence is gone
```

`--relocate` is the one to reach for when a refactor moves code that claims
cite. Editing a file above a citation moves every line below it and changes
nothing about the evidence, so re-addressing is bookkeeping — it touches line
numbers and hashes, never a verdict. When the quote is *gone* rather than
moved, the evidence really changed and the claim goes back to a person.

Blocking: a new claim with no verdict, a stale one, a refuted one, an edited
claim that has lost its exemption. Advisory: unsupported, unverifiable, and
an orphan that used to carry a verdict — which means a documented fact was
deleted or reworded past recognition, and wants a person either way.

The gate is not "docs must be perfect". It is **no claim may go unexamined,
and no claim may be knowingly false.** A PR that changes a documented
constant has three honest ways out: fix the doc, re-verify the claim against
the new code, or mark it refuted with a correction and open an issue. What
it forecloses is the fourth — changing the code and letting the sentence
rot.

## Step 6 — report to a person

The ledger is machine state. A person wants the reading of it, so lead with
what a reader would act on:

```markdown
# Claim verification: <corpus> @ <commit>

**Coverage.** N of M claims carry a live verdict. Backlog: K exempt.
**Result.** N refuted · N unsupported · N supported · N unverifiable.

## Refuted (N)
| Claim | Where | Refuted by | Correction |

## Unsupported (N)
<claim, where, and what was searched for and not found>

## Unguarded guarantees (N)
<supported class C claims with an empty guarded_by, and the test that should exist>

## What the numbers mean
<coverage is not accuracy: it says every claim was examined, not that the
examining was infallible>
```

Coverage is not accuracy. The closest published system with this evidence
rule (Cascade, 2026) reports 0.88 precision at 0.21 recall — an exhaustive
pass with a strict evidence rule still misses most real inconsistencies. Say
"no claim went unexamined", never "the docs are true".

## Sampling, for a repo you do not own

```bash
python3 skills/lie-detector/scripts/scan.py docs -n 20 --seed drand:4210000
```

Stateless: it draws n claims by a lottery anyone can recompute from the
published seed, and the skill verifies those. Use it when you cannot check a
ledger in, when you want a rate before committing to a ledger, or when the
question is "how bad is this?" rather than "keep this true". The draw is
verifiable always, and unbiasable only when the seed came from outside the
corpus — the output says which you got. Report the result as a rate with its
interval (`scan.py --interval K N`), never as a verdict on the corpus.

## Scoping

Sample or enrol a **doc set**, not a file. Records — dated plans, specs,
ADRs, changelogs — are excluded by default: their claims were true of a
proposal on a date, and disproving them establishes only that the plan
changed.

Run this audit **after** its siblings on a corpus that needs both. A cleanup
audit will happily strip the wrapper off a false claim — "leverages a robust
30-second timeout" becomes "the timeout is 30 seconds", tidier and still
wrong — and verifying cleaned text produces findings about facts rather than
adjectives.
