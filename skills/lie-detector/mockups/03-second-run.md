# Mockup: the second run, and the CI gate

**Status: mockup for review.** The first run is an audit. Every run after it
is a diff — this is the file that shows why the pivot is affordable.

## A PR changes one constant

```console
$ git diff --stat
 src/relay.py | 2 +-

$ lie-detector verify --stale
2 claim(s) stale, 45 live.

docs/relay.md:16  4e2331565ece  evidence moved
    "Relay retries a failed flush 5 times before parking the batch."
    was: src/relay.py:5  MAX_RETRIES = 3   (hash 22c8ab90)
    now: src/relay.py:5  MAX_RETRIES = 8   (hash c1f70b2e)

docs/operations.md:5  6e9733757e14  evidence moved
    "The drain exits with status 0 once the last batch is acknowledged."
    was: src/drain.py:22-31  (hash 5ac09817)
    now: src/drain.py:22-34  (hash 0e4471aa)

45 live verdict(s) untouched — their claims and evidence are unchanged.
Re-verify the 2 above, then: lie-detector record --from-report <file>
```

Two claims to check, not forty-seven. The claim about batch size did not
move, so nobody spends a second on it.

And the first entry is the good case: the doc said 5, the code said 3, and
the code has now become 8. The stale entry catches that the *correction in
flight* is already out of date.

## The CI gate

```console
$ lie-detector verify --check
FAIL  docs/relay.md:16   refuted        MAX_RETRIES = 3, doc says 5
FAIL  docs/relay.md:31   stale          evidence src/relay.py:19-21 changed
WARN  docs/relay.md:24   unsupported    no journal in the tree
ok    44 live verdict(s)

2 blocking, 1 advisory. Coverage 95% (45/47 live).
```

Exit codes: `0` all live and none refuted · `1` refuted or stale · `2`
nothing to verify. Unsupported is advisory by default (`--strict` promotes
it), because a doc set that legitimately describes an external component
should not be unable to pass its own gate.

## What a team actually does with this

The gate is not "docs must be perfect" — it is **"no claim may go
unexamined, and no claim may be knowingly false."** A PR that changes a
constant has three honest ways out:

1. Fix the doc, re-verify, commit the ledger entry.
2. Verify the claim is still true against the new code and re-record it.
3. Mark it refuted with a correction and open an issue — the ledger keeps
   the failing entry, which is louder than a silent stale doc.

What it forecloses is the fourth: changing the code and letting the sentence
rot, which is the failure this whole skill exists for.

## Open questions for review

1. **Ledger location.** `docs/.claims.toml` beside the corpus, or
   `.lie-detector/claims.toml` at the root? Beside the corpus reviews
   better in a docs PR; at the root survives a docs reorganisation.
2. **Is the CI gate in scope at all,** or does this stay a skill that
   produces a ledger and leaves the enforcement to the team? A gate needs
   the extraction to be very stable, or every prose edit becomes a red
   build.
3. **`unverifiable` as a warning?** 15% unfalsifiable prose is a real
   finding, but it is a *writing* finding, which is the sibling audits'
   territory. Report it and stop, or hand it to `ai-slop-audit`?
4. **Who records a verdict.** The mockups show `verified_by =
   "claude-opus-5"`. A human-recorded verdict and a model-recorded one are
   not the same evidence; should the ledger distinguish them, and should CI
   be able to require a human for `severity = "high"` corrections?
