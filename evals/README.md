# Evals

Top-level `evals.json` and `trigger-eval.json` belong to metadiscourse-audit;
each other skill keeps its pair in its own subdirectory (`ai-slop-audit/`,
`lie-detector/`). Fixtures are shared: `repo-a` and `repo-b` are planted for
metadiscourse-audit, `repo-c` for ai-slop-audit, `repo-d` for lie-detector.

`evals.json` — three task prompts that exercise the skill body against
`fixtures/`, which carries planted artifacts: two version changelogs, a dated
status stamp, a tracker status claim, a mid-paragraph caveat, two lines of
filler in `--fix`'s safe set ("it is worth noting", "needless to say" — also
the README's worked example), protected evidence tags that must survive, and
an ADR that must not be touched.

`trigger-eval.json` — 20 queries, 9 should-trigger and 11 should-not, for
tuning the skill description. The negatives are deliberately near-misses:
AI-voice cleanup, doc-vs-code staleness, changelog generation, and the code
sense of "clean up". Easy negatives test nothing.

`lie-detector/` — three prompts against `fixtures/repo-d`, where `docs/`
states a timeout, a retry count and a report-writing behaviour that
`src/relay.py` contradicts, one guarantee the tree cannot settle either way,
and several claims that are true. The prompts separate the three things that
can go wrong: missing the planted lies, hand-picking the sample instead of
drawing one, and reporting an unsettleable claim as false.

`trigger-eval.json` there — 16 queries, 8 each way. The negatives are the
sibling audits' own territory plus the jobs that sound like fact-checking
and are not: proofreading, link checking, and claims about the outside world
that no repository can settle.
