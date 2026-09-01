# Mockup: `init`, and the cold start

**Status: mockup for review.** The gap in the first four: they all show a
repo that already has a ledger. This is how one gets there.

## The problem the other mockups ducked

A ledger-based design is cheap in the steady state and brutal on day one.
A mid-sized `docs/` holds several hundred claims; verifying all of them
before the tool does anything useful is a week nobody has. Any design that
requires that is a design nobody adopts.

Two tools solved exactly this and their answer is the same one:
[`cargo vet init`](https://mozilla.github.io/cargo-vet/setup.html) writes
every existing dependency into an **exemptions** list so the repo is green
on day one, then `cargo vet suggest` ratchets the list down. ESLint's
[bulk suppressions](https://eslint.org/blog/2025/04/introducing-bulk-suppressions/)
(v9.24, 2025) does it for lint rules: `--suppress-all` records today's
violations in `eslint-suppressions.json`, the rule is enforced on new code
immediately, and the backlog is burned down at whatever pace the team has.

So: **`init` grandfathers, it does not verify.**

## What `init` actually does

```console
$ lie-detector init docs README.md
Extracting claims from 14 file(s)...

  412 claims extracted
  318 with evidence candidates found mechanically
   94 with no candidate — these need a human to say what would settle them

Wrote docs/.claims.toml — 412 entries, all `unverified`, all `exempt`.

Backlog by class:
    A  numeric or default        88   ← start here: cheapest, most consequential
    B  interface                134
    C  guarantee                 71
    D  dependency or platform    22
    E  behaviour on error        49
    -  unverifiable (probable)   48   ← not claims; triage or cut

Next:  lie-detector plan --limit 10
Gate:  lie-detector check   (passes today: every claim is exempt)
```

Nothing is marked supported. An `unverified` entry is a claim the tool
*knows about*, not one it has any opinion on — recording a verdict nobody
established is the one thing this skill exists to prevent.

What `init` **can** do mechanically is the expensive half of verification:
finding the candidate evidence. A claim naming `` `--batch-size` `` gets the
argument parser's line; one naming `var/parked.json` gets every write to
that path. The judgement is left; the search is done.

```toml
[[claim]]
id = "4e2331565ece"
file = "docs/relay.md"
line = 13
text = "The `--batch-size` flag defaults to 500 events per flush."
text_hash = "b41c9f2a"
class = "A"
verdict = "unverified"
exempt = true                    # grandfathered by init on 2026-09-01
  [[claim.evidence_candidate]]   # ← not evidence yet; nobody has looked
  file = "src/cli.py"
  symbol = "build_parser"
  lines = "19"
  why = "the only mention of `--batch-size` in the tree"
```

## The gate, from day one

`check` enforces on **new and changed** claims only. Edit a sentence and its
`text_hash` moves, the exemption lapses, and that one claim needs a verdict
before the build is green. Write a new doc and every claim in it is born
un-exempt.

```console
$ lie-detector check
ok    409 exempt (grandfathered, unverified)
FAIL  docs/relay.md:41   new claim, no verdict
FAIL  docs/relay.md:16   claim edited since exemption — re-verify or re-exempt
ok    1 supported

2 blocking. Exemption backlog: 409 (was 412 at init, -3 this week).
```

The backlog number in the footer is the point. It only goes down, and it is
visible in every run, which is what makes a burn-down happen at all.

## Burning it down

```console
$ lie-detector plan --limit 10
10 claims, batched by the evidence they need — 3 files to open, not 10.

src/relay.py  (5 claims)
    docs/relay.md:10   `--timeout` — 30 seconds — how long a sink may take
    docs/relay.md:13   The `--batch-size` flag defaults to 500 events…
    docs/relay.md:16   Relay retries a failed flush 5 times…
    docs/relay.md:31   The parked-batch report is written to…
    docs/operations.md:12  Relay exposes counters on port 9102…

src/drain.py  (3 claims)
    …

pyproject.toml  (2 claims)
    …
```

Two things make the backlog affordable, and neither is sampling:

- **Batching by evidence locality.** The cost of verifying a claim is
  dominated by loading the code that settles it, not by the judgement. Ten
  claims about one file cost roughly one file's worth of reading. Ordering
  the backlog by claim id would cost ten.
- **Ordering by consequence.** Class A and B first — a wrong default or a
  flag that does not exist is what a reader acts on. Guarantees next.
  Probable-unverifiable last, since that queue is a writing problem and
  belongs to `ai-slop-audit` anyway.

At ten claims a sitting, batched, 412 is a few weeks of someone's coffee.
And it never has to finish to be useful: from the first run, no *new* lie
can enter the docs without the gate objecting.

## What this means for the skill's shape

Init is where it becomes obvious that the script and the skill are doing
two different jobs:

| Mechanical — the script | Judgement — the skill |
| --- | --- |
| extract claims, assign stable ids | decide what evidence would settle a claim |
| hash claim text and cited lines | read the code and reach a verdict |
| detect staleness, order the backlog | write the correction for a refuted claim |
| read/write the ledger, run the gate | decide a claim is unverifiable, not just hard |

So the artifact is a **ledger manager** (`init`, `plan`, `record`,
`verify --stale`, `check`) plus a skill that drives the verifying. That is a
different shape from the sibling audits, which are stateless: scan, print
candidates, exit. Worth naming rather than pretending otherwise.

It also gives the sampled design somewhere to live instead of being thrown
away. Two modes, one skill:

- **`sample`** — stateless, nothing checked in, a rate with an interval.
  The right tool for a repo you do not own, a due-diligence read, or a first
  look at whether a ledger is worth starting.
- **`ledger`** — stateful, checked in, exhaustive, gated. The right tool for
  docs you maintain.

`init` belongs only to the second.
