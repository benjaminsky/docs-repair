# Working in this repository

## Run the audit on every prose change

`README.md` and `evals/README.md` are the standing prose documents here.<!--cdcc0fa24-->
Everything else is either the skill's own text or a planted fixture. When you change it, run the
skill against it before committing, and act on what comes back.

CI does not gate this. The scanner over-reports by design, so a verdict on
each candidate needs someone deciding what the surviving fact is.<!--c581bd6e9-->

### Scanning it requires a copy

The two cleanup scanners exclude this repository's own `README.md` by
resolved path, along with `SKILL.md` and `references/`. A document about metadiscourse quotes
metadiscourse on nearly every line, and scanning it in place buries real
findings under its own vocabulary.<!--cff7ad4ec--> Pointing the scanner at the file directly
exits 2 with `no standing markdown found` — that is the exclusion firing, not
a clean result.<!--c8893e942--> Read it as "not scanned".

To scan it anyway, copy it somewhere outside the skill directory first:

```bash
cp README.md /tmp/audit/README.md
python3 skills/metadiscourse-audit/scripts/scan.py /tmp/audit
```

`lie-detector`'s scanner excludes nothing here, and should not: a claim this
README makes about the scanners is checkable against them, so drawing over
`README.md` and `CLAUDE.md` is the cheapest test that both are still true.

### Expect a high discard rate

Most candidates in this README are the document quoting the patterns it
documents — a superlative held up as an example of a collision, a caveat shown
as an example of a caveat. Those are Keep. The rate here runs well above the
one-in-three the skill warns about generally, so triage every candidate
against the surrounding paragraph rather than the line alone.<!--ca2390aa6-->

## What is a fixture

`evals/fixtures/` is planted deliberately, and CI depends on it staying that
way: `repo-a/CLAUDE.md` is clean by construction, and `repo-a/docs/` and the
comments in `repo-a/src/` are dirty by construction, which is how the
metadiscourse scanner's exit codes are pinned — including `--code`'s.<!--cf5ea24e1-->
`repo-c` is the same arrangement for `ai-slop-audit`: `CLAUDE.md` clean,
`docs/` and the comments in `src/` dirty, with the phantom links
(`configuration.md`, `deploy.md`) broken on purpose.<!--c7d689f59--> Do not clean the
fixtures, and do not "fix" those links.

`repo-d` is planted for `lie-detector`, and the plant is a disagreement
rather than a mess: `docs/` documents a 30-second timeout, five retries and
a parked-batch report written on every failure, while `src/relay.py` holds
`TIMEOUT_SECONDS = 10`, `MAX_RETRIES = 3` and writes that report from a
nightly job.<!--c9498a486--> Two of its guarantees are true, and the journal guarantee is
unsettleable from the tree on purpose — it is what an Unsupported verdict
is tested against.<!--c04a3c2ee--> Do not reconcile the docs with the code there.

## The claim ledger

`README.claims.toml` and `CLAUDE.claims.toml` sit beside the documents they
cover, one entry per factual claim with the evidence that settled it, and CI
gates on them.<!--ce3176568--> Editing either document means one of three things
afterwards, and the gate will tell you which:

```bash
python3 skills/lie-detector/scripts/ledger.py check
python3 skills/lie-detector/scripts/ledger.py check --backlog
python3 skills/lie-detector/scripts/ledger.py record verdicts.json --by "$(whoami)"
```

Every claim here is **anchored**: the sentence carries its own id, as an
invisible HTML comment here and as a markdown footnote (`[^c4e233156]`) in
`README.md`.<!--c33ff1498--> `README.md` also carries the block of definitions saying
what settled each one; this file deliberately carries neither block nor
visible marker, because it is loaded into every session and the sidecar holds
the same provenance.<!--c073d0dd0--> Reword an anchored sentence however you like — the
verdict follows the anchor. Change what it *asserts*, a number or a unit or a
"never", and it goes stale, which is the point.<!--c82c1b787--> Do not hand-edit the anchors
or the footnote block; `record` rewrites them.

Those footnotes are metadiscourse, and they are protected on purpose: their
subject is whether a sentence is true, which is the one thing about a
document a reader cannot get by reading it.<!--cc4473b48--> Both cleanup scanners skip them,
and `metadiscourse-audit`'s step 1 says why.<!--cd126ce25-->

When a refactor moves code that claims cite, `check --relocate` re-addresses
the citations whose quote is unchanged; it touches line numbers, never a
verdict.<!--c454420bc--> A reworded sentence holds its verdict; a changed number, unit or quantifier
does not, and neither does a claim whose cited code moved. `record` rejects
a supported or refuted verdict that quotes no evidence, and rejects a quote
that is not at the line it cites — do not work around that, it is the only
thing making the ledger worth more than an assertion.<!--cef5ff1ca-->

Nine claims sit at `unsupported`, all of them about Claude Code's cloud
environment, which no checkout can settle.<!--c6b780797--> That verdict is advisory here on
purpose; do not "fix" them by inventing evidence.

## Before committing

```bash
python3 skills/metadiscourse-audit/scripts/test_scan.py   # from its scripts/
python3 skills/ai-slop-audit/scripts/test_scan.py         # from its scripts/
python3 skills/lie-detector/scripts/test_scan.py          # from its scripts/
python3 skills/lie-detector/scripts/test_ledger.py        # from its scripts/
```

Bump `version` in both `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together when the skill changes; CI fails if
they drift.<!--cbc8891c7-->

`lie-detector`'s draw has to stay reproducible across machines and Python
versions, so nothing in its sampling path may depend on set iteration,
dictionary insertion order or the order a filesystem walk returns files.<!--c8be0c524--> If
you touch `blocks()`, `normalise()` or the claim id, say so in the commit:
every published audit's `--verify` stops reproducing when a claim id moves.<!--c719a12a5-->

The ledger has a sharper version of the same rule. `identity_key()` decides
which claim an entry *is*, and `skeleton()` decides when a verdict goes
stale; changing either silently re-keys or re-stales every ledger in the
wild.<!--c435bb17f--> Touch them only deliberately, and never make `record` accept a verdict
that cites no evidence — that check is the reason a ledger is worth more
than an assertion.<!--c82fce89e--> `ledger.py` also parses its own TOML below Python 3.11,
so any new field must round-trip through both readers: `test_ledger.py`
pins that.<!--c31aa6714-->
