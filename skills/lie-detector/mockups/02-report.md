# Mockup: the report

**Status: mockup for review.** What the skill hands a person after a full
first pass. Generated from the ledger, so every line here is derivable.

The numbers and file names are illustrative — a plausible run over a repo
shaped like `evals/fixtures/repo-d`, not output from a real one. Nothing in
this directory has been verified against anything, which is the joke.

---

# Claim verification: `docs/`, `README.md` @ `a6ae07d`

**Coverage.** 47 claims extracted, 47 with a live verdict (100%).
**Result.** 3 refuted · 6 unsupported · 31 supported · 7 unverifiable.
**Ledger.** `docs/.claims.toml` · re-check with `lie-detector verify --stale`

> Coverage is not accuracy. It says every claim was checked against
> evidence, not that the checking was infallible — the closest published
> system with this evidence rule (Cascade, 2026) reports 0.88 precision at
> 0.21 recall. Read 100% as "no claim went unexamined", not "the docs are
> true".

## Refuted (3)

Each of these is a reader acting on the doc and getting it wrong.

| Claim | Where | Evidence | Correction |
| --- | --- | --- | --- |
| "Relay retries a failed flush 5 times before parking the batch." | `docs/relay.md:16` | `src/relay.py:5` — `MAX_RETRIES = 3` | retries **3** times |
| "`--timeout` — 30 seconds — how long a sink may take" | `docs/relay.md:10` | `src/relay.py:4` — `TIMEOUT_SECONDS = 10` | **10 seconds** |
| "The parked-batch report is written to `var/parked.json` on every flush failure." | `docs/relay.md:31` | `src/relay.py:19-21` — `park()` appends in memory; the report is written by `jobs/nightly.py:44` | written **nightly**, not per failure |

All three cite `src/relay.py`. That is the shape of a doc that was true
against an older revision of one file — worth checking whether anything else
in the corpus was written in the same session.

## Unsupported (6)

Nothing in the tree settles these. Not lies — claims this repository cannot
answer for.

| Claim | Where | What was searched |
| --- | --- | --- |
| "Every batch is written to the journal before it is sent…" | `docs/relay.md:24` | `journal`, `wal`, `fsync`, `durable` across `src/**`, `tests/**` — no journal in the tree |
| "Relay requires Python 3.9 or newer." | `docs/relay.md:29` | no `pyproject.toml`, no `setup.cfg`, no CI matrix; the code parses on 3.8 |
| …4 more in the ledger | | |

The Python-version one is the interesting kind: it is *checkable in
principle* and unsettleable only because the repo has no packaging metadata.
That is a finding about the repo, not the sentence.

## Unguarded guarantees (2)

Supported today, and nothing would fail if they stopped being true.

| Claim | Where | Test that should exist |
| --- | --- | --- |
| "No event is ever delivered twice…" | `docs/relay.md:21` | a test that writes the same event id twice and asserts one sink write |
| "The drain never blocks longer than the configured timeout." | `docs/operations.md:8` | a test that stalls a sink and asserts the drain returns within `TIMEOUT_SECONDS` |

## Unverifiable (7)

Sentences no evidence could settle. Not defects — but a doc set that is
15% unfalsifiable is telling you where its prose stopped saying anything.

- `docs/relay.md:3` — "Relay is designed for reliability at any scale."
- `docs/operations.md:2` — "Draining is straightforward."
- …5 more in the ledger

## Coverage by file

| File | Claims | Supported | Refuted | Unsupported | Unverifiable |
| --- | ---: | ---: | ---: | ---: | ---: |
| `docs/relay.md` | 24 | 15 | 3 | 3 | 3 |
| `docs/operations.md` | 14 | 10 | 0 | 2 | 2 |
| `README.md` | 9 | 6 | 0 | 1 | 2 |

## What was excluded

- `docs/adr/`, `docs/plans/` — records. Their claims were true of a proposal
  on a date; disproving them establishes only that the plan changed.
- `src/**` comments — not requested. `--code` puts them in the corpus, and
  they are the cheapest claims in any repo to settle.
