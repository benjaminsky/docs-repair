# Evals

`evals.json` — three task prompts that exercise the skill body against
`fixtures/`, which carries planted artifacts: two version changelogs, a dated
status stamp, a tracker status claim, a mid-paragraph caveat, protected
evidence tags that must survive, and an ADR that must not be touched.

`trigger-eval.json` — 20 queries, 9 should-trigger and 11 should-not, for
tuning the skill description. The negatives are deliberately near-misses:
AI-voice cleanup, doc-vs-code staleness, changelog generation, and the code
sense of "clean up". Easy negatives test nothing.
