# Mockup: the flows, and where they chafe

**Status: mockup for review.** Eight flows, then the five places this design
is most likely to be annoying enough that someone turns it off.

## How a claim gets into the ledger at all

The worry this answers: *"who remembers to add an entry when the docs
change?"* Nobody, and nobody has to — **the ledger is derived state, not a
registry you maintain.**

Every run re-extracts the claim set from the documents themselves and
compares it to the ledger. That comparison has four outcomes:

| In the docs | In the ledger | Meaning |
| --- | --- | --- |
| yes | no | **new claim** — born un-exempt, needs a verdict |
| yes | yes, hashes match | live — nothing to do |
| yes | yes, a hash moved | **stale** — claim edited, or its evidence was |
| no | yes | **orphan** — the sentence is gone; prune the entry |

So a doc edit cannot silently escape the ledger. The tool notices by
recomputing, not by being told. Forgetting is not a failure mode; the only
failure mode is *ignoring* what it recomputed, and that is what the gate is
for.

**Where the recompute runs** — three options, and they stack:

1. **CI, on every PR** (authoritative). The gate blocks a merge that adds an
   unverified claim or leaves a staled one. Slow feedback, but it is the one
   that actually holds the line.
2. **A git pre-push hook** (fast). Same check, before the push. Skippable
   with `--no-verify`, which is the point: it advises, CI enforces.
3. **A Claude Code hook, at agent time** (cheapest, and the interesting
   one). `PostToolUse` on a `Write`/`Edit` to `docs/**` runs `check`; if it
   reports a new or staled claim, the session verifies it *right then*.

Option 3 is where this design earns its keep, because of a timing argument:
**the cheapest moment to verify a claim is the moment its code changes, in
the session that changed it.** That session already has the constant, the
call site and the reason loaded. A week later, in CI, someone reloads all of
it from cold. This is the same instinct as the just-in-time comment
inconsistency literature, moved from the method to the corpus.

## The flows

### 1. Day 0 — adopt it

```console
$ lie-detector init docs README.md
412 claims extracted, all unverified and exempt. Gate passes.
$ git add docs/.claims.toml && git commit -m "chore: enrol docs in claim ledger"
```

One command, one commit, green build. Nothing is claimed to be true. The
value on day 0 is entirely "no *new* lies from here", which is worth having
before a single claim is verified.

### 2. Burn down the backlog

```console
$ lie-detector plan --limit 10
10 claims, 3 files to open.
```

Agent reads the three files, reaches ten verdicts, records them. Backlog
`412 → 402`, and the footer says so on every subsequent run. Repeatable in
twenty-minute sittings; never has to finish.

### 3. A writer edits a doc

Changes "retries 5 times" to "retries 5 times before parking". Claim's
`text_hash` moves → exemption lapses → gate objects with the one claim.
Writer either verifies it (and discovers it was 3 all along) or re-exempts
it with a note. **The friction is proportional: one sentence, one claim.**

### 4. An engineer changes code

`MAX_RETRIES = 3` → `8`. Three claims citing `src/relay.py:5` go stale.
The gate names them, with the old and new quoted lines side by side. The
engineer fixes the docs in the same PR — which is the entire point, because
that is the PR where they know the answer.

### 5. An agent writes a new doc

Every claim in it is new, so every claim is un-exempt and the gate blocks
until each is verified. This is the flow that matters most in 2026: a
session that generates 40 confident sentences about code it half-read
cannot merge them unverified. The agent verifies them in the same session,
or the doc does not land.

### 6. A reviewer reads the PR

The gate's comment is the review aid: *"this PR adds 4 claims (all
verified, evidence cited), stales 2 (re-verified), and refutes 0."* A
reviewer who trusts the ledger can skip re-deriving whether the prose
matches the diff, which is the tedious half of reviewing a docs PR.

### 7. Someone asks "is this still true?"

```console
$ lie-detector show docs/relay.md:16
supported · verified 2026-08-30 by claude-opus-5 @ 7df4c05
evidence: src/relay.py:5  MAX_RETRIES = 3  (hash 22c8ab90, unchanged since)
```

Per-sentence provenance. This is the flow a ledger enables and a report
never can, and it is the one that makes docs trustworthy to *readers*
rather than only to maintainers.

### 8. Somebody else's repo

```console
$ lie-detector sample docs -n 20 --seed drand:4210000
```

No ledger, nothing checked in, a rate with an interval. Due diligence on a
dependency, or deciding whether a ledger is worth starting here at all.

## Where this will chafe

Listed because a tool that annoys people gets switched off, and every one of
these is a plausible reason to switch it off.

1. **Cosmetic edits staling real verdicts.** Hashing normalised text means
   fixing a typo in a verified sentence invalidates its verdict. Doing that
   ten times in a copy-edit pass produces ten pointless re-verifications.
   *Fix:* hash the **claim skeleton** — the numbers, identifiers,
   quantifiers and negations — not the prose around them. "Retries 5 times"
   → `retries|5|times`. Rewording survives; changing 5 to 3 does not.
   Needs care: "never" → "rarely" must move the skeleton.
2. **Reworded sentences losing their history.** A rewrite reads as
   orphan + new claim, discarding the audit trail. *Fix:* rename detection,
   the way git matches a moved file by similarity, plus
   `record --supersedes <id>` when the tool guesses wrong.
3. **Ledger merge conflicts.** Two docs PRs both append entries. TOML with
   one table per claim and a stable sort order conflicts far less than
   JSON, but it will still happen. *Fix:* sort by claim id, keep entries
   append-only-ish, and ship a `--merge` that resolves by union.
4. **The unverifiable pile.** If 15% of a doc set is "designed for
   reliability", the gate nags about sentences that are a *writing*
   problem. *Fix:* `unverifiable` is advisory-only and reported once as a
   count, with the list handed to `ai-slop-audit` rather than to the gate.
5. **Verdicts nobody trusts.** A ledger full of `verified_by =
   "claude-opus-5"` is only as good as that verification, and a
   rubber-stamped ledger is worse than none — it launders assumption as
   evidence. *Fix:* every verdict must cite a `file:line` quote, and a
   verdict with no evidence quote is rejected at `record` time by the tool
   itself. `unsupported` is the honest escape hatch, and it must stay
   cheaper to record than a fake `supported`.

Number 5 is the one that decides whether any of this is worth building.
