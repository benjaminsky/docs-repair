# Falsifying a claim

Load this when a verdict is not obvious: the recipes per class, the rules
that decide the hard cases, and the families of claim that look false and
are not. `SKILL.md`'s table is enough for clear cases.

## Class A — a number or a default

**Disproof:** find the value in the tree and compare. The order to look in
is argument parser default, config schema default, module constant,
environment fallback, and finally the call site — a documented default is
wrong as often because it moved to a different layer as because the number
changed.

```
docs/relay.md:13   "The `--batch-size` flag defaults to 500 events."
src/relay.py:3     BATCH_SIZE = 500                    → True
src/cli.py:22      parser.add_argument("--batch-size", default=100)
                                                       → False. The constant
                   is 500; the flag's default is 100, and the flag is what
                   the sentence is about.
```

**The trap:** two true values in different places. Say which one the
sentence claims, and report the divergence — a constant the CLI overrides
is a finding whether or not the doc is wrong.

**Units count.** "30 seconds" against `TIMEOUT_MS = 30000` is True; against
`TIMEOUT = 30` in a function that takes milliseconds it is False, and worth
leading with, because it is the kind of error that reaches production.

## Class B — an interface

**Disproof:** the flag, path, function, endpoint or variable either exists
as described or does not. Grep the parser, not the docs; `ls` the path; open
the symbol. A renamed flag with a compatibility alias is True with a note.

The strongest finding in this class is the documented feature that was never
built — a flag no parser defines, an endpoint no router serves. It outranks
everything else in the report, because a reader following the doc gets an
error, not a surprise.

**The trap:** the interface exists but does something else. Check the body,
not the signature: `--dry-run` that is parsed and never read is False, and
the greps that would have said True stop one line too early.

## Class C — a guarantee

**Disproof:** find the path that violates it. "No event is ever delivered
twice" is broken by any retry that does not deduplicate; "every batch is
journalled before it is sent" is broken by one code path that sends first.

This class has a second, quieter finding, and it is the one worth reporting
even when the claim holds: **is there a test that would fail if this broke?**
A guarantee no test guards is not a lie — it is a claim whose truth is
currently accidental, and it will become a lie without anyone editing the
sentence. Report it as unguarded, and name the test that should exist.

**The trap:** the guarantee is scoped and the sentence dropped the scope.
"Never" that means "never, within a single process" is a doc bug even when
the code is right; the verdict is False with the scope as the correction.

## Class D — a dependency, version or platform

**Disproof:** the packaging metadata and the CI matrix, in that order. A
`requires-python` of `>=3.8` refutes "requires Python 3.9 or newer", and so
does a CI job that runs 3.8 green. Untested is not unsupported — say which
one the evidence shows.

**The trap:** "works on Windows" where nothing in CI runs on Windows. That
is Unsupported, not False: absence of a test is absence of evidence. The
finding is that a support claim rests on nobody having tried it.

## Class E — behaviour on error

**Disproof:** the handler. Follow the failure path — what the function
returns, what it raises, whether the retry loop it claims exists is bounded,
what the process exits with. Documented retries that are unbounded, or
absent, are common and consequential.

**The trap:** the behaviour is right but only under a condition the sentence
omits. "Falls back to the cache on error" that is true for timeouts and
false for auth failures is False with the condition as the correction, not
True with a caveat.

## Class F — something external

Usually **Unsupported from the tree**, and that is the honest verdict. A URL
can be checked if fetching is available; a licence can be checked against
the licence file and the package metadata; a claim about a third party's
behaviour usually cannot be checked at all.

Do not spend the sample here. If a draw lands on an unresolvable external
claim, that is Unsupported, and it stays in the tally as a claim the
documentation makes on someone else's authority.

# Claims that look false and are not

1. **The doc describes the interface; the code you found is the
   implementation.** A wrapper's default overrides a library's. Check which
   layer the sentence is about before calling it wrong.

2. **Stale in the branch, correct on the release.** A claim can be true of
   the version the docs ship with and false of `HEAD`. Say which revision
   you checked — the audit's header carries the commit for this reason.

3. **The generated file disagrees with its source.** Compare against the
   generator's input, not its stale output, or every regenerated file reads
   as a corpus of lies.

4. **Rounding and idiom.** "About a second" against 1200 ms is True; "under
   a second" against the same is False. The verdict follows the claim's own
   precision, not yours.

5. **A conditional read as absolute.** "Retries are disabled in tests" is
   not refuted by the retry loop existing. Read the whole sentence,
   including the clause that scopes it.

6. **Your grep was wrong.** The commonest cause of a false "False". Before
   filing one, search for the symbol a second way — a different spelling, a
   different file type, the test suite. Unsupported is the verdict for a
   search that came back empty; False needs the contradicting line quoted.

# What the ledger asks of each verdict

`record` enforces these; the reasoning is here so the enforcement does not
read as bureaucracy.

**supported** — cite the `file:line` and quote it. The quote is checked
against the file, so a citation that does not say what the verdict claims is
rejected. Add `guarded_by` when a test would catch the claim breaking, and
leave it empty when none would: a guarantee true by accident is a finding.

**refuted** — cite the contradicting line *and* write the correction. Whoever
trusted the sentence needs the true statement, not just the news that the old
one was wrong. Set `severity` high when a reader acting on the claim gets a
wrong result.

**unsupported** — record what you searched. This is what makes the verdict
falsifiable by the next reader: if the journal does exist and the search was
bad, the list shows exactly how it was bad. An unsupported verdict is never a
failure to try; it is the honest answer when the tree cannot settle a claim,
and it must stay cheaper to record than a fabricated supported.

**unverifiable** — no evidence could settle the sentence. Report the count;
the individual sentences are `ai-slop-audit`'s territory, since a doc set
that is 15% unfalsifiable has a writing problem rather than a truth problem.

# When a claim moves

The ledger distinguishes two kinds of edit, and it is worth knowing which
you are looking at:

- **The skeleton moved** — a number, unit, quantifier or identifier changed.
  The claim now asserts something different, and the old verdict says nothing
  about it. Re-verify.
- **The evidence moved** — the cited lines changed under a verdict that still
  reads correctly. Re-verify *against the new lines*: this is the case where
  a doc was right, the code changed, and the doc is now wrong without anyone
  touching it. It is the whole reason the ledger hashes evidence.

A rewrite that changes both is an orphan plus a new claim. When it is
genuinely the same claim reworded, record the new one with
`supersedes = "<old id>"` so the history survives.

# What a sample supports

The scanner's `--interval K N` prints a 95% Wilson interval, which is the
sentence the report should carry instead of an adjective. Some shapes worth
recognising:

| Found | Drawn | Observed | 95% interval | The sentence to write |
| --- | --- | --- | --- | --- |
| 0 | 10 | 0% | 0-28% | Nothing disproved; the corpus could still be a quarter wrong |
| 0 | 20 | 0% | 0-16% | Nothing disproved; a rate above one in six is unlikely |
| 0 | 50 | 0% | 0-7% | Nothing disproved, and the rate is bounded tightly |
| 1 | 20 | 5% | 1-24% | One lie found; the rate is poorly determined either way |
| 4 | 20 | 20% | 8-42% | One claim in five is wrong; this doc set needs a pass, not a sample |

Two rules follow from that table. A draw of ten cannot support "the docs are
in good shape" — it cannot distinguish a clean corpus from a corpus that is
a quarter false. And a high observed rate does not need a bigger sample: at
one in five, stop sampling and audit the whole corpus, because the sample
has already answered the only question it was asked.
