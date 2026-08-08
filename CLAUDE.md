# Working in this repository

## Run the audit on every prose change

`README.md` is the only standing prose document here. Everything else is
either the skill's own text or a planted fixture. When you change it, run the
skill against it before committing, and act on what comes back.

CI does not gate this. The scanner over-reports by design, so a verdict on
each candidate needs someone deciding what the surviving fact is.

### Scanning it requires a copy

`scan.py` excludes this repository's own `README.md` by resolved path, along
with `SKILL.md` and `references/`. A document about metadiscourse quotes
metadiscourse on nearly every line, and scanning it in place buries real
findings under its own vocabulary. Pointing the scanner at the file directly
exits 2 with `no standing markdown found` — that is the exclusion firing, not
a clean result. Read it as "not scanned".

To scan it anyway, copy it somewhere outside the skill directory first:

```bash
cp README.md /tmp/audit/README.md
python3 skills/metadiscourse-audit/scripts/scan.py /tmp/audit
```

### Expect a high discard rate

Most candidates in this README are the document quoting the patterns it
documents — a superlative held up as an example of a collision, a caveat shown
as an example of a caveat. Those are Keep. The rate here runs well above the
one-in-three the skill warns about generally, so triage every candidate
against the surrounding paragraph rather than the line alone.

## What is a fixture

`evals/fixtures/` is planted with metadiscourse deliberately, and CI depends
on it staying that way: `repo-a/CLAUDE.md` is clean by construction, and
`repo-a/docs/` and the comments in `repo-a/src/` are dirty by construction,
which is how the scanner's exit codes are pinned — including `--code`'s. Do
not clean the fixtures.

## Before committing

```bash
python3 skills/metadiscourse-audit/scripts/test_scan.py   # from scripts/
```

Bump `version` in both `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` together when the skill changes; CI fails if
they drift.
