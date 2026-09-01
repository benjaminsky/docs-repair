# Pivot: verify every claim, not a sample

**Status: mockup for review. Delete this directory before merge.**

The sampled version of this skill answered "roughly how wrong are these
docs?" — a rate with a confidence interval. This pivot answers a different
question: **"is every factual claim in these docs currently true, and what
is the evidence?"** That is a ledger, not a survey.

## Why exhaustive is affordable — the part that makes this work

Checking every claim once is expensive. Checking every claim *on every run*
is not affordable, which is why the first design sampled. The way out is not
a smaller sample; it is **not re-verifying what has not moved**.

Every verdict is recorded against two hashes: the claim's own normalised
text, and the evidence it was settled by (the file, symbol, and the hash of
the lines cited). A verdict stays live while both hashes hold. When either
moves — the sentence was edited, or the code it cited was — that one entry
goes **stale** and is the only thing re-verified.

So the first run is a full audit, and every run after it is a diff. A PR
that touches `TIMEOUT_SECONDS` invalidates the three claims that cite it and
nothing else.

This is `cargo-vet`'s model applied to prose: audits are recorded per
version, and a version bump requires only a delta audit rather than a fresh
review of the whole dependency.

## Four verdicts, and the one that matters most

Deliberately the FEVER labels plus one, because the fact-verification
literature settled this taxonomy and there is no reason to invent another:

| Verdict | FEVER | Meaning |
| --- | --- | --- |
| **Supported** | SUPPORTS | The cited evidence entails the claim. |
| **Refuted** | REFUTES | The cited evidence contradicts it. |
| **Unsupported** | NOT ENOUGH INFO | Nothing in the tree settles it either way. |
| **Unverifiable** | — | No evidence *could* settle it: the sentence asserts nothing checkable. |

The fourth is the addition, and it earns its place by being a finding about
the documentation rather than about the code. "Relay is designed for
reliability" is not true or false; it is a sentence that cannot be wrong,
which is worth knowing when a doc set is 60% made of them.

**Unsupported is never Refuted.** A grep that came back empty is a fact
about the search, not about the claim.

## What the ledger buys that a report does not

A report is read once. A ledger is a checked-in file with four uses:

1. **Incremental re-verification** — the point above.
2. **A CI gate** — `--check` fails the build when any claim is Refuted, or
   when a claim has no live verdict at all. Coverage becomes a number a
   team can hold: "97% of claims in `docs/` have a live verdict; 3 are
   stale since yesterday's push."
3. **An audit trail** — who or what verified a claim, when, against which
   revision. A doc set can then answer "when was this last checked?"
   per sentence rather than per file.
4. **A worklist** — stale entries are the queue, and they arrive ordered by
   the blast radius of the code change that staled them.

## Where this sits against prior art

Nothing found in the survey does exactly this, but three neighbours are
close enough to steal from, and one is close enough to worry about:

- **Docs-as-tests / Doc Detective (Silva).** Turns documented *procedures*
  into executable tests. Strictly better than prose verification where a
  claim is executable — a CLI invocation, an API call, a UI flow. It cannot
  touch the claims that are not procedures: defaults, guarantees, "the
  report is written nightly".
- **Cascade (2026).** LLM generates unit tests from a docstring, runs them
  against the real implementation and against a fresh implementation
  synthesised from the doc; an inconsistency is reported only when the
  original fails a test the synthesised code passes. Precision 0.88 —
  and **recall 0.21**. That number is the warning: exhaustive checking with
  a strict evidence rule finds few of the real inconsistencies, so a
  coverage percentage must never be read as "the docs are 97% true".
- **Doc-drift GitHub Actions** (doc-drift, driftcheck, DocDrift, Doc Drift
  Guard). All diff-triggered: changed code, LLM asks "does this contradict
  the docs?". Fast and cheap, but stateless — no ledger, no coverage, and a
  claim nobody's diff touches is never checked at all.
- **Comment-code inconsistency research** (iComment, @tComment, DOCREF,
  Panthaplackel's just-in-time detection). Twenty years of it, all scoped to
  comments and docstrings beside a method. The evidence-anchoring idea here
  is the same one; the scope is a whole doc corpus rather than a method.

The gap this fills: **corpus-wide, evidence-anchored, incremental, with a
coverage number and a durable ledger.** Everything above is either
procedure-shaped, method-shaped, or diff-shaped.
