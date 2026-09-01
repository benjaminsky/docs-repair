# Working in this repository

## Run the audit on every prose change

`README.md` is the only standing prose document here. Everything else is
either the skill's own text or a planted fixture. When you change it, run the
skill against it before committing, and act on what comes back.

CI does not gate this. The scanner over-reports by design, so a verdict on
each candidate needs someone deciding what the surviving fact is.

### Scanning it requires a copy

The two cleanup scanners exclude this repository's own `README.md` by
resolved path, along with `SKILL.md` and `references/`. A document about metadiscourse quotes
metadiscourse on nearly every line, and scanning it in place buries real
findings under its own vocabulary. Pointing the scanner at the file directly
exits 2 with `no standing markdown found` — that is the exclusion firing, not
a clean result. Read it as "not scanned".

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
against the surrounding paragraph rather than the line alone.

## What is a fixture

`evals/fixtures/` is planted deliberately, and CI depends on it staying that
way: `repo-a/CLAUDE.md` is clean by construction, and `repo-a/docs/` and the
comments in `repo-a/src/` are dirty by construction, which is how the
metadiscourse scanner's exit codes are pinned — including `--code`'s.
`repo-c` is the same arrangement for `ai-slop-audit`: `CLAUDE.md` clean,
`docs/` and the comments in `src/` dirty, with the phantom links
(`configuration.md`, `deploy.md`) broken on purpose. Do not clean the
fixtures, and do not "fix" those links.

`repo-d` is planted for `lie-detector`, and the plant is a disagreement
rather than a mess: `docs/` documents a 30-second timeout, five retries and
a parked-batch report written on every failure, while `src/relay.py` holds
`TIMEOUT_SECONDS = 10`, `MAX_RETRIES = 3` and writes that report from a
nightly job. Two of its guarantees are true, and the journal guarantee is
unsettleable from the tree on purpose — it is what an Unsupported verdict
is tested against. Do not reconcile the docs with the code there.

## Before committing

```bash
python3 skills/metadiscourse-audit/scripts/test_scan.py   # from its scripts/
python3 skills/ai-slop-audit/scripts/test_scan.py         # from its scripts/
python3 skills/lie-detector/scripts/test_scan.py          # from its scripts/
python3 skills/lie-detector/scripts/test_ledger.py        # from its scripts/
```

Bump `version` in both `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together when the skill changes; CI fails if
they drift.

`lie-detector`'s draw has to stay reproducible across machines and Python
versions, so nothing in its sampling path may depend on set iteration,
dictionary insertion order or the order a filesystem walk returns files. If
you touch `blocks()`, `normalise()` or the claim id, say so in the commit:
every published audit's `--verify` stops reproducing when a claim id moves.

The ledger has a sharper version of the same rule. `identity_key()` decides
which claim an entry *is*, and `skeleton()` decides when a verdict goes
stale; changing either silently re-keys or re-stales every ledger in the
wild. Touch them only deliberately, and never make `record` accept a verdict
that cites no evidence — that check is the reason a ledger is worth more
than an assertion. `ledger.py` also parses its own TOML below Python 3.11,
so any new field must round-trip through both readers: `test_ledger.py`
pins that.
